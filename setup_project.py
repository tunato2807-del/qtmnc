#!/usr/bin/env python3
"""Install dependencies, configure a local SSH profile and verify its host key."""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import os
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


def configure(path):
    from dotenv import dotenv_values
    from monitor_ssh import Config, ConfigError
    path = Path(path)
    source = path if path.exists() else ROOT / "examples/windows-to-linux.env"
    saved = {k: v for k, v in dotenv_values(source, interpolate=False, encoding="utf-8-sig").items() if v is not None}
    if saved.get("MONITOR_PROTOCOL", "ssh") != "ssh":
        raise SetupError("Bộ hướng dẫn này dành cho SSH; hãy giữ/chỉnh profile SNMP riêng")
    values = dict(saved)
    print("\nBộ cài SSH. Mặc định: Windows chạy Python giám sát Linux VM.")
    print("Secret chỉ lưu cục bộ trong .env; không gửi lên GitHub.")
    values["MONITOR_PROTOCOL"] = "ssh"
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
    if target == "windows":
        values["MONITOR_TEMP_PATH"] = ""
    auth_default = "key" if saved.get("SSH_KEY_FILE") else ("password" if saved.get("SSH_PASSWORD") or not path.exists() else "agent")
    auth = ask("Xác thực SSH: password/key/agent", auth_default).lower()
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
            entered = input("Dán fingerprint SHA256 lấy trực tiếp từ máy đích (bỏ trống để dừng): ").strip()
            if entered != fingerprint:
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


def install_dependencies(root=ROOT):
    root = Path(root)
    directory = root / ".venv"
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if directory.exists() and not python.is_file():
        raise SetupError(".venv đã tồn tại nhưng không hợp lệ; hãy kiểm tra thư mục trước khi tiếp tục")
    if not directory.exists():
        print("Đang tạo môi trường Python .venv...")
        venv.EnvBuilder(with_pip=True).create(directory)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True, cwd=root)
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true", help="Chỉnh lại cấu hình đã lưu")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--skip-ssh-check", action="store_true", help="Chỉ chuẩn bị cấu hình; chưa xác minh SSH")
    parser.add_argument("--finish", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("Cần Python 3.10 trở lên.", file=sys.stderr)
        return 2
    try:
        if not args.finish:
            python = install_dependencies()
            command = [str(python), str(ROOT / "setup_project.py"), "--finish", "--env-file", str(args.env_file.absolute())]
            if args.configure:
                command.append("--configure")
            if args.skip_ssh_check:
                command.append("--skip-ssh-check")
            return subprocess.call(command, cwd=ROOT)
        if args.configure or not args.env_file.exists():
            configure(args.env_file)
        else:
            print("Giữ cấu hình đã có. Dùng --configure nếu muốn thay đổi.")
        from monitor_ssh import Config, ConfigError, load_environment_file
        try:
            load_environment_file(args.env_file)
            config = Config.from_env()
        except ConfigError as exc:
            raise SetupError(str(exc)) from None
        if config.protocol != "ssh":
            raise SetupError("Bộ cài này dành cho SSH; profile SNMP được giữ nguyên")
        if not args.skip_ssh_check:
            verify_ssh(config)
            subprocess.run([sys.executable, str(ROOT / "monitor_ssh.py"), "--env-file", str(args.env_file), "--check-config"], check=True, cwd=ROOT)
        else:
            print("Chưa kiểm tra kết nối, host key hoặc đăng nhập SSH.")
        print("\nĐã hoàn tất bước chuẩn bị. Trên Windows chạy: .\\run_windows.cmd")
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
