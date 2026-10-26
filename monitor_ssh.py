#!/usr/bin/env python3
"""Device monitoring over SSH/SNMP with a persistent Telegram/Slack outbox."""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import shlex
import sqlite3
import threading
import time
from urllib.parse import urlsplit

LOG = logging.getLogger("device_monitor")
METRIC_LABELS = {"cpu": "CPU", "ram": "RAM", "temp": "Nhiệt độ", "iface": "Interface"}


class ConfigError(ValueError):
    pass


class DataError(ValueError):
    pass


class DeviceUnavailable(Exception):
    pass


def number(value, minimum=None, maximum=None):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise DataError("Dữ liệu không phải số") from None
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (
        maximum is not None and result > maximum
    ):
        raise DataError("Giá trị nằm ngoài phạm vi hợp lệ")
    return result


def env_number(env, name, default, minimum, maximum):
    try:
        return number(env.get(name, default), minimum, maximum)
    except DataError:
        raise ConfigError(f"{name}: cần số trong khoảng {minimum}–{maximum}") from None


def env_bool(env, name, default=True):
    value = str(env.get(name, str(default))).lower()
    if value not in {"true", "false"}:
        raise ConfigError(f"{name}: chỉ nhận true hoặc false")
    return value == "true"


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
    state_file: Path = field(default_factory=lambda: Path(__file__).resolve().parent / ".monitor_state/state.sqlite3")
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = field(default="", repr=False)
    ssh_key: str = ""
    known_hosts: str = "~/.ssh/known_hosts"
    temp_path: str = ""
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
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        host = e.get("MONITOR_HOST", "").strip()
        if not host or not re.fullmatch(r"[A-Za-z0-9_.:\-]+", host):
            raise ConfigError("Cần MONITOR_HOST là IP hoặc hostname hợp lệ")
        c = cls(host=host)
        c.protocol = e.get("MONITOR_PROTOCOL", "ssh").lower()
        if c.protocol not in {"ssh", "snmp"}:
            raise ConfigError("MONITOR_PROTOCOL phải là ssh hoặc snmp")
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
        if c.target_os == "windows" and c.temp_path:
            raise ConfigError("MONITOR_TEMP_PATH chỉ dành cho cảm biến Linux")
        if c.temp_path and (not c.temp_path.startswith("/sys/") or ".." in Path(c.temp_path).parts or not re.fullmatch(r"[/A-Za-z0-9_.:\-]+", c.temp_path)):
            raise ConfigError("MONITOR_TEMP_PATH phải là đường dẫn cảm biến bên dưới /sys/")
        c.snmp_port = cls.port(e, "SNMP_PORT", 161)
        c.snmp_version = e.get("SNMP_VERSION", "3")
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
        if c.protocol == "ssh":
            if not c.ssh_user:
                raise ConfigError("Cần SSH_USER")
        else:
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
            if not c.oids.get("cpu") or not c.oids.get("iface") or not (
                c.oids.get("ram") or (c.oids.get("ram_used") and c.oids.get("ram_total"))
            ):
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


def cpu_percent(raw):
    rows = [line.split()[1:] for line in raw.splitlines() if line.startswith("cpu ")]
    if len(rows) != 2 or any(len(row) < 4 for row in rows):
        raise DataError("Không đọc được hai mẫu CPU từ /proc/stat")
    try:
        samples = [[int(v) for v in row[:8]] for row in rows]
    except ValueError:
        raise DataError("Bộ đếm CPU không hợp lệ") from None
    if len(samples[0]) != len(samples[1]):
        raise DataError("Hai mẫu CPU không cùng định dạng")
    delta = [b - a for a, b in zip(*samples)]
    if any(v < 0 for v in delta) or sum(delta) <= 0:
        raise DataError("Bộ đếm CPU bị reset hoặc không tiến triển")
    idle = delta[3] + (delta[4] if len(delta) > 4 else 0)
    return number(100 * (1 - idle / sum(delta)), 0, 100)


