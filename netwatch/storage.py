import json
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
    def __init__(self, path="data/netwatch.sqlite3", demo=False):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.demo = demo
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS current(device TEXT PRIMARY KEY, payload TEXT NOT NULL, states TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY, device TEXT NOT NULL, at REAL NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS samples_device_at ON samples(device,at);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, at REAL NOT NULL, device TEXT NOT NULL, metric TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, channel TEXT NOT NULL, message TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL, sent_at REAL, last_error TEXT);
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
            return sample

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
