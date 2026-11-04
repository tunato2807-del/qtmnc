#!/usr/bin/env python3
"""Tùy chọn SNMPv2c Net-SNMP extend; chỉ chạy trên clone lab sau provision."""
import argparse
import getpass
import os
import pwd
import re
import shutil
import socket
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    role = Path("/etc/netwatch/role").read_text().strip()
    if role not in ("router", "server"):
        parser.error("Chưa provision lab mới")
    address, interfaces = ("192.168.73.10", "mgmt0 srv0 users0") if role == "router" else ("10.10.10.10", "lan0")
    if not args.apply:
        print(f"Sẽ tạo dịch vụ netwatch-snmp trên {address}:161; chỉ đọc từ 192.168.73.1.")
        print("Thêm --apply sau khi cài snmpd; community nhập kín, không ghi trong command line.")
        return
    if os.geteuid() != 0 or not shutil.which("snmpd"):
        parser.error("Cần sudo và gói snmpd")
    if subprocess.run(["systemctl", "is-active", "--quiet", "netwatch-snmp"]).returncode != 0:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind((address, 161))
            except OSError:
                parser.error("UDP 161 đã có dịch vụ; kiểm tra dịch vụ snmpd trước")
    community = getpass.getpass("Community riêng (16–64 ký tự A–Z, a–z, 0–9, _, -): ")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", community):
        parser.error("Community không đúng định dạng")
    config = Path("/etc/netwatch/snmpd.conf")
    config.touch(mode=0o600, exist_ok=True)
    config.chmod(0o600)
    config.write_text(f"agentaddress udp:{address}:161\nrocommunity {community} 192.168.73.1\nextend netwatch /usr/bin/python3 /opt/netwatch/probe.py --interfaces {interfaces}\n", encoding="utf-8")
    daemon_user = pwd.getpwnam("Debian-snmp")
    os.chown(config, daemon_user.pw_uid, daemon_user.pw_gid)
    unit = Path("/etc/systemd/system/netwatch-snmp.service")
    unit.write_text("[Unit]\nDescription=NetWatch read-only lab SNMP\nAfter=network-online.target\nWants=network-online.target\n[Service]\nExecStart=/usr/sbin/snmpd -f -Lo -C -u Debian-snmp -g Debian-snmp -c /etc/netwatch/snmpd.conf\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target\n", encoding="utf-8")
    for command in (["systemctl", "daemon-reload"], ["systemctl", "enable", "--now", "netwatch-snmp"], ["systemctl", "restart", "netwatch-snmp"]):
        subprocess.run(command, check=True)
    print("Đã cấu hình. Nhập cùng community vào .env.netwatch trên Windows; đổi protocol trong inventory.json thành snmp.")


if __name__ == "__main__":
    main()
