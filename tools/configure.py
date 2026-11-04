#!/usr/bin/env python3
"""Nhập secret kín vào file cục bộ dành riêng cho dự án mới."""
import getpass
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from netwatch.config import load_inventory


def main():
    target = ROOT / ".env.netwatch"
    if not target.exists():
        shutil.copy2(ROOT / ".env.example", target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    existing = dotenv_values(target)
    print("Cấu hình mới: secret chỉ lưu .env.netwatch, không hiển thị và không đưa lên Git.")
    for device in load_inventory()["devices"]:
        prefix = device["credential_prefix"]
        if device["protocol"] == "ssh":
            key = prefix + "_SSH_USER"
            value = input(f"{device['name']} SSH user [{existing.get(key) or 'monitor'}]: ").strip()
            set_key(target, key, value or existing.get(key) or "monitor")
            value = getpass.getpass(f"{device['name']} mật khẩu (Enter giữ giá trị cũ): ")
            if value:
                set_key(target, prefix + "_SSH_PASSWORD", value)
        else:
            value = getpass.getpass(f"{device['name']} SNMP community (Enter giữ giá trị cũ): ")
            if value:
                set_key(target, prefix + "_SNMP_COMMUNITY", value)
    print("Kênh cảnh báo: 0=chỉ dashboard, 1=Telegram, 2=Slack, 3=cả hai")
    mode = input("Chọn [1]: ").strip() or "1"
    if mode not in ("0", "1", "2", "3"):
        raise SystemExit("Lựa chọn không hợp lệ; thông tin SSH vừa nhập đã lưu.")
    keys = ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "SLACK_WEBHOOK"]
    wanted = keys[:2] if mode == "1" else keys[2:] if mode == "2" else keys if mode == "3" else []
    for key in keys:
        if key not in wanted:
            set_key(target, key, "")
        else:
            value = getpass.getpass(key + " (Enter giữ giá trị cũ): ")
            if value:
                set_key(target, key, value)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print("Đã lưu. Tiếp theo: xác minh host key, rồi chạy start.cmd.")


if __name__ == "__main__":
    main()
