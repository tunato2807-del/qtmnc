"""Đo ICMP và HTTP độc lập với vòng lấy CPU/RAM; không cần scapy/admin Windows."""
import base64
import ipaddress
import json
import math
import platform
import re
import subprocess
import time

import requests


def parse_linux_ping(output, count):
    counters = re.search(r"(\d+) packets transmitted,\s*(\d+) (?:packets )?received", output)
    if not counters:
        return {"sent": count, "received": None, "packet_loss_pct": None, "rtt_avg_ms": None, "error": "Không phân tích được kết quả ping"}
    sent, received = map(int, counters.groups())
    if sent != count or not 0 <= received <= sent:
        raise ValueError("Bộ đếm ping không hợp lệ")
    timing = re.search(r"(?:rtt|round-trip) min/avg/max/\S+\s*=\s*[\d.]+/([\d.]+)/", output)
    average = float(timing[1]) if timing and received else None
    if average is not None and (not math.isfinite(average) or average < 0):
        raise ValueError("RTT không hợp lệ")
    return {"sent": sent, "received": received, "packet_loss_pct": round(100 * (sent - received) / sent, 2), "rtt_avg_ms": average, "error": ""}


def ping_target(host, count=10, timeout_ms=1000):
    host = str(ipaddress.IPv4Address(host))
    if not 1 <= count <= 20 or not 100 <= timeout_ms <= 3000:
        raise ValueError("Giới hạn phép đo ping không hợp lệ")
    unknown = {"kind": "ping", "host": host, "sent": count, "received": None, "packet_loss_pct": None, "rtt_avg_ms": None}
    try:
        if platform.system() == "Windows":
            # .NET trả số liệu có cấu trúc, không lệ thuộc ngôn ngữ của ping.exe.
            script = f"""$ErrorActionPreference='Stop'; $p=New-Object System.Net.NetworkInformation.Ping; $times=@();
try {{ for($i=0;$i -lt {count};$i++) {{
try {{ $r=$p.Send('{host}',{timeout_ms}); if($r.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {{$times += [double]$r.RoundtripTime}} }} catch {{}}
}}; $avg=$null; if($times.Count -gt 0) {{$avg=($times | Measure-Object -Average).Average}};
@{{sent={count};received=$times.Count;packet_loss_pct=(100.0*({count}-$times.Count)/{count});rtt_avg_ms=$avg;error=''}} | ConvertTo-Json -Compress
}} finally {{$p.Dispose()}}"""
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], capture_output=True, text=True, timeout=count * timeout_ms / 1000 + 8, check=False)
            if result.returncode != 0:
                raise ValueError("Ping PowerShell thất bại")
            value = json.loads(result.stdout)
            sent, received = value.get("sent"), value.get("received")
            avg = value.get("rtt_avg_ms")
            if sent != count or not isinstance(received, int) or not 0 <= received <= count or (avg is not None and (not isinstance(avg, (int, float)) or not math.isfinite(avg) or avg < 0)):
                raise ValueError("Kết quả ping không hợp lệ")
            sample = {"sent": count, "received": received, "packet_loss_pct": round(100 * (count - received) / count, 2), "rtt_avg_ms": avg if received else None, "error": ""}
        else:
            import os
            result = subprocess.run(["ping", "-n", "-c", str(count), "-i", "0.2", "-W", str(max(1, math.ceil(timeout_ms / 1000))), host],
                                    capture_output=True, text=True, timeout=count * (timeout_ms / 1000 + 1) + 5, env={**os.environ, "LC_ALL": "C"}, check=False)
            # Kể cả exit code=1 vẫn phân tích stdout để giữ tỷ lệ mất gói một phần.
            sample = parse_linux_ping(result.stdout, count)
        return {"kind": "ping", "host": host, **sample}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return {**unknown, "error": "Chưa đo được ICMP; kiểm tra công cụ ping và quyền chạy"}


def http_target(url, timeout=5, session=None):
    client = session or requests
    start = time.monotonic()
    try:
        # Không theo redirect: yêu cầu bài thực hành là HTTP status phải bằng 200.
        response = client.get(url, timeout=timeout, allow_redirects=False, stream=True)
        try:
            return {"kind": "http", "status_code": response.status_code, "response_ms": round((time.monotonic() - start) * 1000, 2), "error": ""}
        finally:
            response.close()
    except requests.RequestException as exc:
        # Không ghi URL/headers hoặc nội dung lỗi có thể mang thông tin nhạy cảm.
        return {"kind": "http", "status_code": None, "response_ms": None, "error": f"Không truy cập được HTTP ({type(exc).__name__})"}


def verdict(sample, checks):
    if sample["kind"] == "ping":
        loss, rtt = sample.get("packet_loss_pct"), sample.get("rtt_avg_ms")
        if loss is None:
            return None, sample.get("error") or "Chưa có kết quả ICMP"
        if sample.get("received") == 0:
            return False, "Không có ICMP Echo Reply; chưa đủ kết luận SSH/HTTP cũng mất"
        passed = loss <= checks["packet_loss_pct"] and rtt is not None and rtt <= checks["latency_ms"]
        return passed, f"RTT {rtt:.2f} ms; mất gói {loss:.1f}%" if rtt is not None else f"Mất gói {loss:.1f}%; chưa có RTT"
    status, elapsed = sample.get("status_code"), sample.get("response_ms")
    if status is None:
        return False, sample.get("error") or "Không truy cập được HTTP"
    return status == 200 and elapsed is not None and elapsed <= checks["http_slow_seconds"] * 1000, f"HTTP {status}; {elapsed:.1f} ms" if elapsed is not None else f"HTTP {status}; chưa có thời gian đáp ứng"
