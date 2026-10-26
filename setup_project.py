#!/usr/bin/env python3
"""Install dependencies, configure a local SSH profile and verify its host key."""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parent


class SetupError(ValueError):
    """An actionable message composed locally, without library/credential text."""


def ask(label, default=""):
    value = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip()
    return value or default


def ask_secret(label, previous=""):
    note = " (Enter để giữ giá trị đã lưu)" if previous else ""
    return getpass.getpass(label + note + ": ") or previous

def choose(label,options,default):
    while True:
        value=ask(label,default).lower()
        if value in options:
            return value
        if value.isdigit() and 1<=int(value)<=len(options):
            return options[int(value)-1]
        print("Chỉ chọn: "+", ".join(options)+". Enter để giữ mặc định; mật khẩu nhập ở ô tiếp theo.")


def save_settings(path, updates):
    """Preserve comments/unknown keys; replace the complete file atomically."""
    from dotenv import set_key
    path = Path(path)
    if path.is_symlink():
        raise SetupError("File cấu hình là symlink; hãy chọn file thông thường")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".env.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            if path.exists():
                handle.write(path.read_text(encoding="utf-8-sig"))
        for key, value in updates.items():
            set_key(temporary, key, str(value), quote_mode="always", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def configure_simple(path):
    """Only ask what a first SSH lab needs; reuse locally saved secrets."""
    from dotenv import dotenv_values
    from device_monitor.config import Config, ConfigError
    path = Path(path)
    values = dict(dotenv_values(ROOT / "examples/simple.env", interpolate=False, encoding="utf-8-sig"))
    if path.exists():
        values.update({k: v for k, v in dotenv_values(path, interpolate=False, encoding="utf-8-sig").items() if v is not None})
    else:
        # Keep the new lab's host/interface defaults. Reuse only local credentials.
        keys = ("SSH_USER", "SSH_PASSWORD", "SSH_KNOWN_HOSTS",
                "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "SLACK_WEBHOOK_URL")
        for old in (ROOT / ".env", ROOT / ".env.gns3"):
            if old.is_file():
                saved = dotenv_values(old, interpolate=False, encoding="utf-8-sig")
                values.update({k: saved[k] for k in keys if saved.get(k)})
    values["MONITOR_PROTOCOL"], values["MONITOR_OS"] = "ssh", "linux"
    values["SSH_KEY_FILE"] = ""
    print("\nBản đơn giản: Windows -> GNS3 -> Linux, thu thập bằng SSH.")
    print(f"Mật khẩu/token chỉ lưu trên máy bạn trong {path.name}.")
    values["MONITOR_HOST"] = ask("IP Linux qua GNS3", values["MONITOR_HOST"])
    values["SSH_USER"] = ask("Tài khoản Linux", values["SSH_USER"])
    values["MONITOR_IFACE"] = ask("Card mạng cần xem trạng thái", values["MONITOR_IFACE"])
    values["SSH_PASSWORD"] = ask_secret("Mật khẩu Linux", values.get("SSH_PASSWORD", ""))
    if not values["SSH_PASSWORD"]:
        raise SetupError("Chưa nhập mật khẩu Linux")
    default = "both" if values.get("TELEGRAM_TOKEN") and values.get("SLACK_WEBHOOK_URL") else "slack" if values.get("SLACK_WEBHOOK_URL") else "telegram"
    channel = choose("Nhận tin: telegram/slack/both", ("telegram", "slack", "both"), default)
    if channel in {"telegram", "both"}:
        values["TELEGRAM_TOKEN"] = ask_secret("Token Telegram", values.get("TELEGRAM_TOKEN", ""))
        values["TELEGRAM_CHAT_ID"] = ask("Telegram chat ID", values.get("TELEGRAM_CHAT_ID", ""))
    else:
        values["TELEGRAM_TOKEN"] = values["TELEGRAM_CHAT_ID"] = ""
    values["SLACK_WEBHOOK_URL"] = ask_secret("Slack Webhook", values.get("SLACK_WEBHOOK_URL", "")) if channel in {"slack", "both"} else ""
    try:
        Config.from_env(values)
    except ConfigError as exc:
        raise SetupError(str(exc)) from None
    save_settings(path, values)
    print("Đã lưu cấu hình. Nhiệt độ VM thiếu cảm biến sẽ hiện KHÔNG XÁC ĐỊNH.")


def configure(path,preset=None):
    from dotenv import dotenv_values
    from monitor_ssh import Config, ConfigError
    path = Path(path)
    source = path if path.exists() else preset if preset is not None else ROOT / "examples/windows-to-linux.env"
    saved = {k: v for k, v in dotenv_values(source, interpolate=False, encoding="utf-8-sig").items() if v is not None}
    values = dict(saved)
    print("\nGNS3 Device Monitor: Windows/VS Code giám sát Linux qua SSH/SNMP.")
    print(f"Secret chỉ lưu cục bộ trong {path.name}; không gửi lên GitHub.")
    values["MONITOR_PROTOCOL"] = choose("Giao thức: ssh/snmp/hybrid",("ssh","snmp","hybrid"),saved.get("MONITOR_PROTOCOL","ssh"))
    target = ask("Hệ điều hành máy đích: linux/windows", saved.get("MONITOR_OS", "linux")).lower()
    if target not in {"linux", "windows"}:
        raise SetupError("Hệ điều hành phải là linux hoặc windows")
    values["MONITOR_OS"] = target
    values["MONITOR_HOST"] = ask("IP/hostname máy đích", saved.get("MONITOR_HOST", "192.168.73.129"))
    values["SSH_PORT"] = ask("Cổng SSH", saved.get("SSH_PORT", "22"))
    values["SSH_USER"] = ask("Tài khoản SSH", saved.get("SSH_USER", "tuanto"))
    values["MONITOR_IFACE"] = ask("Tên interface trên máy đích", saved.get("MONITOR_IFACE", "ens33" if target == "linux" else "Wi-Fi"))
    enabled = ask("Giám sát nhiệt độ? true/false", saved.get("MONITOR_TEMP_ENABLED", "false")).lower()
    values["MONITOR_TEMP_ENABLED"] = enabled
    if enabled=="true":
        values["TEMP_SOURCE"]=choose("Nguồn nhiệt độ: auto/demo (demo luôn ghi nhãn MÔ PHỎNG)",("auto","demo"),saved.get("TEMP_SOURCE","auto"))
    if target == "windows":
        values["MONITOR_TEMP_PATH"] = ""
    auth_default = "key" if saved.get("SSH_KEY_FILE") else ("password" if saved.get("SSH_PASSWORD") or not path.exists() else "agent")
    auth = choose("Xác thực SSH: password/key/agent",("password","key","agent"),auth_default) if values["MONITOR_PROTOCOL"]!="snmp" else "agent"
    if auth == "password":
        values["SSH_PASSWORD"] = ask_secret("Mật khẩu SSH", saved.get("SSH_PASSWORD", ""))
        if not values["SSH_PASSWORD"]:
            raise SetupError("Chưa nhập mật khẩu SSH")
        values["SSH_KEY_FILE"] = ""
    elif auth == "key":
        values["SSH_KEY_FILE"] = ask("Đường dẫn private key", saved.get("SSH_KEY_FILE", ""))
        if not Path(values["SSH_KEY_FILE"]).expanduser().is_file():
            raise SetupError("Private key không tồn tại")
        values["SSH_PASSWORD"] = ask_secret("Passphrase của key, bỏ trống nếu không có", saved.get("SSH_PASSWORD", ""))
    elif auth == "agent":
        values["SSH_PASSWORD"] = values["SSH_KEY_FILE"] = ""
    else:
        raise SetupError("Xác thực phải là password, key hoặc agent")
    values.setdefault("SSH_KNOWN_HOSTS", "~/.ssh/known_hosts")
    if values["MONITOR_PROTOCOL"] in {"snmp","hybrid"}:
        values["SNMP_PROFILE"]=saved.get("SNMP_PROFILE","linux-extend")
        values["SNMP_PORT"]=ask("Cổng SNMP",saved.get("SNMP_PORT","161"))
        values["SNMP_VERSION"]=choose("SNMP: 2c (lab tách biệt) / 3 (authPriv)",("2c","3"),saved.get("SNMP_VERSION","2c"))
        if values["SNMP_VERSION"]=="2c":
            values["SNMP_COMMUNITY"]=ask_secret("Community read-only đã cấu hình trên Linux",saved.get("SNMP_COMMUNITY",""))
        else:
            values["SNMP_USER"]=ask("SNMPv3 username",saved.get("SNMP_USER",""))
            values["SNMP_AUTH_KEY"]=ask_secret("SNMPv3 SHA auth key",saved.get("SNMP_AUTH_KEY",""))
            values["SNMP_PRIV_KEY"]=ask_secret("SNMPv3 AES privacy key",saved.get("SNMP_PRIV_KEY",""))
    has_tg, has_slack = bool(saved.get("TELEGRAM_TOKEN")), bool(saved.get("SLACK_WEBHOOK_URL"))
    default_channel = "both" if has_tg and has_slack else ("slack" if has_slack else "telegram")
    channel = ask("Kênh cảnh báo: telegram/slack/both", default_channel).lower()
    if channel not in {"telegram", "slack", "both"}:
        raise SetupError("Kênh cảnh báo không hợp lệ")
    if channel in {"telegram", "both"}:
        values["TELEGRAM_TOKEN"] = ask_secret("Token Telegram mới", saved.get("TELEGRAM_TOKEN", ""))
        values["TELEGRAM_CHAT_ID"] = ask("Telegram chat ID", saved.get("TELEGRAM_CHAT_ID", ""))
    else:
        values["TELEGRAM_TOKEN"] = values["TELEGRAM_CHAT_ID"] = ""
    values["SLACK_WEBHOOK_URL"] = ask_secret("Slack Incoming Webhook", saved.get("SLACK_WEBHOOK_URL", "")) if channel in {"slack", "both"} else ""
    try:
        Config.from_env(values)  # Validate before changing any existing settings.
    except ConfigError as exc:
        raise SetupError(str(exc)) from None
    save_settings(path, values)
    print("Đã lưu cấu hình cục bộ. Nội dung secret không được hiển thị.")


def verify_ssh(config):
    """Require an independently obtained fingerprint before adding an unknown key."""
    import paramiko
    known = Path(config.known_hosts).expanduser()
    ssh = paramiko.SSHClient()
    added = False

    class VerifiedFingerprint(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            nonlocal added
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
            print(f"\nSSH host: {hostname}; loại key: {key.get_name()}")
            print(f"Fingerprint nhận được: {fingerprint}")
            if config.target_os == "linux":
                print("Trên console Linux, chạy: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub")
                print("Nếu key trên đây không phải ED25519, kiểm tra file public key cùng loại trong /etc/ssh.")
            else:
                print("Lấy fingerprint đúng loại key trực tiếp trên Windows trong C:\\ProgramData\\ssh.")
            entered = input("Dán fingerprint hoặc cả dòng ssh-keygen lấy từ console Linux (bỏ trống để dừng): ").strip()
            found=re.findall(r"SHA256:[A-Za-z0-9+/]{43}=?",entered)
            if len(found)!=1 or found[0].rstrip("=") != fingerprint:
                raise paramiko.SSHException("Fingerprint chưa được xác minh")
            client.get_host_keys().add(hostname, key.get_name(), key)
            added = True

    try:
        ssh.load_system_host_keys()
        if known.is_file():
            ssh.load_host_keys(str(known))
        ssh.set_missing_host_key_policy(VerifiedFingerprint())
        ssh.connect(config.host, port=config.ssh_port, username=config.ssh_user,
                    password=config.ssh_password or None,
                    key_filename=str(Path(config.ssh_key).expanduser()) if config.ssh_key else None,
                    timeout=config.timeout, auth_timeout=config.timeout, banner_timeout=config.timeout,
                    allow_agent=not bool(config.ssh_password), look_for_keys=not bool(config.ssh_password))
        _, stdout, _ = ssh.exec_command("exit", timeout=config.timeout)
        stdout.read(1024)
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError("SSH shell không chạy được lệnh")
        if added:
            known.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temporary = tempfile.mkstemp(prefix=".known_hosts.", dir=known.parent)
            os.close(fd)
            try:
                ssh.save_host_keys(temporary)
                os.replace(temporary, known)
            finally:
                Path(temporary).unlink(missing_ok=True)
        print("Đã xác minh host key, đăng nhập SSH và thực thi lệnh thành công.")
    finally:
        ssh.close()


def install_dependencies(root=ROOT, requirements="requirements.txt"):
    root = Path(root)
    directory = root / ".venv"
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if directory.exists() and not python.is_file():
        raise SetupError(".venv đã tồn tại nhưng không hợp lệ; hãy kiểm tra thư mục trước khi tiếp tục")
    if not directory.exists():
        print("Đang tạo môi trường Python .venv...")
        venv.EnvBuilder(with_pip=True).create(directory)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(root / requirements)], check=True, cwd=root)
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true", help="Chỉnh lại cấu hình đã lưu")
    parser.add_argument("--profile", choices=("classic","gns3","simple"),default="classic")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--skip-ssh-check", action="store_true", help="Chỉ chuẩn bị cấu hình; chưa xác minh SSH")
    parser.add_argument("--finish", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.env_file is None:
        args.env_file=ROOT/{"classic":".env","gns3":".env.gns3","simple":".env.simple"}[args.profile]
    if sys.version_info < (3, 10):
        print("Cần Python 3.10 trở lên.", file=sys.stderr)
        return 2
    try:
        if not args.finish:
            python = install_dependencies(requirements="requirements-simple.txt" if args.profile=="simple" else "requirements.txt")
            command = [str(python), str(ROOT / "setup_project.py"), "--finish", "--profile",args.profile,"--env-file", str(args.env_file.absolute())]
            if args.configure:
                command.append("--configure")
            if args.skip_ssh_check:
                command.append("--skip-ssh-check")
            return subprocess.call(command, cwd=ROOT)
        if args.configure or not args.env_file.exists():
            if args.profile=="simple":
                configure_simple(args.env_file)
            else:
                configure(args.env_file,ROOT/"examples/gns3.env" if args.profile=="gns3" else None)
        else:
            print("Giữ cấu hình đã có. Dùng --configure nếu muốn thay đổi.")
        from monitor_ssh import Config, ConfigError, load_environment_file
        try:
            load_environment_file(args.env_file)
            config = Config.from_env()
        except ConfigError as exc:
            raise SetupError(str(exc)) from None
        if not args.skip_ssh_check:
            if config.protocol in {"ssh","hybrid"}:
                verify_ssh(config)
            subprocess.run([sys.executable, str(ROOT / "monitor_ssh.py"), "--env-file", str(args.env_file), "--check-config"], check=True, cwd=ROOT)
            if config.protocol in {"snmp","hybrid"}:
                print("Chưa đo thử SNMP. Chạy --once để kiểm tra agent, community/user và UDP thực tế.")
        else:
            print("Chưa kiểm tra kết nối, host key hoặc đăng nhập SSH.")
        if args.profile == "simple":
            print("\nĐã hoàn tất. Trên Windows chạy: .\\run_windows.cmd")
        else:
            print(f'\nĐã hoàn tất. Chạy: python -m device_monitor --env-file "{args.env_file}"')
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nĐã dừng cài đặt; giữ nguyên cấu hình đã lưu.", file=sys.stderr)
        return 130
    except SetupError as exc:
        print(f"Thiết lập chưa hoàn tất: {exc}. Dùng --configure để chỉnh cấu hình.", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"Lệnh cài đặt/kiểm tra không thành công (exit {exc.returncode}).", file=sys.stderr)
        return 2
    except Exception as exc:
        # Do not expose exception messages from SSH/HTTP libraries or credentials.
        print(f"Thiết lập chưa hoàn tất ({type(exc).__name__}). Kiểm tra Python/dependency, cấu hình, IP/cổng SSH và fingerprint.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
