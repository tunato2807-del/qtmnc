#!/usr/bin/env python3
"""Cấu hình HAI FULL CLONE Ubuntu cho mô hình mới; mặc định chỉ xem kế hoạch."""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def netplan(role, macs):
    devices = {"mgmt0": {"addresses": ["192.168.73.10/24"], "routes": [{"to": "default", "via": "192.168.73.2"}], "nameservers": {"addresses": ["192.168.73.2"]}},
               "srv0": {"addresses": ["10.10.10.1/24"]}, "users0": {"addresses": ["10.20.20.1/24"]}} if role == "router" else {
               "lan0": {"addresses": ["10.10.10.10/24"], "routes": [{"to": "default", "via": "10.10.10.1"}], "nameservers": {"addresses": ["192.168.73.2"]}}}
    for name, device in devices.items():
        device.update({"match": {"macaddress": macs[name]}, "set-name": name, "dhcp4": False, "dhcp6": False, "optional": True})
    # JSON là tập con của YAML, netplan đọc được; tránh phụ thuộc PyYAML.
    return json.dumps({"network": {"version": 2, "renderer": "networkd", "ethernets": devices}}, indent=2) + "\n"


NFT = """flush table inet netwatch_router
table inet netwatch_router {
 chain forward {
  type filter hook forward priority 0; policy accept;
  ct state established,related accept
  iifname "users0" oifname "srv0" tcp dport 22 reject
  iifname "users0" oifname "srv0" udp dport 161 reject
 }
 chain postrouting {
  type nat hook postrouting priority srcnat; policy accept;
  ip saddr { 10.10.10.0/24, 10.20.20.0/24 } oifname "mgmt0" masquerade
 }
}
"""
UNIT = """[Unit]
Description=NetWatch lab routing rules
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=-/usr/sbin/nft add table inet netwatch_router
ExecStart=/usr/sbin/nft -f /etc/netwatch/router.nft
ExecStop=-/usr/sbin/nft delete table inet netwatch_router
[Install]
WantedBy=multi-user.target
"""


def plan(role, macs):
    result = {"/etc/netplan/90-netwatch.yaml": netplan(role, macs),
              "/etc/sysctl.d/90-netwatch.conf": "net.ipv4.ip_forward=" + ("1" if role == "router" else "0") + "\n",
              "/etc/ssh/sshd_config.d/00-netwatch.conf": "PasswordAuthentication yes\nPermitRootLogin no\n",
              "/etc/netwatch/role": role + "\n"}
    if role == "router":
        result.update({"/etc/netwatch/router.nft": NFT, "/etc/systemd/system/netwatch-router.service": UNIT})
    return result


def run(*args):
    subprocess.run(args, check=True)


