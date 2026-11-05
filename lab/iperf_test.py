#!/usr/bin/env python3
"""Đo thông lượng TCP nội bộ theo yêu cầu, có giới hạn tải và thời gian."""
import argparse
import csv
import ipaddress
import json
import subprocess
import time
from pathlib import Path


def measure(target, seconds=5, mbps=20, reverse=False):
    target = str(ipaddress.IPv4Address(target))
    if not 1 <= seconds <= 30 or not 1 <= mbps <= 200:
        raise ValueError("Thời gian hoặc tải không hợp lệ")
    command = ["iperf3", "-c", target, "-p", "5201", "-t", str(seconds), "-b", f"{mbps}M", "-J"]
    if reverse:
        command.append("-R")
    base = {"target": target, "direction": "SRV1→R1" if reverse else "R1→SRV1", "limit_mbps": mbps, "seconds": seconds}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=seconds + 10, check=False)
        data = json.loads(result.stdout)
        if result.returncode or data.get("error"):
            raise ValueError("iperf3 lỗi")
        end = data["end"]
        sent, received = float(end["sum_sent"]["bits_per_second"]), float(end["sum_received"]["bits_per_second"])
        import math
        if not math.isfinite(sent) or not math.isfinite(received) or min(sent, received) < 0:
            raise ValueError("Số liệu không hợp lệ")
        return {**base, "sent_mbps": round(sent / 1e6, 3), "received_mbps": round(received / 1e6, 3), "status": "OK"}
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return {**base, "sent_mbps": None, "received_mbps": None, "status": "ERROR: kiểm tra iperf3/server TCP 5201"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="10.10.10.10")
    parser.add_argument("--seconds", type=int, default=5)
    parser.add_argument("--mbps", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("data/iperf_results.csv"))
    args = parser.parse_args()
    values = [measure(args.target, args.seconds, args.mbps, reverse) for reverse in (False, True)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = not args.output.exists() or args.output.stat().st_size == 0
    with args.output.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["timestamp_utc", *values[0]])
        if header:
            writer.writeheader()
        for value in values:
            writer.writerow({"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **value})
            print(json.dumps(value, ensure_ascii=False))
    print("TCP throughput khi giới hạn tải; không phải tốc độ Internet hoặc băng thông tối đa.")


if __name__ == "__main__":
    main()
