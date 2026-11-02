"""Read-only localhost dashboard; reads committed SQLite, never polls a device."""
from __future__ import annotations

import argparse
from contextlib import closing
import csv
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web"


def empty_snapshot(now):
    return {"demo": False, "server_time": now, "device": None, "devices": [],
            "history": [], "events": [], "queues": [], "summary": {}, "fresh": False}


def read_snapshot(path, *, minutes=60, device=None, now=None):
    now = time.time() if now is None else now
    result = empty_snapshot(now)
    path = Path(path).resolve()
    if not path.is_file():
        return result
    # URI mode=ro prevents the dashboard from creating or changing the database.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.execute("BEGIN")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "samples" not in tables:
            return result
        latest = db.execute("SELECT id,device_key,recorded_at,payload FROM samples "
                            "WHERE device_key=? ORDER BY id DESC LIMIT 1", (device,)).fetchone() if device else db.execute(
                            "SELECT id,device_key,recorded_at,payload FROM samples ORDER BY id DESC LIMIT 1").fetchone()
        if not latest:
            return result
        _, key, recorded_at, payload = latest
        data = json.loads(payload)
        channel_ids = data.pop("channels", [])
        data.update(key=key, recorded_at=recorded_at, age_seconds=max(0, now-recorded_at))
        result["device"] = data
        result["fresh"] = now-recorded_at <= max(30, data["interval"] * 3 + data["timeout"])
        for row in db.execute("SELECT s.device_key,s.payload FROM samples s JOIN "
                              "(SELECT device_key,MAX(id) id FROM samples GROUP BY device_key) l ON s.id=l.id"):
            meta = json.loads(row[1])
            result["devices"].append({"key": row[0], "host": meta["host"], "iface": meta["iface"]})
        rows = db.execute("SELECT recorded_at,payload FROM samples WHERE device_key=? AND recorded_at>=? "
                          "ORDER BY recorded_at,id", (key, now-minutes*60)).fetchall()
        for stamp, raw in rows:
            item = json.loads(raw)
            result["history"].append({"time": stamp, "connection": item["connection"],
                                      "values": item["values"], "sources": item["sources"]})
        # All samples are kept in the API for honest CSV export; the browser can draw <=5000 points.
        if "events" in tables:
            result["events"] = [{"time": row[0], "severity": row[1], "message": row[2]} for row in db.execute(
                "SELECT recorded_at,severity,message FROM events WHERE device_key=? AND recorded_at>=? "
                "ORDER BY id DESC LIMIT 100", (key, now-minutes*60))]
        if "outbox" in tables:
            for channel in channel_ids:
                count = db.execute("SELECT COUNT(*) FROM outbox WHERE channel=?", (channel["key"],)).fetchone()[0]
                first = db.execute("SELECT attempts,next_attempt FROM outbox WHERE channel=? ORDER BY id LIMIT 1",
                                   (channel["key"],)).fetchone()
                result["queues"].append({"kind": channel["kind"], "pending": count,
                                         "attempts": first[0] if first else 0,
                                         "next_attempt": first[1] if first else 0})
    count = len(rows)
    connected = sum(item["connection"] == "UP" for item in result["history"])
    result["summary"] = {"samples": count, "connected_samples": connected,
                          "connection_success_percent": 100*connected/count if count else None,
                          "events": len(result["events"]),
                          "pending": sum(q["pending"] for q in result["queues"])}
    return result


def demo_snapshot(now=None, minutes=60):
    """Explicit illustration only: no database writes, SSH, or messaging APIs."""
    now = time.time() if now is None else now
    points = []
    for i in range(121):
        down = 67 <= i <= 71
        points.append({"time": now-(120-i)*15, "connection": "DOWN" if down else "UP",
                       "values": {} if down else {"cpu": round(38+14*math.sin(i/9)+(36 if 25<i<37 else 0),1),
                         "ram": round(44+5*math.sin(i/13),1), "temp": None,
                         "iface": "down" if 85<i<94 else "up"},
                       "sources": {"cpu": "DEMO", "ram": "DEMO", "iface": "DEMO"}})
    latest = points[-1]
    result = empty_snapshot(now)
    result.update(demo=True, fresh=True,
        device={"key": "demo", "host": "192.168.10.129", "protocol": "ssh", "iface": "gns3test",
                "interval": 15, "timeout": 15, "thresholds": {"cpu":75,"ram":65,"temp":65},
                "temp_enabled":True, "recovery_margin":5, "connection":"UP", "connection_error":"",
                "recorded_at":now, "age_seconds":0, "values":latest["values"], "errors":{"temp":"VM không có cảm biến"},
                "sources":latest["sources"], "states":{k:{"status":"UNKNOWN" if k=="temp" else "OK"} for k in ("cpu","ram","temp","iface")}},
        devices=[{"key":"demo","host":"192.168.10.129","iface":"gns3test"}], history=points,
        events=[{"time":now-405,"severity":"RECOVERY","message":"MÔ PHỎNG: Interface đã phục hồi."},
                {"time":now-540,"severity":"ALERT","message":"MÔ PHỎNG: Interface DOWN."},
                {"time":now-735,"severity":"RECOVERY","message":"MÔ PHỎNG: SSH đã kết nối lại."}],
        queues=[{"kind":"telegram","pending":0,"attempts":0,"next_attempt":0}],
        summary={"samples":len(points),"connected_samples":116,"connection_success_percent":100*116/121,"events":3,"pending":0})
    result["history"]=[item for item in result["history"] if item["time"]>=now-minutes*60]
    result["events"]=[item for item in result["events"] if item["time"]>=now-minutes*60]
    count=len(result["history"])
    connected=sum(item["connection"]=="UP" for item in result["history"])
    result["summary"].update(samples=count,connected_samples=connected,
                             connection_success_percent=100*connected/count if count else None,
                             events=len(result["events"]))
    return result


