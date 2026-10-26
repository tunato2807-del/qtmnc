#!/usr/bin/env python3
"""Provision only the dedicated qtmnc lab agent; run with sudo on Ubuntu 22.04+."""
import argparse
import getpass
import ipaddress
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

SERVICE="qtmnc-lab-snmp.service"
CONFIG=Path("/etc/qtmnc-lab/snmpd.conf")
DEST=Path("/opt/qtmnc-lab")


def configuration(bind,allowed,iface,community,port=161,temperature="auto"):
    ipaddress.IPv4Address(bind)
    ipaddress.IPv4Address(allowed)
    if not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,64}",iface):
        raise ValueError("Interface không hợp lệ")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}",community):
        raise ValueError("Community cần 8–128 ký tự chữ/số/_/-, không có khoảng trắng")
    if not 1<=port<=65535 or temperature not in {"auto","demo"}:
        raise ValueError("Port hoặc nguồn nhiệt độ không hợp lệ")
    return f"""# Dedicated isolated lab agent; do not expose to untrusted networks.
agentAddress udp:{bind}:{port}
rocommunity "{community}" {allowed}/32
sysLocation GNS3-qtmnc-lab
extend qtmnc /usr/bin/python3 -B /opt/qtmnc-lab/linux_probe.py --iface {iface} --temperature-source {temperature}
"""

UNIT="""[Unit]
Description=QTMNC GNS3 read-only SNMP lab agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=Debian-snmp
Group=Debian-snmp
WorkingDirectory=/opt/qtmnc-lab
StateDirectory=qtmnc-lab-snmp
StateDirectoryMode=0700
RuntimeDirectory=qtmnc-lab-snmp
RuntimeDirectoryMode=0700
Environment=SNMP_PERSISTENT_DIR=/var/lib/qtmnc-lab-snmp
ExecStart=/usr/sbin/snmpd -f -Lo -C -c /etc/qtmnc-lab/snmpd.conf -p /run/qtmnc-lab-snmp/snmpd.pid
Restart=on-failure
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
"""


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bind",default="192.168.10.129")
    p.add_argument("--allow",default="192.168.10.1")
    p.add_argument("--iface",required=True)
    p.add_argument("--port",type=int,default=161)
    p.add_argument("--temperature-source",choices=("auto","demo"),default="auto")
    p.add_argument("--reconfigure",action="store_true")
    a=p.parse_args(argv)
    if sys.platform!="linux" or os.geteuid()!=0:
        p.error("Chạy bằng sudo trên máy ảo Ubuntu Linux")
    import grp
    import pwd
    if sys.version_info<(3,10) or not Path("/usr/sbin/snmpd").is_file():
        p.error("Cần Python 3.10+ và gói snmpd: sudo apt install snmpd snmp")
    if not (Path("/sys/class/net")/a.iface).is_dir():
        p.error("Interface chưa tồn tại; kiểm tra ip -br link và MAC card VMware")
    group=grp.getgrnam("Debian-snmp").gr_gid
    pwd.getpwnam("Debian-snmp")
    root=Path(__file__).resolve().parents[2]
    if CONFIG.exists() and not a.reconfigure:
        print("Giữ cấu hình agent hiện có; dùng --reconfigure để đổi bind/interface/community.")
    else:
        community=getpass.getpass("Nhập SNMP community riêng cho lab (sẽ nhập lại trên Windows): ")
        text=configuration(a.bind,a.allow,a.iface,community,a.port,a.temperature_source)
        was_active=subprocess.run(["systemctl","is-active","--quiet",SERVICE],check=False).returncode==0
        if was_active:
            subprocess.run(["systemctl","stop",SERVICE],check=True)
        try:
            # Fail before changing files if another service owns the selected socket.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.bind((a.bind,a.port))
        except OSError:
            if was_active:
                subprocess.run(["systemctl","start",SERVICE],check=True)
            raise
        CONFIG.parent.mkdir(parents=True,exist_ok=True)
        os.chown(CONFIG.parent,0,group)
        os.chmod(CONFIG.parent,0o750)
        if CONFIG.exists():
            backup=CONFIG.parent/"backups"
            backup.mkdir(exist_ok=True,mode=0o700)
            shutil.copy2(CONFIG,backup/f"snmpd-{time.time_ns()}.conf")
        CONFIG.write_text(text)
        os.chown(CONFIG,0,group)
        os.chmod(CONFIG,0o640)
    DEST.mkdir(parents=True,exist_ok=True,mode=0o755)
    shutil.copytree(root/"device_monitor",DEST/"device_monitor",dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copy2(Path(__file__).with_name("linux_probe.py"),DEST/"linux_probe.py")
    for path in DEST.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
        elif path.suffix==".py":
            path.chmod(0o644)
    (Path("/etc/systemd/system")/SERVICE).write_text(UNIT)
    subprocess.run(["systemctl","daemon-reload"],check=True)
    subprocess.run(["systemctl","enable",SERVICE],check=True)
    subprocess.run(["systemctl","restart",SERVICE],check=True)
    subprocess.run(["systemctl","is-active","--quiet",SERVICE],check=True)
    print("Agent riêng đã hoạt động. Không thay /etc/snmp/snmpd.conf của dịch vụ khác.")
    print("Kiểm tra: sudo systemctl status qtmnc-lab-snmp --no-pager")
    print("SNMPv2c không mã hóa: chỉ dùng trên mạng lab tách biệt; không chia sẻ community.")


if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as exc:
        print(f"Chưa cài được agent ({type(exc).__name__}); kiểm tra IP/interface, port, gói snmpd và quyền sudo.",file=sys.stderr)
        raise SystemExit(2)
