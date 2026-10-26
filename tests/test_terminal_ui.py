"""UI regression tests use committed alert state; never send real notifications."""
from contextlib import redirect_stdout
import io
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from rich.console import Console
import monitor_ssh as m
from terminal_ui import TerminalDashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = m.Store(Path(self.directory.name) / "state.sqlite3")
        self.config = m.Config(host="192.168.73.129", temp_enabled=False,
                               ssh_password="SENTINEL_PRIVATE_PASSWORD", telegram_token="SENTINEL_PRIVATE_TOKEN")
        self.channel = SimpleNamespace(key="tg", kind="telegram")
        self.stream = io.StringIO()
        self.console = Console(file=self.stream, width=120, color_system=None, force_terminal=False)
        self.view = TerminalDashboard(self.config, self.store, [self.channel], live=True, console=self.console)

    def sample(self, **overrides):
        sample = m.Sample({"cpu": 87.68472906403942, "ram": 46.3523296075903, "iface": "up", **overrides})
        self.store.observe(self.config, sample, ["tg"])
        self.view.sample_received(sample)

    def render(self):
        self.stream.seek(0)
        self.stream.truncate()
        self.console.print(self.view.render())
        return self.stream.getvalue()

    def test_rounding_thresholds_disabled_temperature_and_secret_exclusion(self):
        self.sample()
        text = self.render()
        self.assertIn("87.7%", text)
        self.assertIn("46.4%", text)
        self.assertNotIn("87.684729", text)
        self.assertIn("> 75%", text)
        self.assertIn("CẢNH BÁO", text)
        self.assertIn("ĐÃ TẮT", text)
        self.assertIn("ens33", text)
        self.assertNotIn("SENTINEL_", text)
        self.assertNotIn("0.0°C", text)

    def test_display_uses_persisted_hysteresis_instead_of_simple_threshold(self):
        self.sample(cpu=90)
        self.sample(cpu=72)
        text = self.render()
        self.assertIn("72.0%", text)
        self.assertIn("CẢNH BÁO", text)
        self.assertIn("CPU ≤ 70%", text)

    def test_connection_loss_marks_cached_values_as_stale(self):
        self.sample()
        self.store.observe(self.config, None, ["tg"], connection_error="test timeout")
        self.view.device_failed("test timeout")
        text = self.render()
        self.assertIn("MẤT KẾT NỐI", text)
        self.assertIn("87.7% (cũ)", text)
        self.assertIn("CHƯA CẬP NHẬT", text)
        self.assertNotIn("BÌNH THƯỜNG", text)

    def test_missing_data_is_never_displayed_as_zero_or_normal(self):
        self.sample(cpu=None, ram=None, iface="unknown")
        text = self.render()
        self.assertIn("KHÔNG XÁC ĐỊNH", text)
        self.assertNotIn("0.0%", text)
        self.assertNotIn("BÌNH THƯỜNG", text)

    def test_retry_queue_then_acknowledged_delivery(self):
        self.sample()
        self.view.sending("tg")
        self.assertIn("Đang gửi...", self.render())
        self.view.delivery("tg", m.Delivery(False, "HTTP 503"))
        event = self.store.due("tg", 10**12)
        with patch("terminal_ui.time.time", return_value=1000):
            self.store.failed(event[0], 0, retry_after=30)
        with patch("terminal_ui.time.time", return_value=1001):
            text = self.render()
        self.assertIn("Thử lại sau 29s", text)
        self.store.delivered(event[0])
        self.view.delivery("tg", m.Delivery(True))
        text = self.render()
        self.assertIn("Đã gửi thành công", text)

    def test_unavailable_storage_does_not_look_like_empty_queue(self):
        self.sample()
        with patch.object(self.store, "display_snapshot", side_effect=OSError()):
            self.assertIn("Không đọc được hàng đợi", self.render())

    def test_piped_output_has_no_ansi_cursor_controls(self):
        self.sample()
        self.assertFalse(self.view.use_live)
        self.view.show_once()
        self.assertNotIn("\x1b", self.stream.getvalue())

    def test_narrow_terminal_keeps_values_and_states(self):
        self.console.width = 72
        self.sample()
        text = self.render()
        self.assertIn("87.7%", text)
        self.assertIn("CẢNH BÁO", text)
        self.assertNotIn("Mức sử dụng", text)

    def test_hybrid_rows_show_partial_failure_sources_and_simulation_label(self):
        self.config.protocol="hybrid"
        self.config.temp_enabled=True
        self.config.temp_source="demo"
        sample=m.Sample({"cpu":40,"ram":50,"temp":75,"iface":"up","ssh":"down","snmp":"up"},
                        {"ssh":"SSH unavailable"},
                        {"cpu":"SNMP","temp":"SNMP / DEMO","iface":"SNMP / IF-MIB"})
        self.store.observe(self.config,sample,["tg"])
        self.view.sample_received(sample)
        text=self.render()
        for value in ("Kênh SSH","Kênh SNMP","MÔ PHỎNG","SNMP / IF-MIB","DOWN","75.0°C"):
            self.assertIn(value,text)

    def test_logging_redirect_and_cleanup_restore_caller_settings(self):
        logger = logging.getLogger("device_monitor")
        original_handlers, original_level, original_propagate = list(logger.handlers), logger.level, logger.propagate
        self.view.start()
        try:
            logger.warning("Telegram đang giữ tin để thử lại")
            self.assertIn("Telegram đang giữ tin", self.stream.getvalue())
        finally:
            self.view.stop()
        self.assertEqual(logger.handlers, original_handlers)
        self.assertEqual(logger.level, original_level)
        self.assertEqual(logger.propagate, original_propagate)

    def test_cli_table_output_and_exit_status_reflect_delivery_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"MONITOR_HOST": "device.test", "SSH_USER": "fixture",
                   "TELEGRAM_TOKEN": "123:fake_token", "TELEGRAM_CHAT_ID": "1000",
                   "MONITOR_TEMP_ENABLED": "false",
                   "MONITOR_STATE_FILE": str(Path(directory) / "state.sqlite3")}
            channel = Mock(key="tg", kind="telegram")
            channel.send.return_value = m.Delivery(False, "HTTP 503")
            output = io.StringIO()
            with patch.dict("os.environ", env, clear=True), patch.object(m, "SSHCollector") as collector, patch.object(m, "Channel", return_value=channel), redirect_stdout(output):
                collector.return_value.collect.return_value = m.Sample({"cpu": 90., "ram": 40., "iface": "up"})
                with self.assertLogs(m.LOG, level="WARNING"):
                    result = m.main(["--once", "--display", "table"])
            self.assertEqual(result, 1)
            text = output.getvalue()
            self.assertIn("90.0%", text)
            self.assertIn("CẢNH BÁO", text)
            self.assertIn("Thử lại sau", text)
            self.assertNotIn("123:fake_token", text)


if __name__ == "__main__":
    unittest.main()
