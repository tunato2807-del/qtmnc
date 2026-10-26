from __future__ import annotations

from dataclasses import dataclass, field

METRIC_LABELS = {"cpu":"CPU", "ram":"RAM", "temp":"Nhiệt độ", "iface":"Interface", "ssh":"Kết nối SSH", "snmp":"Kết nối SNMP"}

@dataclass
class Sample:
    values: dict
    errors: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)


@dataclass
class Delivery:
    ok: bool
    reason: str = ""
    retry_after: float | None = None
