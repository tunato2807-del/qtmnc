import base64
import copy
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from lab.iperf_test import measure
from lab.web_demo import make_handler
from netwatch.config import ROOT, load_inventory
from netwatch.health import http_target, parse_linux_ping, ping_target, verdict
from netwatch.report import build_html
from netwatch.storage import Store
from netwatch.web import create_app
from tests.test_core import sample
from tools.build_gns3_preview import preview
from tools.make_lab import discover_vms


PARTIAL = "10 packets transmitted, 6 received, 40% packet loss, time 9012ms\nrtt min/avg/max/mdev = 0.100/1.250/3.000/0.900 ms\n"


class PingTests(unittest.TestCase):
    def test_partial_loss_retains_valid_rtt(self):
        result = parse_linux_ping(PARTIAL, 10)
        self.assertEqual(result["received"], 6)
        self.assertEqual(result["packet_loss_pct"], 40)
        self.assertEqual(result["rtt_avg_ms"], 1.25)

    def test_no_echo_is_not_zero_latency(self):
        result = parse_linux_ping("10 packets transmitted, 0 received, +10 errors, 100% packet loss", 10)
        self.assertEqual(result["packet_loss_pct"], 100)
        self.assertIsNone(result["rtt_avg_ms"])

    def test_bad_output_is_unknown(self):
        result = parse_linux_ping("permission denied", 10)
        self.assertIsNone(result["packet_loss_pct"])
        self.assertIsNone(result["received"])

    @patch("netwatch.health.platform.system", return_value="Linux")
    @patch("netwatch.health.subprocess.run")
    def test_exit_one_still_parses_partial_loss(self, run, system):
        run.return_value = Mock(returncode=1, stdout=PARTIAL)
        value = ping_target("127.0.0.1")
        self.assertEqual(value["packet_loss_pct"], 40)
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")

    @patch("netwatch.health.platform.system", return_value="Windows")
    @patch("netwatch.health.subprocess.run")
    def test_windows_uses_structured_dotnet_data(self, run, system):
        run.return_value = Mock(returncode=0, stdout=json.dumps({"sent": 10, "received": 8, "rtt_avg_ms": 0.5}))
        value = ping_target("127.0.0.1")
        self.assertEqual(value["packet_loss_pct"], 20)
        self.assertEqual(value["rtt_avg_ms"], .5)
        args = run.call_args.args[0]
        self.assertEqual(args[0], "powershell.exe")
        script = base64.b64decode(args[-1]).decode("utf-16le")
        self.assertIn("IPStatus]::Success", script)
        self.assertNotIn("shell", run.call_args.kwargs)

    @patch("netwatch.health.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_ping_tool_remains_unknown(self, run):
        value = ping_target("127.0.0.1")
        self.assertIsNone(value["packet_loss_pct"])
        self.assertIsNone(verdict(value, load_inventory()["checks"])[0])

    def test_target_cannot_inject_a_shell_command(self):
        with self.assertRaises(ValueError):
            ping_target("127.0.0.1; reboot")


class HTTPWireTests(unittest.TestCase):
    def probe(self, status=200, delay=0):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(status, delay))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with requests.Session() as client:
                # Chỉ loopback trong test; không dùng proxy ra Internet.
                client.trust_env = False
                return http_target(f"http://127.0.0.1:{server.server_port}/", timeout=1, session=client)
        finally:
            server.shutdown()
            thread.join(2)
            server.server_close()

    def test_200_real_loopback(self):
        result = self.probe()
        self.assertEqual(result["status_code"], 200)
        self.assertTrue(verdict(result, load_inventory()["checks"])[0])

    def test_503_real_loopback(self):
        result = self.probe(503)
        self.assertFalse(verdict(result, load_inventory()["checks"])[0])

    def test_slow_200_is_an_alert(self):
        result = self.probe(200, .15)
        checks = {**load_inventory()["checks"], "http_slow_seconds": .1}
        self.assertFalse(verdict(result, checks)[0])
        self.assertGreaterEqual(result["response_ms"], 100)

    def test_timeout_keeps_empty_response_values(self):
        session = Mock()
        session.get.side_effect = requests.Timeout("private test message")
        value = http_target("http://127.0.0.1/", session=session)
        self.assertIsNone(value["response_ms"])
        self.assertIsNone(value["status_code"])
        self.assertNotIn("private", value["error"])


class StoreHealthTests(unittest.TestCase):
    def test_health_dedup_persistence_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "metrics.sqlite3"
            s = Store(db)
            value = {"kind": "http", "status_code": 503, "response_ms": 20}
            for at in (100, 110):
                s.record_health("http-srv1-web", "Web SRV1", "srv1", value, False, "HTTP 503", ["telegram"], at)
            self.assertEqual(s.queue()["pending"], 1)
            s.close()
            s = Store(db)
            s.record_health("http-srv1-web", "Web SRV1", "srv1", {**value, "status_code": 200}, True, "HTTP 200", ["telegram"], 120)
            self.assertEqual(s.queue()["pending"], 2)
            self.assertEqual(s.health()[0]["state"], "OK")
            self.assertEqual(len(s.health_history("http-srv1-web")), 3)
            s.close()

    def test_ping_alert_does_not_mark_ssh_offline(self):
        cfg = load_inventory()
        s = Store(":memory:")
        s.record(cfg["devices"][0], cfg, sample())
        s.record_health("ping-r1", "ICMP R1", "r1", {"kind": "ping", "packet_loss_pct": 100, "rtt_avg_ms": None, "received": 0}, False, "ICMP không phản hồi")
        self.assertEqual(s.snapshot()["r1"]["kind"], "online")
        self.assertEqual(s.health()[0]["state"], "ALERT")
        s.close()

    def test_csv_has_interface_counters_and_empty_unknowns(self):
        cfg = load_inventory()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "system_metrics.csv"
            s = Store(":memory:", csv_path=output)
            s.record(cfg["devices"][0], cfg, sample(count=3000))
            s.record(cfg["devices"][0], cfg, kind="offline", error="test")
            s.close()
            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["rx_bytes"], "3000")
            self.assertEqual(rows[3]["cpu_pct"], "")
            self.assertEqual(rows[0]["sample_kind"], "lab")

    def test_demo_cannot_write_real_csv_or_queue(self):
        cfg = load_inventory()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "never.csv"
            s = Store(":memory:", demo=True, csv_path=output)
            s.record(cfg["devices"][0], cfg, sample(99), channels=["telegram"])
            s.record_health("ping-r1", "ICMP R1", "r1", {"kind": "ping"}, False, "test", ["telegram"])
            self.assertFalse(output.exists())
            self.assertEqual(s.queue()["pending"], 0)
            s.close()


