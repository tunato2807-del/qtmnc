"""Move complete Ethernet frames between a TAP device and a local GNS3 UDP NIO."""
from collections import Counter
import queue
import socket
import threading

MAX_FRAME = 65507  # Maximum IPv4 UDP payload; normal Ethernet frames are smaller.


def ethernet_frame(data):
    return isinstance(data, bytes) and 14 <= len(data) <= MAX_FRAME


class EthernetTunnel:
    """Device.read/write inject at the TAP receive path; frames are never rewritten."""

    def __init__(self, device, udp_socket, peer_port):
        self.device = device
        self.socket = udp_socket
        self.peer = ("127.0.0.1", peer_port)
        self.stop = threading.Event()
        self.errors = queue.Queue()
        self.counts = Counter()
        self.lock = threading.Lock()
        self.workers = []

    def count(self, name):
        with self.lock:
            self.counts[name] += 1

    def snapshot(self):
        with self.lock:
            return dict(self.counts)

    def _guard(self, operation):
        try:
            operation()
        except Exception as exc:
            if not self.stop.is_set():
                self.errors.put(exc)
                self.stop.set()

    def _tap_to_udp(self):
        while not self.stop.is_set():
            frame = self.device.read(self.stop)
            if frame is None:
                continue
            if not ethernet_frame(frame):
                self.count("dropped")
                continue
            try:
                self.socket.sendto(frame, self.peer)
            except (ConnectionResetError, ConnectionRefusedError):
                self.count("peer_unavailable")
                continue
            self.count("tap_to_gns3")

    def _udp_to_tap(self):
        while not self.stop.is_set():
            try:
                frame, sender = self.socket.recvfrom(MAX_FRAME + 1)
            except (socket.timeout, ConnectionResetError):
                # Windows can report an ICMP error while GNS3 is not started yet.
                continue
            if sender != self.peer or not ethernet_frame(frame):
                self.count("dropped")
                continue
            if self.device.write(frame, self.stop):
                self.count("gns3_to_tap")

    def start(self):
        if self.workers:
            raise RuntimeError("Tunnel đã được khởi động")
        self.socket.settimeout(0.25)
        for name, operation in (("tap-read", self._tap_to_udp), ("udp-read", self._udp_to_tap)):
            worker = threading.Thread(target=self._guard, args=(operation,), name=name, daemon=True)
            self.workers.append(worker)
            worker.start()

    def raise_if_failed(self):
        if not self.errors.empty():
            raise self.errors.get_nowait()

    def close(self):
        self.stop.set()
        self.device.cancel()
        for worker in self.workers:
            worker.join(timeout=5)
        if any(worker.is_alive() for worker in self.workers):
            raise RuntimeError("Chưa dừng được I/O TAP; đóng cửa sổ cầu nối rồi kiểm tra driver")