def csv_export(snapshot):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["timestamp_utc","host","connection","cpu_percent","ram_percent","temperature_c","interface_state",
                     "cpu_source","ram_source","temp_source","interface_source","dashboard_demo"])
    def cell(value):
        return "'"+value if isinstance(value,str) and value.startswith(("=","+","-","@")) else value
    for item in snapshot["history"]:
        v = item["values"]
        writer.writerow([datetime.fromtimestamp(item["time"], timezone.utc).isoformat(),
                         cell(snapshot["device"]["host"]), item["connection"],
                         v.get("cpu"),v.get("ram"),v.get("temp"),cell(v.get("iface")),
                         *(cell(item.get("sources",{}).get(k,"")) for k in ("cpu","ram","temp","iface")),snapshot["demo"]])
    return "\ufeff"+output.getvalue()


def handler_factory(path, demo=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, content_type="application/json; charset=utf-8", download=None):
            if isinstance(body,str):
                body=body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition",f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            allowed={f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}"}
            if self.headers.get("Host","").lower() not in allowed:
                return self.send(403,'{"error":"Chỉ cho phép truy cập localhost"}')
            origin=self.headers.get("Origin")
            if origin and origin not in {"http://"+host for host in allowed}:
                return self.send(403,'{"error":"Origin không hợp lệ"}')
            url=urlsplit(self.path)
            if url.path=="/favicon.ico":
                return self.send(204,b"","image/x-icon")
            assets={"/":"index.html","/app.js":"app.js","/style.css":"style.css"}
            if url.path in assets:
                name=assets[url.path]
                mime="text/html" if name.endswith("html") else "text/javascript" if name.endswith("js") else "text/css"
                return self.send(200,(ASSETS/name).read_bytes(),mime+"; charset=utf-8")
            if url.path not in {"/api/snapshot","/api/export.csv"}:
                return self.send(404,'{"error":"Không tìm thấy"}')
            args=parse_qs(url.query)
            try:
                minutes=int(args.get("minutes",["60"])[0])
                if not 1<=minutes<=1440:
                    raise ValueError
                device=args.get("device",[None])[0]
                snapshot=demo_snapshot(minutes=minutes) if demo else read_snapshot(path,minutes=minutes,device=device)
                if url.path.endswith(".csv"):
                    return self.send(200,csv_export(snapshot),"text/csv; charset=utf-8", "qtmnc-demo.csv" if demo else "qtmnc-metrics.csv")
                return self.send(200,json.dumps(snapshot,ensure_ascii=False,allow_nan=False))
            except json.JSONDecodeError:
                return self.send(503,'{"error":"Kho dữ liệu không hợp lệ; kiểm tra monitor"}')
            except ValueError:
                return self.send(400,'{"error":"Khoảng thời gian phải từ 1 đến 1440 phút"}')
            except (sqlite3.Error,OSError,KeyError):
                return self.send(503,'{"error":"Chưa đọc được kho dữ liệu; thử lại sau"}')

        def do_POST(self):
            self.send(405,'{"error":"Dashboard chỉ hỗ trợ đọc dữ liệu"}')
    return Handler


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file",type=Path,default=ROOT/".monitor_state/simple.sqlite3")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--demo",action="store_true",help="Dữ liệu minh họa, không truy cập thiết bị hay gửi tin")
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:
        parser.error("Port phải trong 1..65535")
    server=ThreadingHTTPServer(("127.0.0.1",args.port),handler_factory(args.state_file,args.demo))
    print(f"Dashboard: http://127.0.0.1:{args.port} · "+("MÔ PHỎNG" if args.demo else "dữ liệu monitor đã lưu"),flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