def apply(role, macs):
    if os.geteuid() != 0:
        raise ValueError("Chạy sudo trong console Ubuntu của FULL CLONE")
    for tool in ("netplan", "ssh-keygen", "sshd", "systemctl", "nft"):
        if not shutil.which(tool):
            raise ValueError("Thiếu " + tool + "; cài các gói theo docs/01_GNS3.md trước")
    if shutil.which("ufw"):
        ufw = subprocess.run(["ufw", "status"], capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"})
        if ufw.returncode != 0 or ufw.stdout.startswith("Status: active"):
            raise ValueError("Cần xem lại trạng thái/chính sách UFW trước khi áp dụng lab")
    backup = Path("/root/netwatch-backups") / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True, mode=0o700)
    saved = backup / "netplan"
    saved.mkdir()
    for path in Path("/etc/netplan").glob("*.yaml"):
        shutil.copy2(path, saved / path.name)
    files = plan(role, macs)
    for name in files:
        path = Path(name)
        if path.exists():
            dest = backup / "files" / name.lstrip("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    (backup / "manifest.json").write_text(json.dumps(list(files)), encoding="utf-8")
    (backup / "restore.sh").write_text("""#!/bin/sh
set -eu
cd "$(dirname "$0")"
systemctl disable --now netwatch-router.service 2>/dev/null || true
rm -f /etc/netplan/*.yaml
cp -a netplan/. /etc/netplan/
python3 - <<'PY'
import json,pathlib,shutil
for name in json.loads(pathlib.Path('manifest.json').read_text()):
    old=pathlib.Path('files')/name.lstrip('/')
    target=pathlib.Path(name)
    if old.exists():shutil.copy2(old,target)
    else:target.unlink(missing_ok=True)
PY
if [ -d ssh_keys ]; then cp -a ssh_keys/. /etc/ssh/; fi
sysctl --system
systemctl daemon-reload
netplan generate
netplan apply
systemctl restart ssh
echo 'Đã phục hồi file; kiểm tra lại dịch vụ và đường mạng tại console.'
""", encoding="utf-8")
    try:
        subprocess.run(["id", "monitor"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        run("useradd", "--create-home", "--shell", "/bin/bash", "monitor")
        print("Đặt mật khẩu cho tài khoản giám sát monitor:", flush=True)
        run("passwd", "monitor")
    # Xóa host key sao chép chỉ ở lần provision đầu trên từng full clone.
    if not Path("/etc/netwatch/role").exists():
        keys = backup / "ssh_keys"
        keys.mkdir()
        for key in Path("/etc/ssh").glob("ssh_host_*key*"):
            shutil.move(str(key), str(keys / key.name))
        run("ssh-keygen", "-A")
    for path in Path("/etc/netplan").glob("*.yaml"):
        path.unlink()
    for name, content in files.items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600 if "netplan/" in name else 0o644)
    helper = Path("/opt/netwatch/probe.py")
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).with_name("probe.py"), helper)
    helper.chmod(0o755)
    run("netplan", "generate")
    run("/usr/sbin/sshd", "-t")
    run("systemctl", "enable", "--now", "systemd-networkd", "ssh")
    run("systemctl", "restart", "ssh")
    run("sysctl", "--system")
    run("systemctl", "daemon-reload")
    if role == "router":
        run("systemctl", "enable", "--now", "netwatch-router.service")
    print("Backup:", backup)
    print("Tiếp theo netplan try: nhấn ENTER khi cấu hình hoạt động. Sau đó reboot để đổi tên cổng theo MAC.", flush=True)
    run("netplan", "try", "--timeout", "120")
    print("Xác minh host key tại console:", flush=True)
    run("ssh-keygen", "-lf", "/etc/ssh/ssh_host_ed25519_key.pub")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("router", "server"))
    parser.add_argument("--management-iface")
    parser.add_argument("--server-iface", required=True)
    parser.add_argument("--user-iface")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cloned-vm", action="store_true", help="Xác nhận đây là full clone dành riêng cho lab mới")
    args = parser.parse_args()
    names = {"mgmt0": args.management_iface, "srv0": args.server_iface, "users0": args.user_iface} if args.role == "router" else {"lan0": args.server_iface}
    try:
        if None in names.values() or len(set(names.values())) != len(names):
            raise ValueError("Router cần ba interface khác nhau; đối chiếu MAC với VMware")
        macs = {}
        for alias, name in names.items():
            if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,32}", name) or name == "lo":
                raise ValueError("Tên interface không hợp lệ")
            macs[alias] = (Path("/sys/class/net") / name / "address").read_text().strip()
        if not args.apply:
            print(json.dumps(plan(args.role, macs), ensure_ascii=False, indent=2))
            print("Chỉ xem kế hoạch. Thêm --apply --cloned-vm khi đã đối chiếu đúng ba MAC trên clone.")
        else:
            if not args.cloned_vm:
                raise ValueError("Chỉ áp dụng trên clone dành riêng; cần --cloned-vm")
            apply(args.role, macs)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Chưa hoàn tất: {exc}\nDùng console Ubuntu để kiểm tra; có backup tại /root/netwatch-backups nếu đã bắt đầu áp dụng.\n")


if __name__ == "__main__":
    main()
