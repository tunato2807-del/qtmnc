"""Local Linux metrics exporter for the read-only Net-SNMP extend command."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import time
from .collectors.ssh import cpu_percent, ram_percent
from .errors import DataError
from .models import Sample
from .validation import number

DEMO_FILE = Path("/var/lib/qtmnc-lab/temperature.json")


def read_temperature(source="auto", demo_file=DEMO_FILE, sysroot=Path("/sys")):
    if source == "demo":
        try:
            data = json.loads(Path(demo_file).read_text())
            if not isinstance(data,dict):
                raise DataError("Dữ liệu mô phỏng không hợp lệ")
            expires = number(data.get("expires_at"), 0)
            value = data.get("celsius") if expires > time.time() else data.get("baseline", 40)
            return number(value, -50, 200)
        except (OSError, ValueError, TypeError):
            raise DataError("Chưa có file nhiệt độ MÔ PHỎNG hợp lệ; chạy labctl temperature") from None
    values = []
    for hw in (Path(sysroot)/"class/hwmon").glob("hwmon*"):
        try:
            if (hw/"name").read_text().strip() not in {"coretemp","k10temp","zenpower","cpu_thermal"}:
                continue
            for path in hw.glob("temp*_input"):
                values.append(number(path.read_text().strip(), -50000, 200000)/1000)
        except (OSError, DataError):
            continue
    for zone in (Path(sysroot)/"class/thermal").glob("thermal_zone*"):
        try:
            kind = (zone/"type").read_text().strip()
            if kind in {"x86_pkg_temp","soc_thermal"} or kind.startswith("cpu"):
                values.append(number((zone/"temp").read_text().strip(), -50000, 200000)/1000)
        except (OSError, DataError):
            continue
    if not values:
        raise DataError("Linux/VM không cung cấp cảm biến nhiệt độ CPU")
    return max(values)


def collect_local(iface, temperature_source="auto", interval=1.0, procroot=Path("/proc"), sysroot=Path("/sys"), demo_file=DEMO_FILE):
    if not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,64}", iface):
        raise ValueError("Tên interface không hợp lệ")
    values, errors, sources = {}, {}, {}
    def record(metric, operation):
        try:
            values[metric] = operation()
        except (OSError, DataError, ValueError):
            values[metric] = None
            errors[metric] = "Không đọc được chỉ số từ Linux; cảm biến hoặc quyền có thể chưa có"
        sources[metric] = "DEMO" if metric == "temp" and temperature_source == "demo" else "Linux"
    def cpu():
        before = (Path(procroot)/"stat").read_text()
        time.sleep(interval)
        after = (Path(procroot)/"stat").read_text()
        return cpu_percent(before+"\n"+after)
    record("cpu",cpu)
    record("ram",lambda:ram_percent((Path(procroot)/"meminfo").read_text()))
    record("iface",lambda:(Path(sysroot)/"class/net"/iface/"operstate").read_text().strip().lower())
    record("temp",lambda:read_temperature(temperature_source,demo_file,sysroot))
    return Sample(values,errors,sources)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface",required=True)
    parser.add_argument("--temperature-source",choices=("auto","demo"),default="auto")
    args=parser.parse_args(argv)
    result=collect_local(args.iface,args.temperature_source)
    print(json.dumps({"version":1,"values":result.values,"errors":result.errors,"sources":result.sources},ensure_ascii=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
