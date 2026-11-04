import copy
import importlib.util
import json
import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from netwatch.config import ROOT, load_inventory, validate_sample
from netwatch.storage import Store, transition
from netwatch.notifications import configured_channels, send
from netwatch.web import create_app
from lab.probe import cpu_counters, cpu_percent, ram_percent, read_interfaces, temperature
from lab.provision import plan
from tools.make_lab import project, validate_vms


def sample(cpu=40, ram=35, count=1000, state="up"):
    return {"schema": 1, "cpu_pct": cpu, "ram_pct": ram, "temperature_c": None,
            "interfaces": {"mgmt0": {"state": state, "rx_bytes": count, "tx_bytes": count, "rx_errors": 0, "tx_errors": 0},
                           "srv0": {"state": "up"}, "users0": {"state": "up"}}}


class ProbeTests(unittest.TestCase):
    def test_guest_is_not_double_counted(self):
        self.assertEqual(cpu_counters("cpu 100 0 50 800 20 5 15 10 40 0\n"), (1000, 820))

    def test_cpu_interval_includes_iowait_in_idle(self):
        self.assertEqual(cpu_percent((1000, 800), (1200, 950)), 25)
        self.assertIsNone(cpu_percent((1000, 800), (1000, 800)))
        self.assertIsNone(cpu_percent((1000, 800), (900, 700)))

    def test_ram_uses_available_not_free(self):
        self.assertEqual(ram_percent("MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 600 kB\n"), 40)
        self.assertIsNone(ram_percent("MemTotal: 0 kB\n"))

    def test_sensor_and_missing_interface_are_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(temperature(root))
            p = root / "thermal_zone0"
            p.mkdir()
            (p / "temp").write_text("44000")
            self.assertEqual(temperature(root), 44)
            result = read_interfaces(["absent"], root)
            self.assertEqual(result["absent"]["state"], "unknown")
            self.assertIsNone(result["absent"]["rx_bytes"])


class ConfigTests(unittest.TestCase):
    def test_inventory(self):
        cfg = load_inventory()
        self.assertEqual([d["host"] for d in cfg["devices"]], ["192.168.73.10", "10.10.10.10"])

    def test_nonfinite_and_injection_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, 101, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_sample(sample(cpu=value), ["mgmt0"])
        cfg = load_inventory()
        cfg["devices"][0]["interfaces"] = ["srv0; reboot"]
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "inventory.json"
            p.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                load_inventory(p)
            cfg["devices"][0]["interfaces"] = "mgmt0"
            p.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                load_inventory(p)

    def test_missing_metric_remains_none(self):
        value = validate_sample({"schema": 1, "interfaces": {}}, ["mgmt0"])
        self.assertIsNone(value["cpu_pct"])
        self.assertEqual(value["interfaces"]["mgmt0"]["state"], "unknown")


class EngineStoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_inventory()
        self.device = self.cfg["devices"][0]
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def record(self, value=None, **kwargs):
        return self.store.record(self.device, self.cfg, value, **kwargs)

    def test_threshold_hysteresis_unknown_and_recovery(self):
        state = transition(76, {}, 75)
        self.assertEqual(state["state"], "ALERT")
        state = transition(None, state, 75)
        self.assertEqual(state, {"state": "UNKNOWN", "last": "ALERT"})
        state = transition(72, state, 75)
        self.assertEqual(state["state"], "ALERT")
        self.assertEqual(transition(70, state, 75)["state"], "OK")

    def test_deduplicate_and_recovery_message(self):
        self.record(sample(90), channels=["telegram"], at=100)
        self.record(sample(90), channels=["telegram"], at=115)
        self.assertEqual(len(self.store.events()), 1)
        self.record(kind="unknown", error="Probe lỗi", channels=["telegram"], at=130)
        self.record(sample(90), channels=["telegram"], at=145)
        cpu_event = next(e for e in self.store.events() if e["metric"] == "cpu_pct")
        self.assertIn("VẪN CẢNH BÁO", cpu_event["message"])
        self.record(sample(69), channels=["telegram"], at=160)
        self.assertEqual(self.store.events()[0]["state"], "OK")
        self.assertEqual(self.store.queue()["pending"], 4)  # Gộp thay đổi theo thiết bị/chu kỳ.

    def test_connection_loss_is_one_event(self):
        self.record(sample(), at=100)
        self.record(kind="offline", error="Mất đường", at=115)
        self.record(kind="offline", error="Mất đường", at=130)
        events = self.store.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metric"], "connection")
        self.assertEqual(self.store.snapshot()["r1"]["states"]["cpu_pct"], "UNKNOWN")
        self.record(sample(), at=145)
        self.assertEqual(self.store.events()[0]["state"], "OK")

    def test_rates_and_counter_reset(self):
        self.record(sample(count=1000), at=100)
        value = self.record(sample(count=1001000), at=110)
        self.assertEqual(value["interfaces"]["mgmt0"]["rx_mbps"], .8)
        value = self.record(sample(count=100), at=120)
        self.assertIsNone(value["interfaces"]["mgmt0"]["rx_mbps"])

    def test_state_and_retry_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "new.sqlite3"
            store = Store(path)
            store.record(self.device, self.cfg, sample(90), channels=["telegram"], at=100)
            item = store.due(100)
            store.delivered(item, "ConnectionError", now=100)
            self.assertIsNone(store.due(101))
            store.close()
            store = Store(path)
            self.assertEqual(store.due(102)["attempts"], 1)
            store.record(self.device, self.cfg, sample(90), channels=["telegram"], at=115)
            self.assertEqual(len(store.events()), 1)
            store.delivered(store.due(115), now=115)
            self.assertEqual(store.queue()["pending"], 0)
            store.close()

    def test_retry_after_and_demo_no_notifications(self):
        self.record(sample(90), channels=["telegram"], at=100)
        item = self.store.due(100)
        self.store.delivered(item, "429", 60, now=100)
        self.assertIsNone(self.store.due(159))
        self.assertIsNotNone(self.store.due(160))
        demo = Store(":memory:", demo=True)
        demo.record(self.device, self.cfg, sample(90), channels=["telegram"])
        self.assertEqual(demo.queue()["pending"], 0)
        demo.close()

    def test_retention_and_disabled_temperature(self):
        self.record(sample(90), at=100)
        self.record(sample(40), at=86501)
        self.assertEqual(len(self.store.history("r1")), 1)
        self.assertFalse(any(e["metric"] == "temperature_c" for e in self.store.events()))


class NotificationTests(unittest.TestCase):
    @patch.dict(os.environ, {"TELEGRAM_TOKEN": "local-test", "TELEGRAM_CHAT_ID": "123", "SLACK_WEBHOOK": ""}, clear=True)
    def test_telegram_response_and_rate_limit(self):
        session = Mock()
        session.post.return_value = Mock(status_code=200, json=lambda: {"ok": True})
        self.assertEqual(send({"channel": "telegram", "message": "test"}, session), (None, None))
        self.assertFalse(session.post.call_args.kwargs["allow_redirects"])
        session.post.return_value = Mock(status_code=429, json=lambda: {"parameters": {"retry_after": 47}})
        self.assertEqual(send({"channel": "telegram", "message": "test"}, session)[1], 47)

    @patch.dict(os.environ, {"SLACK_WEBHOOK": "https://hooks.slack.com/services/local-test"}, clear=True)
    def test_slack_success_and_retry(self):
        session = Mock()
        session.post.return_value = Mock(status_code=200, text="ok")
        self.assertEqual(send({"channel": "slack", "message": "test"}, session), (None, None))
        session.post.return_value = Mock(status_code=429, headers={"Retry-After": "31"})
        self.assertEqual(send({"channel": "slack", "message": "test"}, session)[1], 31)

    @patch.dict(os.environ, {"SLACK_WEBHOOK": "http://127.0.0.1/private"}, clear=True)
    def test_arbitrary_webhook_rejected(self):
        with self.assertRaises(ValueError):
            configured_channels()


class WebTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_inventory()
        self.store = Store(":memory:")
        self.app = create_app(self.cfg, self.store)
        self.client = self.app.test_client()

    def tearDown(self):
        self.store.close()

    def test_routes_and_local_security(self):
        for route in ("/", "/api/state", "/api/history", "/api/events", "/static/app.js"):
            with self.client.get(route) as response:
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/api/state").status_code, 405)
        self.assertEqual(self.client.get("/api/state", headers={"Host": "hostile.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/state", headers={"Origin": "https://hostile.example"}).status_code, 403)
        response = self.client.get("/api/state")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertNotIn("credential_prefix", response.text)
        self.assertEqual(self.client.get("/api/history?device=../../private").status_code, 404)

    def test_stale_and_missing_data_are_distinct(self):
        self.assertEqual(self.client.get("/api/state").json["devices"][0]["freshness"], "waiting")
        self.store.record(self.cfg["devices"][0], self.cfg, sample(), at=time.time() - 500)
        self.assertEqual(self.client.get("/api/state").json["devices"][0]["freshness"], "stale")

    def test_csv_labels_and_values(self):
        self.store.record(self.cfg["devices"][0], self.cfg, sample(82))
        response = self.client.get("/api/export?device=r1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("sample_kind", response.text)
        self.assertIn(",lab,online,82,", response.text)


class LabTests(unittest.TestCase):
    def test_gns3_schema_and_no_bypass_link(self):
        import jsonschema
        p = project(Path("C:/VMs/R1/R1.vmx"), Path("C:/VMs/SRV1/SRV1.vmx"))
        fixture = ROOT / "tests/fixtures"
        jsonschema.validate(p, json.loads((fixture / "gns3-project-schema.json").read_text()))
        nodes = p["topology"]["nodes"]
        self.assertEqual(len(nodes), 6)
        self.assertNotIn("cloud", [n["node_type"] for n in nodes])
        r1 = next(n for n in nodes if n["name"] == "R1-LINUX")
        self.assertFalse(r1["properties"]["use_any_adapter"])
        for n in nodes:
            if n["node_type"] == "vmware":
                jsonschema.validate(n["properties"], json.loads((fixture / "gns3-vmware-properties.json").read_text()))
        for link in p["topology"]["links"]:
            for endpoint in link["nodes"]:
                self.assertFalse(endpoint["node_id"] == r1["node_id"] and endpoint["adapter_number"] == 0)

    def test_vmx_validation_distinct_and_nat_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            r, s = Path(folder) / "R1.vmx", Path(folder) / "SRV1.vmx"
            r.write_text('ethernet0.connectionType = "nat"\nethernet1.present = "TRUE"\nethernet1.connectionType = "custom"\nethernet2.present = "TRUE"\nethernet2.connectionType = "custom"\n')
            s.write_text('ethernet0.present = "TRUE"\nethernet0.connectionType = "custom"\n')
            self.assertEqual(validate_vms(r, s), (r, s))
            with self.assertRaises(ValueError):
                validate_vms(r, r)
            s.write_text('ethernet0.present = "TRUE"\nethernet0.connectionType = "custom"\nethernet0.vnet = "VMnet2"\n')
            with self.assertRaises(ValueError):
                validate_vms(r, s)
            s.write_text('ethernet0.present = "TRUE"\nethernet0.connectionType = "nat"\n')
            with self.assertRaises(ValueError):
                validate_vms(r, s)

    def test_linux_plan_roles_mac_renaming_and_narrow_nft_table(self):
        files = plan("router", {"mgmt0": "00:11:22:33:44:01", "srv0": "00:11:22:33:44:02", "users0": "00:11:22:33:44:03"})
        cfg = json.loads(files["/etc/netplan/90-netwatch.yaml"])
        ports = cfg["network"]["ethernets"]
        self.assertEqual(ports["mgmt0"]["routes"][0]["via"], "192.168.73.2")
        self.assertNotIn("routes", ports["srv0"])
        self.assertEqual(ports["srv0"]["set-name"], "srv0")
        self.assertNotIn("flush ruleset", files["/etc/netwatch/router.nft"])
        server = plan("server", {"lan0": "00:11:22:33:44:04"})
        self.assertEqual(json.loads(server["/etc/netplan/90-netwatch.yaml"])["network"]["ethernets"]["lan0"]["addresses"], ["10.10.10.10/24"])
        self.assertNotIn("/etc/netwatch/router.nft", server)


if __name__ == "__main__":
    unittest.main()
