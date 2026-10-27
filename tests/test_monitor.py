"""Regression tests: no real devices or messaging endpoints are contacted."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import monitor_ssh as m


def config(**kwargs):
    return m.Config(host="device.test", ssh_user="tester", **kwargs)


class ParsingTests(unittest.TestCase):
    def test_cpu_interval_includes_irq_steal_and_excludes_guest_double_count(self):
        raw = "cpu  100 0 100 700 50 10 20 20 100 0\ncpu0 1 2 3 4\ncpu  120 0 110 750 60 15 23 22 120 0\n"
        self.assertAlmostEqual(m.cpu_percent(raw), 40)

    def test_cpu_reset_and_empty_samples_rejected(self):
        for raw in ("", "cpu 1 2 3 4\ncpu 0 1 2 3\n", "cpu 1 2 3 4\ncpu 1 2 3 4\n"):
            with self.subTest(raw=raw), self.assertRaises(m.DataError):
                m.cpu_percent(raw)

    def test_ram_uses_available_instead_of_cached_as_used(self):
        self.assertEqual(m.ram_percent("MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 600 kB\n"), 40)

    def test_ram_supported_fallback(self):
        self.assertEqual(m.ram_percent("MemTotal: 1000 kB\nMemFree: 100 kB\nBuffers: 100 kB\nCached: 300 kB\nSReclaimable: 100 kB\nShmem: 100 kB\n"), 50)

    def test_invalid_numbers_rejected(self):
        for raw in ("nan", "inf", None, "missing"):
            with self.subTest(raw=raw), self.assertRaises(m.DataError):
                m.number(raw, 0, 100)


class ConfigTests(unittest.TestCase):
    def env(self, **extra):
        return {"MONITOR_HOST": "device.test", "SSH_USER": "tester",
                "TELEGRAM_TOKEN": "123:fake_token", "TELEGRAM_CHAT_ID": "1234", **extra}

    def test_no_hardcoded_secret_or_device(self):
        with self.assertRaises(m.ConfigError):
            m.Config.from_env({})
        c = m.Config.from_env(self.env())
        self.assertNotIn("fake_token", repr(c))

    def test_bad_values_and_partial_channel_rejected(self):
        cases = [
            {"MONITOR_INTERVAL": "nan"}, {"MONITOR_INTERVAL": "0"}, {"SSH_PORT": "22.1"},
            {"MONITOR_IFACE": "eth0;id"}, {"MONITOR_TEMP_PATH": "/sys/../etc/passwd"},
            {"TELEGRAM_CHAT_ID": ""}, {"MONITOR_TEMP_ENABLED": "maybe"},
            {"SLACK_WEBHOOK_URL": "http://hooks.slack.com/services/fake"},
            {"SLACK_WEBHOOK_URL": "https://evil.test/services/fake"},
            {"SLACK_WEBHOOK_URL": "https://hooks.slack.com@evil.test/services/fake"},
        ]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(m.ConfigError):
                m.Config.from_env(self.env(**extra))

    def test_snmp_requires_real_oid_configuration(self):
        with self.assertRaises(m.ConfigError):
            m.Config.from_env(self.env(MONITOR_PROTOCOL="snmp", SNMP_VERSION="2c", SNMP_COMMUNITY="test"))

    def test_snmp_v3_and_ram_ratio_configuration(self):
        c = m.Config.from_env(self.env(MONITOR_PROTOCOL="snmp", SNMP_USER="test",
            SNMP_AUTH_KEY="fake_auth_key", SNMP_PRIV_KEY="fake_priv_key",
            SNMP_CPU_OID="1.3.6.1.4.1.999.1.0", SNMP_IFACE_OID="1.3.6.1.2.1.2.2.1.8.2",
            SNMP_RAM_USED_OID="1.3.6.1.4.1.999.2.0", SNMP_RAM_TOTAL_OID="1.3.6.1.4.1.999.3.0"))
        self.assertEqual(c.snmp_version, "3")


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.store = m.Store(self.path)
        self.c = config()

    def events(self, channel=None):
        with self.store.connect() as db:
            if channel:
                return db.execute("SELECT id,message,attempts,next_attempt FROM outbox WHERE channel=? ORDER BY id", (channel,)).fetchall()
            return db.execute("SELECT id,message,attempts,next_attempt FROM outbox ORDER BY id").fetchall()

    def observe(self, **values):
        return self.store.observe(self.c, m.Sample(values), ["tg", "slack"])

    def test_normal_start_does_not_send(self):
        self.observe(cpu=20, ram=30, temp=40, iface="up")
        self.assertEqual(self.events(), [])

    def test_initial_alert_then_no_duplicate_even_after_restart(self):
        self.observe(cpu=90)
        self.store = m.Store(self.path)
        self.observe(cpu=92)
        self.assertEqual(len(self.events()), 2)

    def test_missing_temperature_never_becomes_false_recovery(self):
        self.observe(temp=80)
        messages = self.observe(temp=None)
        self.assertIn("KHÔNG XÁC ĐỊNH", messages[0])
        self.assertNotIn("bình thường", messages[0])
        self.assertEqual(self.observe(temp=None), [])

    def test_hysteresis_is_preserved_across_unknown(self):
        self.observe(cpu=90)
        self.observe(cpu=None)
        self.observe(cpu=72)
        with self.store.connect() as db:
            state = json.loads(db.execute("SELECT value FROM states").fetchone()[0])
        self.assertEqual(state["cpu"]["status"], "ALERT")
        self.assertIn("bình thường", self.observe(cpu=70)[0])

    def test_unknown_interface_not_reported_as_down(self):
        message = self.observe(iface="unknown")[0]
        self.assertIn("KHÔNG XÁC ĐỊNH", message)
        self.assertNotIn("CẢNH BÁO", message)

    def test_connection_loss_and_recovery_only_on_transition(self):
        self.store.observe(self.c, None, ["tg"], connection_error="timeout")
        self.store.observe(self.c, None, ["tg"], connection_error="timeout")
        self.assertEqual(len(self.events()), 1)
        self.observe(cpu=20)
        self.assertEqual(len(self.events()), 3)
        self.assertIn("khôi phục", self.events()[1][1])

    def test_failed_notification_is_retried_from_disk_without_new_transition(self):
        self.observe(cpu=90)
        tg, slack = Mock(), Mock()
        tg.key, tg.kind = "tg", "telegram"
        slack.key, slack.kind = "slack", "slack"
        tg.send.return_value = m.Delivery(False, "HTTP 503")
        slack.send.return_value = m.Delivery(True)
        with self.assertLogs(m.LOG, level="WARNING"):
            self.assertEqual(m.Dispatcher(self.store, [tg, slack]).tick(), 1)
        self.assertEqual(len(self.events()), 1)
        event = self.events()[0]
        self.assertEqual(event[2], 1)
        self.assertGreater(event[3], 0)
        self.store = m.Store(self.path)
        self.observe(cpu=95)
        self.assertEqual(len(self.events()), 1)
        tg.send.return_value = m.Delivery(True)
        with patch.object(m.time, "time", return_value=event[3] + 1):
            m.Dispatcher(self.store, [tg]).tick()
        self.assertEqual(self.events(), [])
        self.assertEqual(tg.send.call_count, 2)
        self.assertEqual(slack.send.call_count, 1)

    def test_recovery_is_queued_behind_failed_alert(self):
        self.observe(cpu=90)
        first = self.events("tg")[0]
        self.store.failed(first[0], 0)
        self.observe(cpu=20)
        self.assertIsNone(self.store.due("tg", 0))
        self.assertEqual(self.store.due("tg", 10**12)[0], first[0])
        self.store.delivered(first[0])
        self.assertIn("bình thường", self.store.due("tg", 10**12)[1])

    def test_rate_limit_backoff_honors_server(self):
        self.observe(cpu=90)
        event = self.events("tg")[0]
        with patch.object(m.time, "time", return_value=100):
            self.store.failed(event[0], 0, retry_after=120)
        self.assertIsNone(self.store.due("tg", 219))
        self.assertIsNotNone(self.store.due("tg", 220))

    def test_state_and_outbox_rollback_together(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.observe(self.c, m.Sample({"cpu": 90}), [None])
        self.assertEqual(self.events(), [])
        self.observe(cpu=90)
        self.assertEqual(len(self.events()), 2)


class HTTPTests(unittest.TestCase):
    def channel(self, kind="telegram", status=200, data=None, text="ok", headers=None):
        response = Mock(status_code=status, text=text, headers=headers or {})
        response.json.return_value = {"ok": True} if data is None else data
        session = Mock()
        session.post.return_value = response
        return m.Channel(kind, "123:fake_token" if kind == "telegram" else "https://hooks.slack.com/services/fake", "123", session), session

    def test_plain_text_and_safe_http_options(self):
        channel, session = self.channel()
        self.assertTrue(channel.send("*a_b_c*").ok)
        kwargs = session.post.call_args.kwargs
        self.assertNotIn("parse_mode", kwargs["json"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (5, 10))

    def test_telegram_requires_api_confirmation(self):
        for data in ({"ok": False}, [], {"result": {}}):
            channel, _ = self.channel(data=data)
            self.assertFalse(channel.send("test").ok)

    def test_retryable_post_failure_is_returned_to_outbox(self):
        channel, session = self.channel(status=503)
        result = channel.send("test")
        self.assertFalse(result.ok)
        self.assertEqual(session.post.call_count, 1)

    def test_telegram_rate_limit(self):
        channel, _ = self.channel(status=429, data={"parameters": {"retry_after": 60}})
        self.assertEqual(channel.send("test").retry_after, 60)

    def test_slack_rate_limit_and_acknowledgement(self):
        channel, _ = self.channel("slack", status=429, headers={"Retry-After": "90"})
        self.assertEqual(channel.send("test").retry_after, 90)
        channel, session = self.channel("slack")
        self.assertTrue(channel.send("test").ok)
        self.assertFalse(session.post.call_args.kwargs["json"]["mrkdwn"])
        channel, _ = self.channel("slack", text="invalid_payload")
        self.assertFalse(channel.send("test").ok)

    def test_url_secret_not_exposed_in_error(self):
        channel, session = self.channel()
        session.post.side_effect = RuntimeError("https://example.test/secret")
        result = channel.send("test")
        self.assertNotIn("secret", result.reason)
        self.assertIn("RuntimeError", result.reason)

    def test_rotating_credentials_preserves_queue_identity(self):
        old = m.Channel("telegram", "123:old_fake", "1234", Mock())
        new = m.Channel("telegram", "123:new_fake", "1234", Mock())
        self.assertEqual(old.key, new.key)
        old = m.Channel("slack", "https://hooks.slack.com/services/old_fake", session=Mock())
        new = m.Channel("slack", "https://hooks.slack.com/services/new_fake", session=Mock())
        self.assertEqual(old.key, new.key)


class SSHTests(unittest.TestCase):
    def collector(self, cpu="bad CPU", iface="unknown", temp="", failure=None):
        c = config()
        obj = m.SSHCollector.__new__(m.SSHCollector)
        obj.c, obj.known_hosts = c, Path("/fake/known_hosts")
        obj._ssh = None
        client = Mock()
        client.get_transport.return_value.is_active.return_value = True
        if failure:
            client.connect.side_effect = failure

        def output(command, **kwargs):
            blocks = {"cpu": cpu, "ram": "MemTotal: 1000 kB\nMemAvailable: 600 kB\n",
                      "iface": iface, "temp": temp}
            value = "\n".join(f"__QTMNC_BEGIN_{metric}__\n{blocks[metric]}\n__QTMNC_END_{metric}__:0"
                              for metric in obj._linux_probes())
            stdout, stderr = Mock(), Mock()
            stdout.read.return_value = value.encode()
            stderr.read.return_value = b""
            stdout.channel.recv_exit_status.return_value = 0
            return None, stdout, stderr
        client.exec_command.side_effect = output
        obj.lib = SimpleNamespace(SSHClient=Mock(return_value=client), RejectPolicy=lambda: "reject")
        self.addCleanup(obj.close)
        return obj, client

    def test_parse_failure_does_not_mark_ssh_disconnected(self):
        obj, client = self.collector()
        sample = obj.collect()
        self.assertIsNone(sample.values["cpu"])
        self.assertIn("cpu", sample.errors)
        self.assertEqual(sample.values["ram"], 40)
        self.assertIsNone(sample.values["temp"])
        client.close.assert_not_called()
        obj.close()
        client.close.assert_called_once()
        client.set_missing_host_key_policy.assert_called_once_with("reject")

    def test_repeated_polls_reuse_authentication_and_one_exec_each(self):
        obj, client = self.collector()
        first, second = obj.collect(), obj.collect()
        self.assertEqual(first.values, second.values)
        obj.lib.SSHClient.assert_called_once()
        client.connect.assert_called_once()
        client.get_transport.return_value.set_keepalive.assert_called_once_with(15)
        self.assertEqual(client.exec_command.call_count, 2)
        client.close.assert_not_called()

    def test_disconnected_cached_client_is_replaced(self):
        obj, old = self.collector()
        _, new = self.collector()
        obj.lib.SSHClient.side_effect = [old, new]
        obj.collect()
        old.get_transport.return_value.is_active.return_value = False
        sample = obj.collect()
        self.assertEqual(sample.values["ram"], 40)
        old.close.assert_called_once()
        new.connect.assert_called_once()

    def test_timeout_discards_client_then_next_poll_reconnects(self):
        obj, client = self.collector()
        output = client.exec_command.side_effect
        client.exec_command.side_effect = TimeoutError("secret must stay hidden")
        failed = obj.collect()
        self.assertTrue(all(v is None for v in failed.values.values()))
        self.assertNotIn("secret", " ".join(failed.errors.values()))
        client.close.assert_called_once()
        client.exec_command.side_effect = output
        self.assertEqual(obj.collect().values["ram"], 40)
        self.assertEqual(client.connect.call_count, 2)

    def test_batch_file_failure_does_not_hide_other_metrics(self):
        obj, client = self.collector(iface="up")
        original = client.exec_command.side_effect
        def output(*args, **kwargs):
            stdin, stdout, stderr = original(*args, **kwargs)
            stdout.read.return_value = stdout.read.return_value.replace(b"__QTMNC_END_ram__:0", b"__QTMNC_END_ram__:1")
            return stdin, stdout, stderr
        client.exec_command.side_effect = output
        sample = obj.collect()
        self.assertIsNone(sample.values["ram"])
        self.assertEqual(sample.values["iface"], "up")
        self.assertIn("ram", sample.errors)
        self.assertNotIn("iface", sample.errors)

    def test_missing_metric_marker_is_unknown_not_zero(self):
        obj, client = self.collector(iface="up")
        original = client.exec_command.side_effect
        def output(*args, **kwargs):
            stdin, stdout, stderr = original(*args, **kwargs)
            stdout.read.return_value = stdout.read.return_value.replace(b"__QTMNC_BEGIN_ram__", b"missing")
            return stdin, stdout, stderr
        client.exec_command.side_effect = output
        sample = obj.collect()
        self.assertIsNone(sample.values["ram"])
        self.assertEqual(sample.values["iface"], "up")

    def test_close_is_idempotent_and_closes_channel_streams(self):
        obj, client = self.collector()
        original = client.exec_command.side_effect
        streams = original("ignored")
        client.exec_command.side_effect = None
        client.exec_command.return_value = streams
        obj.collect()
        streams[1].close.assert_called_once()
        streams[2].close.assert_called_once()
        streams[1].channel.close.assert_called_once()
        obj.close()
        obj.close()
        client.close.assert_called_once()

    def test_connection_failure_closes_client_and_redacts_exception(self):
        obj, client = self.collector(failure=RuntimeError("sensitive_password"))
        with self.assertRaises(m.DeviceUnavailable) as caught:
            obj.collect()
        self.assertNotIn("sensitive_password", str(caught.exception))
        client.close.assert_called_once()

    def test_channel_error_is_metric_error_when_transport_still_active(self):
        obj, client = self.collector()
        client.exec_command.side_effect = TimeoutError()
        sample = obj.collect()
        self.assertEqual(set(sample.errors), {"cpu", "ram", "temp", "iface"})
        client.close.assert_called_once()

    def test_dead_transport_is_connection_failure(self):
        obj, client = self.collector()
        client.exec_command.side_effect = EOFError()
        client.get_transport.return_value.is_active.return_value = False
        with self.assertRaises(m.DeviceUnavailable):
            obj.collect()
        client.close.assert_called_once()

    def test_remote_command_failure_is_not_zero(self):
        obj, client = self.collector()
        stdout, stderr = Mock(), Mock()
        stdout.read.return_value = b""
        stderr.read.return_value = b"permission denied"
        stdout.channel.recv_exit_status.return_value = 1
        client.exec_command.side_effect = None
        client.exec_command.return_value = (None, stdout, stderr)
        sample = obj.collect()
        self.assertTrue(all(value is None for value in sample.values.values()))


class SNMPTests(unittest.TestCase):
    def collector(self, raw):
        obj = m.SNMPCollector.__new__(m.SNMPCollector)
        obj.c = config(protocol="snmp", temp_scale=0.1)
        obj._fetch = AsyncMock(return_value=raw)
        return obj

    def test_ram_ratio_temperature_and_interface(self):
        sample = self.collector({"cpu": "20", "ram_used": "3", "ram_total": "10",
                                 "temp": "450", "iface": "7"}).collect()
        self.assertEqual(sample.errors, {})
        self.assertEqual(sample.values, {"cpu": 20., "ram": 30., "temp": 45., "iface": "lowerlayerdown"})

    def test_missing_oid_and_zero_ram_total_are_unknown(self):
        sample = self.collector({"cpu": "No Such Instance", "ram_used": "3",
                                 "ram_total": "0", "iface": "4"}).collect()
        self.assertIsNone(sample.values["cpu"])
        self.assertIsNone(sample.values["ram"])
        self.assertIsNone(sample.values["temp"])
        self.assertEqual(sample.values["iface"], "unknown")

    def test_snmp_timeout_not_fabricated_metrics(self):
        obj = self.collector({})
        obj._fetch.side_effect = m.DeviceUnavailable("timeout")
        with self.assertRaises(m.DeviceUnavailable):
            obj.collect()

    def test_query_error_is_unknown_data_not_connection_loss(self):
        obj = self.collector({})
        obj._fetch.side_effect = m.DataError("Agent rejected OID")
        sample = obj.collect()
        self.assertEqual(set(sample.errors), {"cpu", "ram", "temp", "iface"})
        self.assertTrue(all(v is None for v in sample.values.values()))

    def test_disabled_temperature_is_not_reported_as_missing(self):
        obj = self.collector({"cpu": "20", "ram": "30", "iface": "1"})
        obj.c.temp_enabled = False
        sample = obj.collect()
        self.assertNotIn("temp", sample.values)
        self.assertEqual(sample.errors, {})


class CLITests(unittest.TestCase):
    def run_once(self, sample, delivery):
        with tempfile.TemporaryDirectory() as directory:
            env = {"MONITOR_HOST": "device.test", "SSH_USER": "fixture",
                   "TELEGRAM_TOKEN": "123:fake_token", "TELEGRAM_CHAT_ID": "1234",
                   "MONITOR_STATE_FILE": str(Path(directory) / "state.sqlite3")}
            channel = Mock(key="tg", kind="telegram")
            channel.send.return_value = delivery
            with patch.dict(os.environ, env, clear=True), patch.object(m, "SSHCollector") as collector, patch.object(m, "Channel", return_value=channel):
                collector.return_value.collect.return_value = sample
                result = m.main(["--once", "--display", "log"])
            return result, channel

    def test_once_success_requires_acknowledgement(self):
        result, channel = self.run_once(m.Sample({"cpu": 90}), m.Delivery(True))
        self.assertEqual(result, 0)
        channel.send.assert_called_once()
        channel.close.assert_called_once()

    def test_once_failure_keeps_backlog_and_nonzero_status(self):
        with self.assertLogs(m.LOG, level="WARNING"):
            result, _ = self.run_once(m.Sample({"cpu": 90}), m.Delivery(False, "HTTP 503"))
        self.assertEqual(result, 1)

    def test_config_check_does_not_connect_or_send(self):
        env = {"MONITOR_HOST": "device.test", "SSH_USER": "fixture",
               "TELEGRAM_TOKEN": "123:fake_token", "TELEGRAM_CHAT_ID": "1234"}
        with patch.dict(os.environ, env, clear=True), patch.object(m, "SSHCollector") as collector, patch.object(m, "Channel") as channel:
            self.assertEqual(m.main(["--check-config"]), 0)
            collector.return_value.collect.assert_not_called()
            channel.return_value.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