class Buoi5ConfigurationTests(unittest.TestCase):
    def test_profile_matches_supplied_lab(self):
        value = load_inventory(ROOT / "inventory.buoi5.json")
        self.assertEqual(value["interval_seconds"], 5)
        self.assertEqual(value["thresholds"]["cpu_pct"], 85)
        self.assertEqual(value["thresholds"]["ram_pct"], 90)
        self.assertTrue(value["csv_enabled"])
        self.assertEqual(value["checks"]["ping_count"], 10)
        self.assertEqual(value["checks"]["http_slow_seconds"], 3)

    def test_http_target_must_match_configured_device(self):
        value = load_inventory()
        value["checks"]["http_services"][0]["url"] = "http://example.com/private"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                load_inventory(path)

    def test_preview_has_no_fake_vm_paths(self):
        import jsonschema
        value = preview()
        jsonschema.validate(value, json.loads((ROOT / "tests/fixtures/gns3-project-schema.json").read_text()))
        self.assertEqual(value["topology"]["nodes"], [])
        self.assertNotIn("vmx_path", json.dumps(value))
        self.assertIn("BẢN XEM SƠ ĐỒ", value["topology"]["drawings"][0]["svg"])
        jsonschema.validate(json.loads((ROOT / "lab/gns3/NETWATCH_XEM_NGAY.gns3").read_text()), json.loads((ROOT / "tests/fixtures/gns3-project-schema.json").read_text()))

    def test_autodiscovery_never_guesses_between_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / (name + ".vmx") for name in ("one", "two", "three")]
            for p, label in zip(paths, ("R1-LINUX", "SRV1-LINUX", "R1-LINUX")):
                p.write_text('displayName = "' + label + '"\n')
            self.assertEqual(discover_vms(paths[:2])["router"], paths[0])
            self.assertIsNone(discover_vms(paths)["router"])

    def test_open_existing_lab_never_overwrites_it(self):
        from tools import make_lab
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "NETWATCH_ROUTED.gns3"
            target.write_text('{"custom":"keep"}')
            with patch.object(sys, "argv", ["make_lab", "--output", folder, "--open"]), patch.object(make_lab, "open_project") as opened, patch.object(make_lab, "validate_vms") as validate:
                make_lab.main()
                opened.assert_called_once_with(target)
                validate.assert_not_called()
            self.assertEqual(target.read_text(), '{"custom":"keep"}')


class ReportAndWebTests(unittest.TestCase):
    def test_report_is_standalone_escaped_and_labels_demo(self):
        cfg = load_inventory()
        cfg["devices"][0]["name"] = "<script>alert(1)</script>"
        s = Store(":memory:", demo=True)
        s.record(cfg["devices"][0], cfg, sample())
        document = build_html(s, cfg)
        self.assertNotIn("<script>", document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("MÔ PHỎNG", document)
        self.assertIn("<svg", document)
        self.assertNotIn("cdn.jsdelivr", document)
        s.close()

    def test_health_endpoints_history_and_report_download(self):
        cfg = load_inventory()
        s = Store(":memory:")
        s.record_health("ping-r1", "ICMP R1", "r1", {"kind": "ping", "rtt_avg_ms": 2, "packet_loss_pct": 0}, True, "normal")
        client = create_app(cfg, s).test_client()
        response = client.get("/api/health")
        self.assertEqual(len(response.json["items"]), 3)
        first = next(v for v in response.json["items"] if v["id"] == "ping-r1")
        self.assertEqual(first["freshness"], "fresh")
        self.assertEqual(len(client.get("/api/health/history?check=ping-r1").json), 1)
        self.assertEqual(client.get("/api/health/history?check=private").status_code, 404)
        self.assertIn("attachment", client.get("/api/report").headers["Content-Disposition"])
        s.close()


class IperfTests(unittest.TestCase):
    @patch("lab.iperf_test.subprocess.run")
    def test_iperf_json_direction_and_rate_limit(self, run):
        run.return_value = Mock(returncode=0, stdout=json.dumps({"end": {"sum_sent": {"bits_per_second": 20000000}, "sum_received": {"bits_per_second": 19000000}}}))
        result = measure("10.10.10.10", reverse=True)
        self.assertEqual(result["received_mbps"], 19)
        self.assertIn("-R", run.call_args.args[0])
        self.assertIn("20M", run.call_args.args[0])

    @patch("lab.iperf_test.subprocess.run", side_effect=FileNotFoundError)
    def test_iperf_error_does_not_fabricate_zero_throughput(self, run):
        value = measure("10.10.10.10")
        self.assertIsNone(value["received_mbps"])
        self.assertTrue(value["status"].startswith("ERROR"))


if __name__ == "__main__":
    unittest.main()
