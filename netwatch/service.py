import math
import threading
import time

from .collectors import CollectionError, SSHCollector, SNMPCollector
from .notifications import configured_channels, delivery_loop


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
                sample = {"schema": 1, "cpu_pct": cpu, "ram_pct": 43 + idx * 10, "temperature_c": None,
                          "interfaces": {name: {"state": "up", "rx_bytes": tick * 270000 + idx * 100, "tx_bytes": tick * 180000, "rx_errors": 0, "tx_errors": 0} for name in device["interfaces"]}}
                self.store.record(device, self.config, sample)
            tick += 1
            self.stop.wait(2)

    def start(self):
        targets = [(self.demo_worker, ())] if self.demo else [(self.worker, (d,)) for d in self.config["devices"]] + [(delivery_loop, (self.store, self.stop))]
        for target, args in targets:
            thread = threading.Thread(target=target, args=args, daemon=True)
            self.threads.append(thread)
            thread.start()

    def shutdown(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=2)
