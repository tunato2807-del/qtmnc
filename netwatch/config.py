import ipaddress
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IFACE = re.compile(r"^[a-zA-Z0-9_.:-]{1,32}$")


def load_inventory(path=ROOT / "inventory.json"):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or not isinstance(cfg.get("thresholds"), dict):
        raise ValueError("Inventory và thresholds phải là object JSON")
    for key, low, high in (("interval_seconds", 5, 3600), ("timeout_seconds", 2, 120), ("hysteresis", 0, 20)):
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} phải nằm trong {low}–{high}")
    for key, high in (("cpu_pct", 100), ("ram_pct", 100), ("temperature_c", 200)):
        value = cfg["thresholds"][key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= high:
            raise ValueError(f"Ngưỡng {key} không hợp lệ")
    if not isinstance(cfg.get("monitor_temperature"), bool):
        raise ValueError("monitor_temperature phải là true/false")
    if not isinstance(cfg["devices"], list) or not 1 <= len(cfg["devices"]) <= 20:
        raise ValueError("Cần 1–20 thiết bị")
    ids = set()
    for device in cfg["devices"]:
        if not isinstance(device, dict) or not all(isinstance(device.get(k), str) and device[k] for k in ("id", "name", "role", "host", "protocol", "credential_prefix")):
            raise ValueError("Thông tin thiết bị phải có đủ trường chuỗi không rỗng")
        name = device["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name) or name in ids:
            raise ValueError("ID thiết bị trùng hoặc không hợp lệ")
        ids.add(name)
        ipaddress.IPv4Address(device["host"])
        if device["protocol"] not in ("ssh", "snmp"):
            raise ValueError("Giao thức phải là ssh hoặc snmp")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", device["credential_prefix"]):
            raise ValueError("credential_prefix không hợp lệ")
        interfaces = device["interfaces"]
        if not isinstance(interfaces, list) or not interfaces or len(interfaces) > 8 or not all(isinstance(i, str) and IFACE.fullmatch(i) for i in interfaces) or len(set(interfaces)) != len(interfaces):
            raise ValueError("Danh sách interface không hợp lệ")
    for device in cfg["devices"]:
        parent = device.get("parent")
        if parent and (parent not in ids or parent == device["id"]):
            raise ValueError("Thiết bị cha không hợp lệ")
    return cfg


def validate_sample(value, interfaces):
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("Probe phải trả schema=1")
    for key, high in (("cpu_pct", 100), ("ram_pct", 100), ("temperature_c", 200)):
        v = value.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= high):
            raise ValueError(f"Số liệu {key} không hợp lệ")
    if not isinstance(value.get("interfaces"), dict):
        raise ValueError("Thiếu dữ liệu interface")
    clean = {"schema": 1, **{k: value.get(k) for k in ("cpu_pct", "ram_pct", "temperature_c")}, "interfaces": {}}
    for name in interfaces:
        item = value["interfaces"].get(name, {})
        state = item.get("state", "unknown")
        if state not in ("up", "down", "unknown"):
            raise ValueError("Trạng thái interface không hợp lệ")
        clean["interfaces"][name] = {"state": state}
        for key in ("rx_bytes", "tx_bytes", "rx_errors", "tx_errors"):
            counter = item.get(key)
            if counter is not None and (isinstance(counter, bool) or not isinstance(counter, int) or counter < 0):
                raise ValueError("Counter không hợp lệ")
            clean["interfaces"][name][key] = counter
    return clean
