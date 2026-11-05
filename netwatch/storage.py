import json
import csv
import sqlite3
import threading
import time
from pathlib import Path

LABELS = {"connection": "Kết nối", "cpu_pct": "CPU", "ram_pct": "RAM", "temperature_c": "Nhiệt độ"}


def transition(value, previous, threshold=None, margin=5):
    last = previous.get("last", "OK")
    if value is None:
        return {"state": "UNKNOWN", "last": last}
    if threshold is None:
        state = "OK" if value else "ALERT"
    else:
        state = "ALERT" if value > threshold or (last == "ALERT" and value > threshold - margin) else "OK"
    return {"state": state, "last": state}


class Store:
    def __init__(self, path="data/netwatch.sqlite3", demo=False, csv_path=None):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.demo = demo
        self.csv_path = Path(csv_path) if csv_path and not demo else None
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS current(device TEXT PRIMARY KEY, payload TEXT NOT NULL, states TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY, device TEXT NOT NULL, at REAL NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS samples_device_at ON samples(device,at);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, at REAL NOT NULL, device TEXT NOT NULL, metric TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, channel TEXT NOT NULL, message TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL, sent_at REAL, last_error TEXT);
        CREATE TABLE IF NOT EXISTS health_current(id TEXT PRIMARY KEY, payload TEXT NOT NULL, last TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS health_samples(id INTEGER PRIMARY KEY, check_id TEXT NOT NULL, at REAL NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS health_samples_at ON health_samples(check_id,at);
        """)

    def record(self, device, config, sample=None, kind="online", error="", channels=(), at=None):
        now = time.time() if at is None else at
        device_id = device["id"]
        with self.lock, self.db:
            old = self.db.execute("SELECT payload,states FROM current WHERE device=?", (device_id,)).fetchone()
            prior_sample = json.loads(old["payload"]) if old else {}
            prior = json.loads(old["states"]) if old else {}
            sample = json.loads(json.dumps(sample)) if sample is not None else {"cpu_pct": None, "ram_pct": None, "temperature_c": None, "interfaces": {}}
            dt = now - prior_sample.get("at", now)
            for name in device["interfaces"]:
                item = sample.setdefault("interfaces", {}).setdefault(name, {"state": "unknown"})
                before = prior_sample.get("interfaces", {}).get(name, {})
                for direction in ("rx", "tx"):
                    current, previous = item.get(direction + "_bytes"), before.get(direction + "_bytes")
                    item[direction + "_mbps"] = round((current - previous) * 8 / dt / 1e6, 4) if dt > 0 and current is not None and previous is not None and current >= previous else None
            sample.update({"id": device_id, "at": now, "kind": kind, "error": error, "source": device["protocol"].upper(), "sample_kind": "demo" if self.demo else "lab"})
            states = {}
            states["connection"] = transition(kind != "offline", prior.get("connection", {}))
            if kind != "offline":
                keys = ["cpu_pct", "ram_pct"] + (["temperature_c"] if config["monitor_temperature"] else [])
                for key in keys:
                    states[key] = transition(sample.get(key), prior.get(key, {}), config["thresholds"][key], config["hysteresis"])
                for name in device["interfaces"]:
                    raw = sample["interfaces"][name]["state"]
                    states["iface:" + name] = transition(None if raw == "unknown" else raw == "up", prior.get("iface:" + name, {}))
            else:
                # Không tạo hàng loạt lỗi CPU/RAM khi nguyên nhân chung là mất kết nối.
                for key, state in prior.items():
                    if key != "connection":
                        states[key] = {"state": "UNKNOWN", "last": state["last"]}
            changed_messages = []
            event_id = None
            for key, state in states.items():
                previous = prior.get(key, {}).get("state")
                if key != "connection" and kind == "offline":
                    continue
                if previous == state["state"] or (previous is None and state["state"] == "OK"):
                    continue
                label = LABELS.get(key, key.replace("iface:", "Interface "))
                suffix = ""
                if key in config["thresholds"] and sample.get(key) is not None:
                    unit = "°C" if key == "temperature_c" else "%"
                    suffix = f" ({sample[key]:.1f}{unit}; ngưỡng > {config['thresholds'][key]})"
                if key == "connection" and state["state"] == "ALERT":
                    suffix = ": " + error
                wording = {"ALERT": "CẢNH BÁO", "UNKNOWN": "KHÔNG CÓ DỮ LIỆU", "OK": "ĐÃ PHỤC HỒI"}[state["state"]]
                if previous == "UNKNOWN" and state["state"] == "ALERT":
                    wording = "ĐÃ CÓ DỮ LIỆU, VẪN CẢNH BÁO"
                message = f"{device['name']} [{sample['source']}] | {label}: {wording}{suffix}"
                event_id = self.db.execute("INSERT INTO events(at,device,metric,state,message) VALUES(?,?,?,?,?)", (now, device_id, key, state["state"], message)).lastrowid
                changed_messages.append(message)
            if changed_messages and not self.demo:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(now))
                for channel in channels:
                    self.db.execute("INSERT INTO outbox(event_id,channel,message,next_at) VALUES(?,?,?,?)", (event_id, channel, timestamp + "\n" + "\n".join(changed_messages), now))
            sample["states"] = {k: v["state"] for k, v in states.items()}
            self.db.execute("INSERT INTO current VALUES(?,?,?) ON CONFLICT(device) DO UPDATE SET payload=excluded.payload,states=excluded.states", (device_id, json.dumps(sample), json.dumps(states)))
            self.db.execute("INSERT INTO samples(device,at,payload) VALUES(?,?,?)", (device_id, now, json.dumps(sample)))
            self.db.execute("DELETE FROM samples WHERE at < ?", (now - 86400,))
            self.db.execute("DELETE FROM samples WHERE device=? AND id NOT IN (SELECT id FROM samples WHERE device=? ORDER BY id DESC LIMIT 5000)", (device_id, device_id))
            self.db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)")
            self.db.execute("DELETE FROM outbox WHERE sent_at IS NOT NULL AND sent_at < ?", (now - 86400,))
        if self.csv_path:
            try:
                self.append_csv(device, sample)
            except OSError as exc:
                print(f"Không ghi được CSV ({type(exc).__name__}); mẫu đã lưu SQLite", flush=True)
        return sample

    def append_csv(self, device, sample):
        with self.lock:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            header = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
            with self.csv_path.open("a", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                if header:
                    writer.writerow(["timestamp_utc", "device_id", "device_ip", "protocol", "sample_kind", "cpu_pct", "ram_pct", "temperature_c", "interface", "state", "rx_bytes", "tx_bytes", "rx_mbps", "tx_mbps"])
                for name, interface in sample["interfaces"].items():
                    writer.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sample["at"])), device["id"], device["host"], sample["source"], sample["sample_kind"], sample.get("cpu_pct"), sample.get("ram_pct"), sample.get("temperature_c"), name, interface.get("state"), interface.get("rx_bytes"), interface.get("tx_bytes"), interface.get("rx_mbps"), interface.get("tx_mbps")])

    def record_health(self, check_id, name, device_id, sample, passed, detail, channels=(), at=None):
        now = time.time() if at is None else at
        with self.lock, self.db:
            old = self.db.execute("SELECT payload,last FROM health_current WHERE id=?", (check_id,)).fetchone()
            previous = json.loads(old["payload"])["state"] if old else None
            changed = transition(passed, {"last": old["last"] if old else "OK"})
            value = {**sample, "id": check_id, "name": name, "device": device_id, "at": now, "state": changed["state"], "detail": detail, "sample_kind": "demo" if self.demo else "lab"}
            if previous != changed["state"] and not (previous is None and changed["state"] == "OK"):
                wording = {"ALERT": "CẢNH BÁO", "OK": "ĐÃ PHỤC HỒI", "UNKNOWN": "KHÔNG CÓ DỮ LIỆU"}[changed["state"]]
                message = f"{name}: {wording} | {detail}"
                event_id = self.db.execute("INSERT INTO events(at,device,metric,state,message) VALUES(?,?,?,?,?)", (now, device_id, "check:" + check_id, changed["state"], message)).lastrowid
                if not self.demo:
                    stamp = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(now))
                    for channel in channels:
                        self.db.execute("INSERT INTO outbox(event_id,channel,message,next_at) VALUES(?,?,?,?)", (event_id, channel, stamp + "\n" + message, now))
            self.db.execute("INSERT INTO health_current VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last=excluded.last", (check_id, json.dumps(value), changed["last"]))
            self.db.execute("INSERT INTO health_samples(check_id,at,payload) VALUES(?,?,?)", (check_id, now, json.dumps(value)))
            self.db.execute("DELETE FROM health_samples WHERE at < ?", (now - 86400,))
            self.db.execute("DELETE FROM health_samples WHERE check_id=? AND id NOT IN (SELECT id FROM health_samples WHERE check_id=? ORDER BY id DESC LIMIT 5000)", (check_id, check_id))
            self.db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)")
            return value

    def health(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM health_current ORDER BY id")]

    def health_history(self, check_id, limit=300):
        with self.lock:
            rows = self.db.execute("SELECT payload FROM health_samples WHERE check_id=? ORDER BY id DESC LIMIT ?", (check_id, max(1, min(5000, limit)))).fetchall()
            return [json.loads(r[0]) for r in reversed(rows)]

    def snapshot(self):
        with self.lock:
            return {r["device"]: json.loads(r["payload"]) for r in self.db.execute("SELECT device,payload FROM current")}

    def history(self, device, limit=300):
        with self.lock:
            rows = self.db.execute("SELECT payload FROM samples WHERE device=? ORDER BY id DESC LIMIT ?", (device, min(5000, max(1, limit)))).fetchall()
            return [json.loads(row[0]) for row in reversed(rows)]

    def events(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100")]

    def due(self, now=None):
        with self.lock:
            row = self.db.execute("SELECT * FROM outbox WHERE sent_at IS NULL AND next_at<=? ORDER BY id LIMIT 1", (time.time() if now is None else now,)).fetchone()
            return dict(row) if row else None

    def delivered(self, item, error=None, retry_after=None, now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            if error is None:
                self.db.execute("UPDATE outbox SET sent_at=?,last_error=NULL WHERE id=?", (now, item["id"]))
            else:
                delay = max(min(300, 2 ** min(item["attempts"] + 1, 9)), min(86400, max(0, retry_after or 0)))
                self.db.execute("UPDATE outbox SET attempts=attempts+1,next_at=?,last_error=? WHERE id=?", (now + delay, error, item["id"]))

    def queue(self):
        with self.lock:
            return dict(self.db.execute("SELECT count(*) pending, COALESCE(sum(attempts>0),0) retrying FROM outbox WHERE sent_at IS NULL").fetchone())

    def close(self):
        with self.lock:
            self.db.close()
