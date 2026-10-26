"""Beginner path: short wizard, two-NIC lab and the actual monitoring entry point."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from dotenv import dotenv_values
import monitor as simple
import setup_project as setup
from device_monitor.models import Delivery, Sample
from lab.linux.configure_network import netplan_text
from tools.create_gns3_project import simple_project


class SimpleTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict("os.environ", {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = self.root / ".env.simple"

    def profile(self, **extra):
        values = {
            "MONITOR_HOST": "192.168.10.129", "SSH_USER": "fixture",
            "MONITOR_PROTOCOL": "ssh", "MONITOR_OS": "linux",
            "SSH_PASSWORD": "local-fixture-password", "MONITOR_IFACE": "ens33",
            "MONITOR_TEMP_ENABLED": "false",
            "TELEGRAM_TOKEN": "123:fake_fixture", "TELEGRAM_CHAT_ID": "1000",
            "MONITOR_STATE_FILE": str(self.root / "state.sqlite3"),
        }
        values.update(extra)
        setup.save_settings(self.env, values)
        return values

    def test_wizard_reuses_only_credentials_and_leaves_old_profile_unchanged(self):
        (self.root / "examples").mkdir()
        source = setup.ROOT / "examples/simple.env"
        (self.root / "examples/simple.env").write_bytes(source.read_bytes())
        old = self.root / ".env.gns3"
        saved = self.profile(MONITOR_HOST="192.168.73.129", MONITOR_IFACE="gns3test")
        self.env.rename(old)
        before = old.read_bytes()
        out = io.StringIO()
        with patch.object(setup, "ROOT", self.root), \
             patch.object(setup, "ask", side_effect=lambda label, default="": default), \
             patch.object(setup, "ask_secret", side_effect=lambda label, previous="": previous), \
             redirect_stdout(out):
            setup.configure_simple(self.env)
        values = dotenv_values(self.env, interpolate=False)
        self.assertEqual((values["MONITOR_HOST"], values["MONITOR_IFACE"]),
                         ("192.168.10.129", "ens33"))
        self.assertEqual(values["SSH_PASSWORD"], saved["SSH_PASSWORD"])
        self.assertEqual(values["TELEGRAM_TOKEN"], saved["TELEGRAM_TOKEN"])
        self.assertEqual(old.read_bytes(), before)
        self.assertNotIn(saved["SSH_PASSWORD"], out.getvalue())
        self.assertNotIn(saved["TELEGRAM_TOKEN"], out.getvalue())

    def test_bad_simple_settings_do_not_replace_saved_secrets(self):
        self.profile()
        before = self.env.read_bytes()
        def ask(label, default=""):
            return "bad;host" if label == "IP Linux qua GNS3" else default
        with patch.object(setup, "ask", side_effect=ask), \
             patch.object(setup, "ask_secret", side_effect=lambda label, previous="": previous), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(setup.SetupError):
                setup.configure_simple(self.env)
        self.assertEqual(self.env.read_bytes(), before)

    def test_simple_topology_contains_exactly_the_management_path(self):
        value = simple_project({1: "Adapter VMnet1", 2: "Adapter VMnet2"})
        nodes, links = value["topology"]["nodes"], value["topology"]["links"]
        self.assertEqual(len(nodes), 3)
        self.assertEqual(len(links), 2)
        self.assertEqual(sorted(n["node_type"] for n in nodes),
                         ["cloud", "cloud", "ethernet_switch"])
        clouds = [n for n in nodes if n["node_type"] == "cloud"]
        self.assertEqual({n["properties"]["ports_mapping"][0]["interface"] for n in clouds},
                         {"Adapter VMnet1", "Adapter VMnet2"})
        self.assertTrue(all(n["compute_id"] == "local" for n in nodes))

    def test_single_extra_nic_netplan_preserves_nat(self):
        text = netplan_text("00:50:56:11:22:33")
        self.assertIn("192.168.10.129/24", text)
        self.assertIn("gns3mgmt:", text)
        self.assertNotIn("gns3test:", text)
        self.assertNotIn("ens33:", text)
        self.assertNotIn("gateway4:", text)

    def test_once_collects_displays_and_sends_real_transition_through_mock_channel(self):
        self.profile()
        channel = Mock(key="tg", kind="telegram")
        channel.send.return_value = Delivery(True)
        out = io.StringIO()
        with patch.object(simple, "SSHCollector") as collector, \
             patch.object(simple, "Channel", return_value=channel), redirect_stdout(out):
            collector.return_value.collect.return_value = Sample({"cpu": 90., "ram": 40., "iface": "up"})
            result = simple.main(["--env-file", str(self.env), "--once"])
        self.assertEqual(result, 0)
        self.assertIn("90.0%", out.getvalue())
        self.assertIn("CẢNH BÁO", out.getvalue())
        channel.send.assert_called_once()
        self.assertIn("CPU", channel.send.call_args.args[0])
        self.assertNotIn("local-fixture-password", out.getvalue())
        self.assertNotIn("fake_fixture", out.getvalue())
        channel.close.assert_called_once()

    def test_test_message_failure_stays_queued_without_attempting_ssh(self):
        self.profile()
        channel = Mock(key="tg", kind="telegram")
        channel.send.return_value = Delivery(False, "HTTP 503")
        with patch.object(simple, "SSHCollector") as collector, \
             patch.object(simple, "Channel", return_value=channel), redirect_stdout(io.StringIO()):
            result = simple.main(["--env-file", str(self.env), "--test"])
        self.assertEqual(result, 1)
        collector.assert_not_called()
        store = simple.Store(self.root / "state.sqlite3")
        with store.connect() as db:
            row = db.execute("SELECT message,attempts FROM outbox").fetchone()
        self.assertIn("TIN THỬ", row[0])
        self.assertEqual(row[1], 1)

    def test_advanced_protocol_is_rejected_before_network_activity(self):
        self.profile(MONITOR_PROTOCOL="snmp", SNMP_PROFILE="linux-extend",
                     SNMP_VERSION="2c", SNMP_COMMUNITY="local-fixture")
        with patch.object(simple, "SSHCollector") as collector, self.assertLogs(simple.LOG, "ERROR"):
            self.assertEqual(simple.main(["--env-file", str(self.env), "--once"]), 2)
        collector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
