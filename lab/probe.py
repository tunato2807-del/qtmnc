#!/usr/bin/env python3
"""Probe chỉ đọc; chạy không cần sudo; một tiến trình Python cho mỗi mẫu."""
import argparse
import json
import re
import time
from pathlib import Path


def cpu_counters(text):
    # Tám trường đầu; guest/guest_nice đã nằm trong user/nice, không cộng lại.
    parts = text.splitlines()[0].split()
    if parts[0] != "cpu" or len(parts) < 9:
        raise ValueError("/proc/stat thiếu trường")
    values = [int(v) for v in parts[1:9]]
    return sum(values), values[3] + values[4]


def cpu_percent(first, second):
    total = second[0] - first[0]
    idle = second[1] - first[1]
    if total <= 0 or idle < 0 or idle > total:
        return None
    return round(100 * (total - idle) / total, 2)


def ram_percent(text):
    data = {line.split(":", 1)[0]: int(line.split()[1]) for line in text.splitlines() if ":" in line}
    total, available = data.get("MemTotal", 0), data.get("MemAvailable")
    if not total or available is None or not 0 <= available <= total:
        return None
    return round(100 * (total - available) / total, 2)


def temperature(root=Path("/sys/class/thermal")):
    values = []
    for path in root.glob("thermal_zone*/temp"):
        try:
            value = float(path.read_text()) / 1000
            if 0 < value < 200:
                values.append(value)
        except (OSError, ValueError):
            pass
    return round(max(values), 1) if values else None


def read_interfaces(names, root=Path("/sys/class/net")):
    result = {}
    for name in names:
        base = root / name
        item = {"state": "unknown"}
        try:
            raw = (base / "operstate").read_text().strip()
            item["state"] = "up" if raw == "up" else "down" if raw in ("down", "lowerlayerdown", "dormant", "notpresent") else "unknown"
        except OSError:
            pass
        for field in ("rx_bytes", "tx_bytes", "rx_errors", "tx_errors"):
            try:
                item[field] = int((base / "statistics" / field).read_text())
            except (OSError, ValueError):
                item[field] = None
        result[name] = item
    return result


def collect(names):
    first = cpu_counters(Path("/proc/stat").read_text())
    time.sleep(1)
    second = cpu_counters(Path("/proc/stat").read_text())
    return {"schema": 1, "cpu_pct": cpu_percent(first, second), "ram_pct": ram_percent(Path("/proc/meminfo").read_text()),
            "temperature_c": temperature(), "interfaces": read_interfaces(names)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interfaces", nargs="+", required=True)
    args = parser.parse_args()
    if len(args.interfaces) > 8 or not all(re.fullmatch(r"[a-zA-Z0-9_.:-]{1,32}", i) for i in args.interfaces):
        parser.error("Interface không hợp lệ")
    print(json.dumps(collect(args.interfaces), separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