def ram_percent(raw):
    try:
        fields = {parts[0].rstrip(":"): int(parts[1]) for line in raw.splitlines() if len(parts := line.split()) >= 2}
        total = fields["MemTotal"]
        available = fields.get("MemAvailable")
        if available is None:
            available = fields["MemFree"] + fields["Buffers"] + fields["Cached"] + fields.get("SReclaimable", 0) - fields.get("Shmem", 0)
        if total <= 0 or not 0 <= available <= total:
            raise ValueError
        return number(100 * (total - available) / total, 0, 100)
    except (ValueError, KeyError):
        raise DataError("Không đọc được MemTotal/MemAvailable hợp lệ") from None


@dataclass
class Sample:
    values: dict
    errors: dict = field(default_factory=dict)


def windows_command(config):
    """An encoded command works with both Windows OpenSSH cmd and PowerShell shells."""
    script = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$r = @{values=@{}; errors=@{}}
try {
  $c = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
  if ($null -eq $c.PercentProcessorTime) { throw 'missing' }
  $r.values.cpu = [double]$c.PercentProcessorTime
} catch { $r.errors.cpu = 'CPU query failed or access denied' }
try {
  $m = Get-CimInstance Win32_OperatingSystem
  if ([double]$m.TotalVisibleMemorySize -le 0) { throw 'missing' }
  $r.values.ram = 100 * (1 - [double]$m.FreePhysicalMemory / [double]$m.TotalVisibleMemorySize)
} catch { $r.errors.ram = 'RAM query failed or access denied' }
try {
  $n = Get-NetAdapter -IncludeHidden | Where-Object { $_.Name -eq __IFACE__ } | Select-Object -First 1
  if ($null -eq $n) { throw 'missing' }
  $r.values.iface = switch ([string]$n.Status) {
    'Up' {'up'}
    'Disconnected' {'down'}
    'Disabled' {'down'}
    'Not Present' {'notpresent'}
    'LowerLayerDown' {'lowerlayerdown'}
    default {'unknown'}
  }
} catch { $r.errors.iface = 'Adapter missing or access denied' }
if (__TEMP__) {
  try {
    $hw = @(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Hardware |
      Where-Object { $_.HardwareType -eq 'Cpu' } | Select-Object -ExpandProperty Identifier)
    $t = @(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor |
      Where-Object { $_.SensorType -eq 'Temperature' -and $_.Parent -in $hw -and $null -ne $_.Value })
    if ($t.Count -eq 0) { throw 'missing' }
    $r.values.temp = [double](($t | Measure-Object -Property Value -Maximum).Maximum)
  } catch { $r.errors.temp = 'CPU sensor unavailable; LibreHardwareMonitor WMI required' }
}
$r | ConvertTo-Json -Compress -Depth 4
"""
    script = script.replace("__TEMP__", "$true" if config.temp_enabled else "$false")
    script = script.replace("__IFACE__", "'" + config.iface.replace("'", "''") + "'")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded


def windows_sample(raw, temp_enabled):
    try:
        data = json.loads(raw.lstrip("\ufeff"))
        if not isinstance(data, dict) or not isinstance(data.get("values"), dict):
            raise ValueError
    except (ValueError, TypeError):
        raise DataError("PowerShell không trả về JSON hợp lệ") from None
    values, errors = {}, {}
    metrics = ["cpu", "ram", "iface"] + (["temp"] if temp_enabled else [])
    for metric in metrics:
        try:
            value = data["values"].get(metric)
            if value is None:
                raise DataError("Không có dữ liệu hoặc không đủ quyền truy vấn Windows")
            if metric == "iface":
                if value not in {"up", "down", "lowerlayerdown", "notpresent", "unknown"}:
                    raise DataError("Trạng thái adapter Windows không hợp lệ")
            else:
                value = number(value, -50 if metric == "temp" else 0, 200 if metric == "temp" else 100)
            values[metric] = value
        except (DataError, TypeError) as exc:
            values[metric] = None
            errors[metric] = str(exc) if isinstance(exc, DataError) else "Dữ liệu Windows không hợp lệ"
    return Sample(values, errors)


class SSHCollector:
    CPU_CMD = "LC_ALL=C sh -c 'cat /proc/stat; sleep 1; cat /proc/stat'"
    TEMP_CMD = """LC_ALL=C sh -c '
for hw in /sys/class/hwmon/hwmon*; do
  name=$(cat "$hw/name" 2>/dev/null)
  case "$name" in coretemp|k10temp|zenpower|cpu_thermal)
    for file in "$hw"/temp*_input; do [ ! -r "$file" ] || cat "$file"; done;;
  esac
