import ipaddress
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
IFACE = re.compile(r"^[a-zA-Z0-9_.:-]{1,32}$")
CHECK_DEFAULTS = {"enabled": False, "interval_seconds": 60, "ping_count": 10, "ping_timeout_ms": 1000,
                  "latency_ms": 100, "packet_loss_pct": 20, "http_timeout_seconds": 5, "http_slow_seconds": 3, "http_services": []}


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
    if not isinstance(cfg.get("checks", {}), dict):
        raise ValueError("checks phải là object JSON")
    checks = cfg["checks"] = {**CHECK_DEFAULTS, **cfg.get("checks", {})}
    if not isinstance(checks["enabled"], bool) or not isinstance(cfg.get("csv_enabled", False), bool):
        raise ValueError("checks.enabled và csv_enabled phải là true/false")
    limits = {"interval_seconds": (30, 3600), "ping_count": (1, 20), "ping_timeout_ms": (100, 3000),
              "latency_ms": (1, 10000), "packet_loss_pct": (0, 100), "http_timeout_seconds": (1, 30), "http_slow_seconds": (0.1, 30)}
    for key, (low, high) in limits.items():
        value = checks[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError("Tham số checks không hợp lệ: " + key)
    if not isinstance(checks["ping_count"], int) or not isinstance(checks["ping_timeout_ms"], int):
        raise ValueError("Số gói và timeout ping phải là số nguyên")
    services, service_ids = checks["http_services"], set()
    if not isinstance(services, list) or len(services) > 10:
        raise ValueError("Cần danh sách HTTP tối đa 10 dịch vụ")
    devices_by_id = {d["id"]: d for d in cfg["devices"]}
    for service in services:
        if not isinstance(service, dict) or not all(isinstance(service.get(k), str) and service[k] for k in ("id", "name", "device", "url")):
            raise ValueError("Thông tin dịch vụ HTTP không hợp lệ")
        sid = service["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", sid) or sid in service_ids or service["device"] not in devices_by_id or not isinstance(service.get("enabled", False), bool):
            raise ValueError("ID/thiết bị/trạng thái HTTP không hợp lệ")
        service_ids.add(sid)
        url = urlsplit(service["url"])
        if url.scheme not in ("http", "https") or url.hostname != devices_by_id[service["device"]]["host"] or url.username or url.password or url.query or url.fragment or (url.port is not None and not 1 <= url.port <= 65535):
            raise ValueError("HTTP URL phải thuộc thiết bị trong inventory, không chứa secret/query")
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
