from __future__ import annotations

import base64
import json
from pathlib import Path
import shlex
import time
from ..errors import ConfigError, DataError, DeviceUnavailable
from ..validation import number
from ..models import Sample

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
                cmd = "cat /var/lib/qtmnc-lab/temperature.json" if self.c.temp_source == "demo" else "cat " + shlex.quote(self.c.temp_path) if self.c.temp_path else self.TEMP_CMD

                def parse_temp(raw):
                    if self.c.temp_source == "demo":
                        try:
                            data=json.loads(raw)
                            expires=number(data.get("expires_at"),0)
                            return number(data.get("celsius") if expires > time.time() else data.get("baseline",40),-50,200)
                        except (ValueError,TypeError,AttributeError):
                            raise DataError("File nhiệt độ MÔ PHỎNG không hợp lệ") from None
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
            sources={key:"SSH" for key in values}
            if "temp" in sources and self.c.temp_source == "demo":
                sources["temp"]="SSH / DEMO"
            return Sample(values, errors, sources)
        finally:
            ssh.close()