done
for zone in /sys/class/thermal/thermal_zone*; do
  kind=$(cat "$zone/type" 2>/dev/null)
  case "$kind" in x86_pkg_temp|cpu*|soc_thermal)
    [ ! -r "$zone/temp" ] || cat "$zone/temp";;
  esac
done
'"""

    def __init__(self, config):
        import paramiko
        self.c = config
        self.lib = paramiko
        self.known_hosts = Path(config.known_hosts).expanduser()
        if not self.known_hosts.is_file():
            raise ConfigError("Chưa có SSH_KNOWN_HOSTS; hãy thêm host key đã xác minh fingerprint")
        if config.ssh_key and not Path(config.ssh_key).expanduser().is_file():
            raise ConfigError("SSH_KEY_FILE không tồn tại")

    def collect(self):
        ssh = self.lib.SSHClient()
        try:
            ssh.load_system_host_keys()
            ssh.load_host_keys(str(self.known_hosts))
            ssh.set_missing_host_key_policy(self.lib.RejectPolicy())
            try:
                ssh.connect(self.c.host, port=self.c.ssh_port, username=self.c.ssh_user,
                            password=self.c.ssh_password or None,
                            key_filename=str(Path(self.c.ssh_key).expanduser()) if self.c.ssh_key else None,
                            timeout=self.c.timeout, auth_timeout=self.c.timeout,
                            banner_timeout=self.c.timeout,
                            allow_agent=not bool(self.c.ssh_password),
                            look_for_keys=not bool(self.c.ssh_password))
            except Exception as exc:
                # Libraries may include sensitive configuration in exception messages.
                raise DeviceUnavailable(f"Không kết nối/xác thực SSH được ({type(exc).__name__}); kiểm tra mạng, tài khoản và host key") from None

            def read(command):
                try:
                    _, stdout, stderr = ssh.exec_command(command, timeout=self.c.timeout)
                    raw = stdout.read(262145)
                    if len(raw) > 262144:
                        raise DataError("Đầu ra lệnh vượt giới hạn")
                    stderr.read(16384)
                    if stdout.channel.recv_exit_status() != 0:
                        raise DataError("Lệnh thu thập không thực thi thành công")
                    return raw.decode("utf-8", errors="replace").strip()
                except DataError:
                    raise
                except Exception as exc:
                    transport = ssh.get_transport()
                    if transport is None or not transport.is_active():
                        raise DeviceUnavailable("Mất kết nối SSH khi thu thập") from None
                    raise DataError(f"Không đọc được lệnh SSH ({type(exc).__name__})") from None

            if self.c.target_os == "windows":
                try:
                    return windows_sample(read(windows_command(self.c)), self.c.temp_enabled)
                except DataError as exc:
                    metrics = ["cpu", "ram", "iface"] + (["temp"] if self.c.temp_enabled else [])
                    return Sample({k: None for k in metrics}, {k: str(exc) for k in metrics})

            probes = {
                "cpu": (self.CPU_CMD, cpu_percent),
                "ram": ("cat /proc/meminfo", ram_percent),
                "iface": ("cat " + shlex.quote(f"/sys/class/net/{self.c.iface}/operstate"), lambda s: s.lower() if s else None),
            }
            if self.c.temp_enabled:
                cmd = "cat " + shlex.quote(self.c.temp_path) if self.c.temp_path else self.TEMP_CMD

                def parse_temp(raw):
                    if not raw:
                        raise DataError("Thiết bị không cung cấp cảm biến nhiệt độ CPU")
                    return max(number(line, -50000, 200000) / 1000 for line in raw.splitlines())

                probes["temp"] = (cmd, parse_temp)
            values, errors = {}, {}
            for metric, (command, parse) in probes.items():
                try:
                    values[metric] = parse(read(command))
                except DataError as exc:
                    values[metric] = None
                    errors[metric] = str(exc)
            return Sample(values, errors)
        finally:
            ssh.close()


