#!/usr/bin/env python3
"""Web mẫu Lab 4 chạy tại SRV1; không đọc/chia sẻ file trong thư mục dự án."""
import argparse
import ipaddress
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(status=200, delay=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(delay)
            payload = ("<!doctype html><html lang='vi'><meta charset='utf-8'><title>SRV1 NetWatch</title><h1>Web SRV1</h1><p>Dịch vụ HTTP thử nghiệm cho bài thực hành buổi 5.</p></html>").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="10.10.10.10")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--status", type=int, choices=(200, 503), default=200)
    parser.add_argument("--delay", type=float, default=0)
    args = parser.parse_args()
    ipaddress.IPv4Address(args.bind)
    if not 1024 <= args.port <= 65535 or not 0 <= args.delay <= 10:
        parser.error("Cổng/delay không hợp lệ")
    with ThreadingHTTPServer((args.bind, args.port), make_handler(args.status, args.delay)) as server:
        print(f"Web lab: http://{args.bind}:{args.port} | status={args.status} | delay={args.delay}s | Ctrl+C dừng", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
