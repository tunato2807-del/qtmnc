"""Dashboard reads committed metrics; no extra SSH or notification requests."""
import csv
import http.client
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from http.server import ThreadingHTTPServer
from device_monitor.config import Config
from device_monitor.dashboard import csv_export,demo_snapshot,handler_factory,read_snapshot
from device_monitor.models import Sample
from device_monitor.storage import Store
from tools.create_gns3_project import course_project


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"state.sqlite3"
        self.store=Store(self.path)
        self.config=Config(host="192.168.10.129",ssh_user="fixture",iface="gns3test",
                           telegram_token="123:private_token",telegram_chat="1000",ssh_password="private_password")

    def observe(self,stamp,values=None,connection_error=None):
        with patch("device_monitor.storage.time.time",return_value=stamp):
            return self.store.observe(self.config,Sample(values or {}) if values is not None else None,
                                      ["tg"],connection_error=connection_error)

    def test_committed_samples_events_and_queue_without_credentials(self):
        self.observe(1000,{"cpu":90,"ram":40,"iface":"up"})
        result=read_snapshot(self.path,now=1001)
        self.assertEqual(result["device"]["values"]["cpu"],90)
        self.assertEqual(result["events"][0]["severity"],"ALERT")
        self.assertEqual(result["queues"][0]["pending"],1)
        self.assertEqual(result["queues"][0]["kind"],"telegram")
        self.assertEqual(result["summary"]["connection_success_percent"],100)
        self.assertTrue(result["fresh"])
        for secret in ("private_token","private_password","telegram_chat"):
            self.assertNotIn(secret,json.dumps(result))

    def test_connection_loss_is_a_gap_not_cpu_zero(self):
        self.observe(1000,{"cpu":30})
        self.observe(1005,connection_error="timeout")
        result=read_snapshot(self.path,now=1006)
        self.assertEqual(result["device"]["connection"],"DOWN")
        self.assertEqual(result["history"][-1]["values"],{})
        self.assertEqual(result["summary"]["connection_success_percent"],50)
        self.assertEqual(result["events"][0]["severity"],"ALERT")

    def test_no_new_samples_marks_existing_state_stale(self):
        self.observe(1000,{"cpu":30})
        self.assertFalse(read_snapshot(self.path,now=1200)["fresh"])

    def test_history_and_alert_state_roll_back_with_outbox(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.observe(self.config,Sample({"cpu":90}),[None])
        with self.store.connect() as db:
            for table in ("states","outbox","samples","events"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],0)

    def test_retention_does_not_delete_unsent_alert(self):
        self.observe(1000,{"cpu":90})
        self.observe(90000,{"cpu":20})
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM samples").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0],2)

    def test_missing_database_is_waiting_without_creating_file(self):
        path=Path(self.temp.name)/"not-created.sqlite3"
        self.assertIsNone(read_snapshot(path)["device"])
        self.assertFalse(path.exists())

    def test_legacy_database_waits_without_altering_schema(self):
        path=Path(self.temp.name)/"legacy.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE states(key TEXT PRIMARY KEY,value TEXT)")
        self.assertIsNone(read_snapshot(path)["device"])
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[("states",)])

    def test_device_filter_uses_parameterized_query(self):
        self.observe(1000,{"cpu":30})
        self.assertIsNone(read_snapshot(self.path,device="' OR 1=1 --",now=1001)["device"])

    def test_csv_keeps_missing_metrics_empty_and_neutralizes_formula(self):
        result=demo_snapshot(1000)
        result["device"]["host"]="=UNTRUSTED()"
        result["history"][1]["sources"]["temp"]="SSH / DEMO"
        rows=list(csv.reader(io.StringIO(csv_export(result).lstrip("\ufeff"))))
        self.assertEqual(rows[1][1],"'=UNTRUSTED()")
        self.assertEqual(rows[1][5],"")
        self.assertEqual(rows[1][-1],"True")
        self.assertEqual(rows[2][rows[0].index("temp_source")],"SSH / DEMO")

    def test_course_topology_separates_management_and_test_segments(self):
        value=course_project()
        nodes=value["topology"]["nodes"]
        self.assertEqual(len(nodes),7)
        self.assertEqual(sum(n["node_type"]=="vpcs" for n in nodes),2)
        clouds=[n for n in nodes if n["node_type"]=="cloud"]
        self.assertEqual(len(clouds),3)
        win=next(n for n in clouds if n["name"]=="Cloud-WINDOWS")
        self.assertEqual(win["properties"]["ports_mapping"][0]["type"],"udp")
        self.assertEqual(win["properties"]["ports_mapping"][0]["lport"],30010)
        for n in nodes:
            if n["node_type"]=="ethernet_switch":
                expected=10 if n["name"]=="SW-MANAGEMENT" else 30
                self.assertTrue(all(p["vlan"]==expected for p in n["properties"]["ports_mapping"]))


class HTTPDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),handler_factory(Path("/nonexistent"),demo=True))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(3)

    def get(self,path,headers=None,method="GET"):
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        try:
            connection.request(method,path,headers=headers or {})
            response=connection.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:
            connection.close()

    def test_real_http_api_is_labelled_demo(self):
        code,headers,body=self.get("/api/snapshot")
        self.assertEqual(code,200)
        self.assertTrue(json.loads(body)["demo"])
        filtered=json.loads(self.get("/api/snapshot?minutes=15")[2])
        self.assertEqual(len(filtered["history"]),61)
        self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])

    def test_rebinding_host_and_cross_origin_are_rejected(self):
        self.assertEqual(self.get("/api/snapshot",{"Host":"attacker.example"})[0],403)
        self.assertEqual(self.get("/api/snapshot",{"Origin":"https://attacker.example"})[0],403)

    def test_invalid_window_and_post_do_not_mutate(self):
        self.assertEqual(self.get("/api/snapshot?minutes=-1")[0],400)
        self.assertEqual(self.get("/api/snapshot?minutes=nan")[0],400)
        self.assertEqual(self.get("/api/snapshot",method="POST")[0],405)

    def test_no_arbitrary_files_or_traversal(self):
        for path in ("/.env.simple","/../device_monitor/config.py","/web/app.js"):
            self.assertEqual(self.get(path)[0],404)

    def test_html_and_csv_are_served_without_external_dependencies(self):
        self.assertEqual(self.get("/")[0],200)
        code,headers,body=self.get("/api/export.csv")
        self.assertEqual(code,200)
        self.assertIn("qtmnc-demo.csv",headers["Content-Disposition"])
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))


if __name__=="__main__":
    unittest.main()