class SNMPCollector:
    """Numeric OIDs must be selected from the monitored device's MIB documentation."""
    def __init__(self, config):
        from pysnmp.hlapi.v3arch import asyncio as api
        self.api, self.c = api, config

    async def _fetch(self):
        a, c = self.api, self.c
        engine = a.SnmpEngine()
        try:
            auth = (a.UsmUserData(c.snmp_user, c.snmp_auth_key, c.snmp_priv_key,
                                authProtocol=a.usmHMACSHAAuthProtocol,
                                privProtocol=a.usmAesCfb128Protocol)
                    if c.snmp_version == "3" else a.CommunityData(c.snmp_community, mpModel=1))
            target = await a.UdpTransportTarget.create((c.host, c.snmp_port), timeout=c.timeout, retries=1)
            requested = {k: v for k, v in c.oids.items() if c.temp_enabled or k != "temp"}
            # Numeric OIDs avoid runtime MIB downloads.
            indication, status, index, bindings = await a.get_cmd(
                engine, auth, target, a.ContextData(),
                *(a.ObjectType(a.ObjectIdentity(oid)) for oid in requested.values()), lookupMib=False)
            if indication:
                raise DeviceUnavailable("SNMP không phản hồi hoặc xác thực thất bại")
            if status:
                raise DataError("SNMP agent trả về lỗi truy vấn; kiểm tra quyền đọc và OID")
            if len(bindings) != len(requested):
                raise DeviceUnavailable("SNMP trả về thiếu varbind")
            return {name: binding[1].prettyPrint() for name, binding in zip(requested, bindings)}
        except (DeviceUnavailable, DataError):
            raise
        except Exception as exc:
            raise DeviceUnavailable(f"Không thu thập được SNMP ({type(exc).__name__})") from None
        finally:
            engine.close_dispatcher()

    def collect(self):
        metrics = ["cpu", "ram", "iface"] + (["temp"] if self.c.temp_enabled else [])
        try:
            raw = asyncio.run(self._fetch())
        except DataError as exc:
            # A responding agent rejecting a query is not a disconnected device.
            return Sample({metric: None for metric in metrics}, {metric: str(exc) for metric in metrics})
        values, errors = {}, {}
        for metric in metrics:
            try:
                if metric == "ram" and "ram" not in raw:
                    used, total = number(raw.get("ram_used"), 0), number(raw.get("ram_total"), 0)
                    if total <= 0:
                        raise DataError("Tổng RAM không hợp lệ")
                    value = number(100 * used / total, 0, 100)
                elif metric == "iface":
                    code = number(raw.get(metric), 1, 7)
                    if code != int(code):
                        raise DataError("ifOperStatus không hợp lệ")
                    value = {1: "up", 2: "down", 3: "testing", 4: "unknown", 5: "dormant", 6: "notpresent", 7: "lowerlayerdown"}[int(code)]
                elif metric == "temp":
                    value = number(number(raw.get(metric)) * self.c.temp_scale, -50, 200)
                else:
                    value = number(raw.get(metric), 0, 100)
                values[metric] = value
            except DataError as exc:
                values[metric], errors[metric] = None, str(exc)
        return Sample(values, errors)


def metric_state(metric, value, previous, config):
    if value is None:
        return "UNKNOWN"
    if metric == "iface":
        if value == "up":
            return "OK"
        return "ALERT" if value in {"down", "lowerlayerdown", "notpresent"} else "UNKNOWN"
    limit = config.thresholds[metric]
    if previous.get("last_known") == "ALERT":
        return "OK" if value <= limit - config.recovery_margin else "ALERT"
    return "ALERT" if value > limit else "OK"


