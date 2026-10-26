from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from .engine import metric_state
from .models import METRIC_LABELS

class Store:
    """Observed states and all channel deliveries are committed in one transaction."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS states (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY, channel TEXT NOT NULL, message TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def observe(self, config, sample, channels, connection_error=None):
        key = config.device_key
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM states WHERE key=?", (key,)).fetchone()
            states = json.loads(row[0]) if row else {}
            messages = []
            connection = "DOWN" if connection_error else "UP"
            previous_connection = states.get("connection")
            if connection == "DOWN" and previous_connection != "DOWN":
                messages.append(f"❌ Mất kết nối {config.protocol.upper()}: {connection_error}")
            elif connection == "UP" and previous_connection == "DOWN":
                messages.append(f"✅ Đã khôi phục kết nối {config.protocol.upper()}")
            states["connection"] = connection
            if sample is not None:
                for metric, value in sample.values.items():
                    previous = states.get(metric, {})
                    status = metric_state(metric, value, previous, config)
                    if status != previous.get("status") and (previous or status != "OK"):
                        label = METRIC_LABELS[metric] + (f" ({config.iface})" if metric == "iface" else "")
                        if "DEMO" in sample.sources.get(metric, "").upper():
                            label += " [MÔ PHỎNG]"
                        detail = (f"{value:.1f}{'°C' if metric == 'temp' else '%'}" if isinstance(value, (int,float)) else str(value)) if value is not None else "không có dữ liệu"
                        if status == "UNKNOWN":
                            messages.append(f"❓ {label}: KHÔNG XÁC ĐỊNH ({sample.errors.get(metric, detail)})")
                        elif status == "ALERT":
                            limit = f"; ngưỡng > {config.thresholds[metric]:g}" if metric in config.thresholds else ""
                            messages.append(f"🚨 {label}: CẢNH BÁO ({detail}{limit})")
                        elif previous.get("status") == "UNKNOWN":
                            messages.append(f"✅ {label}: đã có dữ liệu trở lại, bình thường ({detail})")
                        else:
                            messages.append(f"✅ {label}: đã bình thường ({detail})")
                    states[metric] = {"status": status, "last_known": previous.get("last_known") if status == "UNKNOWN" else status}
            if messages:
                body = f"Thiết bị: {config.host} [{config.protocol.upper()}]\n{time.strftime('%Y-%m-%d %H:%M:%S %z')}\n" + "\n".join(messages)
                for channel in channels:
                    db.execute("INSERT INTO outbox(channel,message) VALUES (?,?)", (channel, body))
            db.execute("INSERT INTO states(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(states)))
            return messages

    def due(self, channel, now):
        with self.connect() as db:
            # Preserve event order within a channel, including while backing off.
            row = db.execute("SELECT id,message,attempts,next_attempt FROM outbox WHERE channel=? ORDER BY id LIMIT 1", (channel,)).fetchone()
        return row if row and row[3] <= now else None

    def enqueue(self, channels, message):
        with self.connect() as db:
            for channel in channels:
                db.execute("INSERT INTO outbox(channel,message) VALUES (?,?)", (channel,message))

    def display_snapshot(self, config, channels):
        """Read committed alert states and channel queues; never expose credentials."""
        with self.connect() as db:
            row = db.execute("SELECT value FROM states WHERE key=?", (config.device_key,)).fetchone()
            states = json.loads(row[0]) if row else {}
            queues = {}
            for key in channels:
                count = db.execute("SELECT COUNT(*) FROM outbox WHERE channel=?", (key,)).fetchone()[0]
                oldest = db.execute("SELECT attempts,next_attempt FROM outbox WHERE channel=? ORDER BY id LIMIT 1", (key,)).fetchone()
                queues[key] = {"pending": count, "attempts": oldest[0] if oldest else 0,
                               "next_attempt": oldest[1] if oldest else 0}
            return states, queues

    def delivered(self, event_id):
        with self.connect() as db:
            db.execute("DELETE FROM outbox WHERE id=?", (event_id,))

    def failed(self, event_id, attempts, retry_after=None):
        delay = min(300, 2 ** min(attempts + 1, 9))
        if retry_after is not None:
            delay = max(delay, retry_after)
        with self.connect() as db:
            db.execute("UPDATE outbox SET attempts=attempts+1,next_attempt=? WHERE id=?", (time.time() + delay, event_id))
