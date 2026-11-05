import math
import threading
import time

from .collectors import CollectionError, SSHCollector, SNMPCollector
from .notifications import configured_channels, delivery_loop
from .health import ping_target, http_target, verdict


class Service:
    def __init__(self, config, store, demo=False):
        self.config, self.store, self.demo = config, store, demo
        self.stop = threading.Event()
        self.threads = []
        self.channels = [] if demo else configured_channels()

    def worker(self, device):
        collector = (SSHCollector if device["protocol"] == "ssh" else SNMPCollector)(device, self.config["timeout_seconds"])
        try:
            while not self.stop.is_set():
                start = time.monotonic()
                try:
                    sample = collector.collect()
                    self.store.record(device, self.config, sample, channels=self.channels)
                except CollectionError as exc:
                    self.store.record(device, self.config, kind=exc.kind, error=exc.detail, channels=self.channels)
                except Exception as exc:
                    # Giữ worker hoạt động ngay cả khi một chu kỳ lỗi; không in secret.
                    print(f"{device['id']}: lỗi xử lý ({type(exc).__name__})", flush=True)
                self.stop.wait(max(1, self.config["interval_seconds"] - (time.monotonic() - start)))
        finally:
            collector.close()

    def demo_worker(self):
        tick = 0
        while not self.stop.is_set():
            for idx, device in enumerate(self.config["devices"]):
                cpu = round(45 + 35 * math.sin(tick / 5 + idx), 1)
                sample = {"schema": 1, "cpu_pct": cpu, "ram_pct": min(90, 43 + idx * 10), "temperature_c": None,
                          "interfaces": {name: {"state": "up", "rx_bytes": tick * 270000 + idx * 100, "tx_bytes": tick * 180000, "rx_errors": 0, "tx_errors": 0} for name in device["interfaces"]}}
                self.store.record(device, self.config, sample)
                health = {"kind": "ping", "host": device["host"], "sent": 10, "received": 10, "packet_loss_pct": 0, "rtt_avg_ms": round(1.5 + idx + math.sin(tick / 4), 2), "error": ""}
                self.store.record_health("ping-" + device["id"], "ICMP " + device["name"], device["id"], health, True, "Dữ liệu mô phỏng")
            for service in self.config["checks"]["http_services"]:
                self.store.record_health("http-" + service["id"], service["name"], service["device"], {"kind": "http", "status_code": 200, "response_ms": 24 + tick % 12, "error": ""}, True, "Dữ liệu mô phỏng")
            tick += 1
            self.stop.wait(2)

    def health_worker(self, device, service=None):
        checks = self.config["checks"]
        check_id = "http-" + service["id"] if service else "ping-" + device["id"]
        name = service["name"] if service else "ICMP " + device["name"]
        while not self.stop.is_set():
            start = time.monotonic()
            try:
                value = http_target(service["url"], checks["http_timeout_seconds"]) if service else ping_target(device["host"], checks["ping_count"], checks["ping_timeout_ms"])
                passed, detail = verdict(value, checks)
                self.store.record_health(check_id, name, device["id"], value, passed, detail, self.channels)
            except Exception as exc:
                print(f"{check_id}: chưa đo được ({type(exc).__name__})", flush=True)
            self.stop.wait(max(1, checks["interval_seconds"] - (time.monotonic() - start)))

    def start(self):
        targets = [(self.demo_worker, ())] if self.demo else [(self.worker, (d,)) for d in self.config["devices"]] + [(delivery_loop, (self.store, self.stop))]
        if not self.demo and self.config["checks"]["enabled"]:
            targets += [(self.health_worker, (d,)) for d in self.config["devices"]]
            by_id = {d["id"]: d for d in self.config["devices"]}
            targets += [(self.health_worker, (by_id[s["device"]], s)) for s in self.config["checks"]["http_services"] if s.get("enabled")]
        for target, args in targets:
            thread = threading.Thread(target=target, args=args, daemon=True)
            self.threads.append(thread)
            thread.start()

    def shutdown(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=2)
