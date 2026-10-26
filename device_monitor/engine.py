from __future__ import annotations

def metric_state(metric, value, previous, config):
    if value is None:
        return "UNKNOWN"
    if metric in {"iface", "ssh", "snmp"}:
        if value == "up":
            return "OK"
        return "ALERT" if value in {"down", "lowerlayerdown", "notpresent"} else "UNKNOWN"
    limit = config.thresholds[metric]
    if previous.get("last_known") == "ALERT":
        return "OK" if value <= limit - config.recovery_margin else "ALERT"
    return "ALERT" if value > limit else "OK"
