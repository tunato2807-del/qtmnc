from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from .errors import ConfigError, DataError
from .validation import number, env_number, env_bool

ROOT = Path(__file__).resolve().parent.parent

def load_environment_file(path=None):
    """Load local settings as data, without shell execution or variable expansion."""
    file = Path(path).expanduser().resolve() if path else ROOT / ".env"
    if path and not file.is_file():
        raise ConfigError("Không tìm thấy file cấu hình --env-file")
    if file.is_file():
        from dotenv import load_dotenv
        # An explicitly selected profile wins over inherited terminal variables.
        # With the default .env, intentional command-level env overrides still work.
        load_dotenv(file, override=path is not None, interpolate=False, encoding="utf-8-sig")


@dataclass
class Config:
    host: str
    protocol: str = "ssh"
    target_os: str = "linux"
    interval: float = 30
    timeout: float = 10
    thresholds: dict = field(default_factory=lambda: {"cpu": 75., "ram": 65., "temp": 65.})
    recovery_margin: float = 5
    temp_enabled: bool = True
    iface: str = "ens33"
    state_file: Path = field(default_factory=lambda: ROOT / ".monitor_state/state.sqlite3")
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = field(default="", repr=False)
    ssh_key: str = ""
    known_hosts: str = "~/.ssh/known_hosts"
    temp_path: str = ""
    temp_source: str = "auto"
    snmp_profile: str = "custom"
    snmp_extend_oid: str = "1.3.6.1.4.1.8072.1.3.2.3.1.2.5.113.116.109.110.99"
    snmp_port: int = 161
    snmp_version: str = "3"
    snmp_community: str = field(default="", repr=False)
    snmp_user: str = ""
    snmp_auth_key: str = field(default="", repr=False)
    snmp_priv_key: str = field(default="", repr=False)
    oids: dict = field(default_factory=dict)
    temp_scale: float = 1
    telegram_token: str = field(default="", repr=False)
    telegram_chat: str = ""
    slack_webhook: str = field(default="", repr=False)

    @property
    def device_key(self):
        port = self.ssh_port if self.protocol == "ssh" else self.snmp_port
        identity = [self.protocol, self.host, port, self.iface, self.oids]
        if self.target_os != "linux":
            identity.append(self.target_os)
        if self.temp_source != "auto":
            identity.append(self.temp_source)
        if self.snmp_profile != "custom":
            identity.append(self.snmp_profile)
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        host = e.get("MONITOR_HOST", "").strip()
        if not host or not re.fullmatch(r"[A-Za-z0-9_.:\-]+", host):
            raise ConfigError("Cần MONITOR_HOST là IP hoặc hostname hợp lệ")
        c = cls(host=host)
        c.protocol = e.get("MONITOR_PROTOCOL", "ssh").lower()
        if c.protocol not in {"ssh", "snmp", "hybrid"}:
            raise ConfigError("MONITOR_PROTOCOL phải là ssh, snmp hoặc hybrid")
        c.target_os = e.get("MONITOR_OS", "linux").lower()
        if c.target_os not in {"linux", "windows"}:
            raise ConfigError("MONITOR_OS phải là linux hoặc windows")
        c.interval = env_number(e, "MONITOR_INTERVAL", 30, 1, 86400)
        c.timeout = env_number(e, "MONITOR_TIMEOUT", 10, 1, 120)
        c.recovery_margin = env_number(e, "RECOVERY_MARGIN", 5, 0, 50)
        c.temp_enabled = env_bool(e, "MONITOR_TEMP_ENABLED")
        for metric, default in c.thresholds.items():
            c.thresholds[metric] = env_number(e, f"{metric.upper()}_THRESHOLD", default, 0, 200 if metric == "temp" else 100)
            if c.recovery_margin > c.thresholds[metric]:
                raise ConfigError("RECOVERY_MARGIN không được lớn hơn ngưỡng cảnh báo")
        c.iface = e.get("MONITOR_IFACE", "Wi-Fi" if c.target_os == "windows" else "ens33")
        iface_pattern = r"[^\x00-\x1f\x7f]{1,128}" if c.target_os == "windows" else r"[A-Za-z0-9_.:@\-]{1,64}"
        if not re.fullmatch(iface_pattern, c.iface):
            raise ConfigError("MONITOR_IFACE không hợp lệ")
        c.state_file = Path(e.get("MONITOR_STATE_FILE", str(c.state_file))).expanduser().resolve()
        c.ssh_port = cls.port(e, "SSH_PORT", 22)
        c.ssh_user = e.get("SSH_USER", "")
        c.ssh_password = e.get("SSH_PASSWORD", "")
        c.ssh_key = e.get("SSH_KEY_FILE", "")
        c.known_hosts = e.get("SSH_KNOWN_HOSTS", "~/.ssh/known_hosts")
        c.temp_path = e.get("MONITOR_TEMP_PATH", "")
        c.temp_source = e.get("TEMP_SOURCE", "auto").lower()
        if c.temp_source not in {"auto", "demo"}:
            raise ConfigError("TEMP_SOURCE phải là auto (cảm biến thật) hoặc demo (mô phỏng có nhãn)")
        if c.target_os == "windows" and c.temp_source == "demo":
            raise ConfigError("Nguồn nhiệt độ demo dành cho Linux lab")
        if c.target_os == "windows" and c.temp_path:
            raise ConfigError("MONITOR_TEMP_PATH chỉ dành cho cảm biến Linux")
        if c.temp_path and (not c.temp_path.startswith("/sys/") or ".." in Path(c.temp_path).parts or not re.fullmatch(r"[/A-Za-z0-9_.:\-]+", c.temp_path)):
            raise ConfigError("MONITOR_TEMP_PATH phải là đường dẫn cảm biến bên dưới /sys/")
        c.snmp_port = cls.port(e, "SNMP_PORT", 161)
        c.snmp_version = e.get("SNMP_VERSION", "3")
        c.snmp_profile = e.get("SNMP_PROFILE", "custom")
        if c.snmp_profile not in {"custom", "linux-extend"}:
            raise ConfigError("SNMP_PROFILE phải là custom hoặc linux-extend")
        c.snmp_extend_oid = e.get("SNMP_EXTEND_OID", c.snmp_extend_oid).lstrip(".")
        if not re.fullmatch(r"\d+(?:\.\d+)+", c.snmp_extend_oid):
            raise ConfigError("SNMP_EXTEND_OID phải là OID số")
        c.snmp_community = e.get("SNMP_COMMUNITY", "")
        c.snmp_user = e.get("SNMP_USER", "")
        c.snmp_auth_key = e.get("SNMP_AUTH_KEY", "")
        c.snmp_priv_key = e.get("SNMP_PRIV_KEY", "")
        c.temp_scale = env_number(e, "SNMP_TEMP_SCALE", 1, 0.000001, 1000000)
        for name in ("cpu", "ram", "ram_used", "ram_total", "temp", "iface"):
            oid = e.get(f"SNMP_{name.upper()}_OID", "").lstrip(".")
            if oid:
                if not re.fullmatch(r"\d+(?:\.\d+)+", oid):
                    raise ConfigError(f"SNMP_{name.upper()}_OID phải là OID dạng số")
                c.oids[name] = oid
        if c.protocol in {"ssh", "hybrid"}:
            if not c.ssh_user:
                raise ConfigError("Cần SSH_USER")
        if c.protocol in {"snmp", "hybrid"}:
            if c.snmp_version == "3":
                if not all((c.snmp_user, c.snmp_auth_key, c.snmp_priv_key)):
                    raise ConfigError("SNMPv3 cần SNMP_USER, SNMP_AUTH_KEY và SNMP_PRIV_KEY (authPriv)")
                if min(len(c.snmp_auth_key), len(c.snmp_priv_key)) < 8:
                    raise ConfigError("Khóa SNMPv3 cần ít nhất 8 ký tự")
            elif c.snmp_version == "2c":
                if not c.snmp_community:
                    raise ConfigError("SNMPv2c cần SNMP_COMMUNITY")
            else:
                raise ConfigError("SNMP_VERSION chỉ hỗ trợ 3 hoặc 2c")
            if c.snmp_profile == "custom" and (not c.oids.get("cpu") or not c.oids.get("iface") or not (
                c.oids.get("ram") or (c.oids.get("ram_used") and c.oids.get("ram_total"))
            )):
                raise ConfigError("SNMP cần OID CPU (%), interface và RAM (% hoặc used + total)")
        c.telegram_token = e.get("TELEGRAM_TOKEN", "")
        c.telegram_chat = e.get("TELEGRAM_CHAT_ID", "")
        c.slack_webhook = e.get("SLACK_WEBHOOK_URL", "")
        if bool(c.telegram_token) != bool(c.telegram_chat):
            raise ConfigError("Cần cả TELEGRAM_TOKEN và TELEGRAM_CHAT_ID")
        if c.telegram_token and not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", c.telegram_token):
            raise ConfigError("TELEGRAM_TOKEN không đúng định dạng")
        if c.slack_webhook:
            url = urlsplit(c.slack_webhook)
            if url.scheme != "https" or url.netloc not in {"hooks.slack.com", "hooks.slack-gov.com"} or not url.path.startswith("/services/") or url.query or url.fragment:
                raise ConfigError("SLACK_WEBHOOK_URL phải là HTTPS Incoming Webhook chính thức của Slack")
        if not c.telegram_token and not c.slack_webhook:
            raise ConfigError("Cần cấu hình Telegram hoặc Slack để nhận cảnh báo")
        return c

    @staticmethod
    def port(env, name, default):
        value = env_number(env, name, default, 1, 65535)
        if value != int(value):
            raise ConfigError(f"{name} phải là số nguyên")
        return int(value)