class Store:
    """Observed states and all channel deliveries are committed in one transaction."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS states (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY, channel TEXT NOT NULL, message TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def observe(self, config, sample, channels, connection_error=None):
        key = config.device_key
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM states WHERE key=?", (key,)).fetchone()
            states = json.loads(row[0]) if row else {}
            messages = []
            connection = "DOWN" if connection_error else "UP"
            previous_connection = states.get("connection")
            if connection == "DOWN" and previous_connection != "DOWN":
                messages.append(f"❌ Mất kết nối {config.protocol.upper()}: {connection_error}")
            elif connection == "UP" and previous_connection == "DOWN":
                messages.append(f"✅ Đã khôi phục kết nối {config.protocol.upper()}")
            states["connection"] = connection
            if sample is not None:
                for metric, value in sample.values.items():
                    previous = states.get(metric, {})
                    status = metric_state(metric, value, previous, config)
                    if status != previous.get("status") and (previous or status != "OK"):
                        label = METRIC_LABELS[metric] + (f" ({config.iface})" if metric == "iface" else "")
                        detail = (str(value) if metric == "iface" else f"{value:.1f}{'°C' if metric == 'temp' else '%'}") if value is not None else "không có dữ liệu"
                        if status == "UNKNOWN":
                            messages.append(f"❓ {label}: KHÔNG XÁC ĐỊNH ({sample.errors.get(metric, detail)})")
                        elif status == "ALERT":
                            limit = "" if metric == "iface" else f"; ngưỡng > {config.thresholds[metric]:g}"
                            messages.append(f"🚨 {label}: CẢNH BÁO ({detail}{limit})")
                        elif previous.get("status") == "UNKNOWN":
                            messages.append(f"✅ {label}: đã có dữ liệu trở lại, bình thường ({detail})")
                        else:
                            messages.append(f"✅ {label}: đã bình thường ({detail})")
                    states[metric] = {"status": status, "last_known": previous.get("last_known") if status == "UNKNOWN" else status}
            if messages:
                body = f"Thiết bị: {config.host} [{config.protocol.upper()}]\n{time.strftime('%Y-%m-%d %H:%M:%S %z')}\n" + "\n".join(messages)
                for channel in channels:
                    db.execute("INSERT INTO outbox(channel,message) VALUES (?,?)", (channel, body))
            db.execute("INSERT INTO states(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(states)))
            return messages

    def due(self, channel, now):
        with self.connect() as db:
            # Preserve event order within a channel, including while backing off.
            row = db.execute("SELECT id,message,attempts,next_attempt FROM outbox WHERE channel=? ORDER BY id LIMIT 1", (channel,)).fetchone()
        return row if row and row[3] <= now else None

    def delivered(self, event_id):
        with self.connect() as db:
            db.execute("DELETE FROM outbox WHERE id=?", (event_id,))

    def failed(self, event_id, attempts, retry_after=None):
        delay = min(300, 2 ** min(attempts + 1, 9))
        if retry_after is not None:
            delay = max(delay, retry_after)
        with self.connect() as db:
            db.execute("UPDATE outbox SET attempts=attempts+1,next_attempt=? WHERE id=?", (time.time() + delay, event_id))


@dataclass
class Delivery:
    ok: bool
    reason: str = ""
    retry_after: float | None = None


class Channel:
    def __init__(self, kind, target, recipient="", session=None):
        self.kind, self.target, self.recipient = kind, target, recipient
        # Credentials may rotate. Keep pending deliveries attached to the recipient,
        # not the old secret. This application has one Slack destination per state file.
        self.key = "telegram:" + hashlib.sha256(recipient.encode()).hexdigest() if kind == "telegram" else "slack"
        if session is None:
            import requests
            session = requests.Session()
            # The persistent outbox manages retries, including POST and HTTP 429.
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        self.session = session

    def send(self, message):
        url = f"https://api.telegram.org/bot{self.target}/sendMessage" if self.kind == "telegram" else self.target
        payload = {"chat_id": self.recipient, "text": message} if self.kind == "telegram" else {"text": message, "mrkdwn": False}
        try:
            response = self.session.post(url, json=payload, timeout=(5, 10), allow_redirects=False)
            try:
                data = response.json() if self.kind == "telegram" else {}
            except ValueError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            if response.status_code == 429:
                params = data.get("parameters", {})
                raw = params.get("retry_after") if isinstance(params, dict) else None
                try:
                    retry_after = number(raw if raw is not None else response.headers.get("Retry-After", 30), 0)
                except DataError:
                    retry_after = 30
                return Delivery(False, "HTTP 429: giới hạn tần suất", retry_after)
            if not 200 <= response.status_code < 300:
                return Delivery(False, f"HTTP {response.status_code}")
            if self.kind == "telegram" and data.get("ok") is not True:
                return Delivery(False, "Telegram chưa xác nhận ok=true")
            if self.kind == "slack" and response.text.strip() != "ok":
                return Delivery(False, "Slack chưa xác nhận ok")
            return Delivery(True)
        except Exception as exc:
            # requests exceptions may expose the token/webhook through their URL.
            return Delivery(False, f"Lỗi gửi ({type(exc).__name__})")

    def close(self):
        self.session.close()


class Dispatcher:
    def __init__(self, store, channels):
        self.store, self.channels = store, channels

    def tick(self):
        failures = 0
        for channel in self.channels:
            event = self.store.due(channel.key, time.time())
            if event is None:
                continue
            event_id, message, attempts, _ = event
            result = channel.send(message)
            if result.ok:
                self.store.delivered(event_id)
                LOG.info("Đã gửi cảnh báo qua %s", channel.kind)
            else:
                self.store.failed(event_id, attempts, result.retry_after)
                LOG.warning("%s: %s; đã giữ cảnh báo để thử lại", channel.kind, result.reason)
                failures += 1
        return failures

    def run(self, stop):
        try:
            while not stop.is_set():
                self.tick()
                stop.wait(0.5)
        except Exception as exc:
            LOG.error("Luồng gửi cảnh báo dừng (%s); dừng chương trình để tránh mất giám sát", type(exc).__name__)
            stop.set()


def poll(collector, store, config, channels):
    try:
        sample = collector.collect()
    except DeviceUnavailable as exc:
        store.observe(config, None, channels, connection_error=str(exc))
        LOG.warning("%s", exc)
        return False
    store.observe(config, sample, channels)
    for metric, value in sample.values.items():
        LOG.info("%s=%s%s", metric, value if value is not None else "UNKNOWN", f" ({sample.errors[metric]})" if metric in sample.errors else "")
    return not sample.errors and all(metric_state(k, v, {}, config) != "UNKNOWN" for k, v in sample.values.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Thu thập một lần và thử gửi các cảnh báo đang đến hạn")
    parser.add_argument("--check-config", action="store_true", help="Kiểm tra cấu hình/dependency mà không kết nối thiết bị hay gửi tin")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    channels, worker = [], None
    stop = threading.Event()
    try:
        config = Config.from_env()
        collector = SSHCollector(config) if config.protocol == "ssh" else SNMPCollector(config)
        if config.telegram_token:
            channels.append(Channel("telegram", config.telegram_token, config.telegram_chat))
        if config.slack_webhook:
            channels.append(Channel("slack", config.slack_webhook))
        if args.check_config:
            LOG.info("Cấu hình và dependency hợp lệ; chưa kiểm tra kết nối hoặc gửi tin")
            return 0
        store = Store(config.state_file)
        dispatcher = Dispatcher(store, channels)
        keys = [c.key for c in channels]
        if args.once:
            healthy = poll(collector, store, config, keys)
            failed = dispatcher.tick()
            with store.connect() as db:
                pending = sum(db.execute("SELECT COUNT(*) FROM outbox WHERE channel=?", (key,)).fetchone()[0] for key in keys)
            return 0 if healthy and not failed and not pending else 1
        worker = threading.Thread(target=dispatcher.run, args=(stop,), name="notifications", daemon=True)
        worker.start()
        LOG.info("Giám sát %s qua %s mỗi %gs", config.host, config.protocol.upper(), config.interval)
        deadline = time.monotonic()
        while not stop.is_set():
            poll(collector, store, config, keys)
            deadline += config.interval
            now = time.monotonic()
            if deadline < now:
                LOG.warning("Chu kỳ thu thập vượt thời gian cấu hình; bỏ qua lịch đã trễ")
                deadline = now + config.interval
            stop.wait(max(0, deadline - now))
        return 1  # Worker failed; let a supervisor restart the monitor.
    except KeyboardInterrupt:
        LOG.info("Đã dừng giám sát; cảnh báo chưa gửi vẫn được lưu")
        return 0
    except (ConfigError, ImportError) as exc:
        LOG.error("%s", str(exc) if isinstance(exc, ConfigError) else "Thiếu dependency; xem requirements và README")
        return 2
    except Exception as exc:
        LOG.error("Lỗi nội bộ (%s); xem cấu hình, quyền ghi state và dependency", type(exc).__name__)
        return 2
    finally:
        stop.set()
        if worker:
            worker.join(timeout=35)
        if not worker or not worker.is_alive():
            for channel in channels:
                channel.close()


if __name__ == "__main__":
    raise SystemExit(main())
