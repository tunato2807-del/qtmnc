#!/usr/bin/env python3
"""Create only the two extra GNS3 NIC definitions. Preserve the existing NAT NIC."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def netplan_text(management_mac,test_mac):
    for mac in (management_mac,test_mac):
        if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}",mac):
            raise ValueError("MAC không hợp lệ")
    if management_mac.lower()==test_mac.lower():
        raise ValueError("Hai card phải khác MAC")
    return f"""# Only extra lab NICs; no gateway/default route is added.
network:
  version: 2
  ethernets:
    gns3mgmt:
      match:
        macaddress: "{management_mac.lower()}"
      set-name: gns3mgmt
      dhcp4: false
      dhcp6: false
      addresses: [192.168.10.129/24]
      optional: true
    gns3test:
      match:
        macaddress: "{test_mac.lower()}"
      set-name: gns3test
      dhcp4: false
      dhcp6: false
      addresses: [192.168.30.129/24]
      optional: true
"""


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--management-iface",required=True)
    p.add_argument("--test-iface",required=True)
    a=p.parse_args()
    if sys.platform!="linux" or os.geteuid()!=0:
        p.error("Chạy sudo từ console máy ảo Ubuntu")
    defaults=json.loads(subprocess.check_output(["ip","-j","route","show","default"],text=True))
    if not defaults:
        p.error("Chưa có default route NAT; kiểm tra card NAT trước khi thêm mạng lab")
    protected={row.get("dev") for row in defaults}|{"lo"}
    for iface in (a.management_iface,a.test_iface):
        if not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,64}",iface) or iface in protected:
            p.error("Không chọn loopback hoặc card NAT/default route; kiểm tra MAC và ip -br link")
    root=Path("/sys/class/net")
    management=(root/a.management_iface/"address").read_text().strip()
    test=(root/a.test_iface/"address").read_text().strip()
    text=netplan_text(management,test)
    destination=Path("/etc/netplan/90-qtmnc-gns3.yaml")
    before=destination.read_bytes() if destination.exists() else None
    if before:
        backup=Path("/root/qtmnc-netplan-backups")
        backup.mkdir(exist_ok=True,mode=0o700)
        shutil.copy2(destination,backup/f"90-qtmnc-{time.time_ns()}.yaml")
    try:
        destination.write_text(text)
        destination.chmod(0o600)
        subprocess.run(["netplan","generate"],check=True)
    except Exception:
        if before is None:
            destination.unlink(missing_ok=True)
        else:
            destination.write_bytes(before)
        raise
    print("Đã tạo netplan cho gns3mgmt / gns3test; chưa đổi mạng đang chạy.")
    print("Từ console VMware chạy: sudo netplan try --timeout 60")
    print("Kiểm tra rồi Enter xác nhận. Không thêm gateway cho hai NIC lab.")
    print("NAT/default route hiện tại được giữ bằng cấu hình riêng có sẵn.")


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print(f"Chưa tạo được netplan ({type(exc).__name__}); kiểm tra tên NIC/MAC và cấu hình có sẵn.",file=sys.stderr)
        raise SystemExit(2)
