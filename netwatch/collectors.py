import asyncio
import base64
import hashlib
import json
import os
import shlex
from pathlib import Path

import paramiko

from .config import ROOT, validate_sample

KNOWN_HOSTS = ROOT / ".local/known_hosts"
EXTEND_OID = "1.3.6.1.4.1.8072.1.3.2.3.1.2.8.110.101.116.119.97.116.99.104"


class CollectionError(Exception):
    def __init__(self, kind, detail):
        self.kind, self.detail = kind, detail
        super().__init__(detail)


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def enroll(host, expected, path=KNOWN_HOSTS):
    """Chỉ lưu key sau khi so khớp SHA256 lấy độc lập từ console Ubuntu."""
    import socket
    expected = expected.strip().split()[0] if expected.strip() else ""
    with socket.create_connection((host, 22), timeout=10) as sock:
        transport = paramiko.Transport(sock)
        try:
            transport.start_client(timeout=10)
            key = transport.get_remote_server_key()
            actual = fingerprint(key)
            if not expected or expected != actual:
                raise ValueError("Fingerprint không khớp; không lưu host key")
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            hosts = paramiko.HostKeys(str(path)) if path.exists() else paramiko.HostKeys()
            # Giữ các loại key khác; thay cùng loại chỉ khi đã xác minh trực tiếp.
            hosts.add(host, key.get_name(), key)
            hosts.save(str(path))
            try:
                path.chmod(0o600)
            except OSError:
                pass
            return actual
        finally:
            transport.close()


class SSHCollector:
    def __init__(self, device, timeout, known_hosts=KNOWN_HOSTS, port=22):
        self.device, self.timeout, self.known_hosts = device, timeout, Path(known_hosts)
        self.port = port
        self.client = None

    def close(self):
        if self.client:
            self.client.close()
        self.client = None

    def collect(self):
        d = self.device
        prefix = d["credential_prefix"]
        try:
            transport = self.client.get_transport() if self.client else None
            if not transport or not transport.is_active() or not transport.is_authenticated():
                self.close()
                if not self.known_hosts.exists():
                    raise CollectionError("offline", "Chưa xác minh host key; chạy python -m netwatch trust")
                password = os.getenv(prefix + "_SSH_PASSWORD")
                if not password:
                    raise CollectionError("offline", "Thiếu mật khẩu trong .env.netwatch")
                client = paramiko.SSHClient()
                self.client = client
                client.load_host_keys(str(self.known_hosts))
                client.set_missing_host_key_policy(paramiko.RejectPolicy())
                client.connect(d["host"], port=self.port, username=os.getenv(prefix + "_SSH_USER", "monitor"), password=password,
                               timeout=self.timeout, auth_timeout=self.timeout, banner_timeout=self.timeout,
                               allow_agent=False, look_for_keys=False)
                client.get_transport().set_keepalive(20)
            command = "/usr/bin/python3 /opt/netwatch/probe.py --interfaces " + " ".join(shlex.quote(i) for i in d["interfaces"])
            _, stdout, stderr = self.client.exec_command(command, timeout=self.timeout, get_pty=False)
            try:
                payload = stdout.read(65537)
                if len(payload) > 65536:
                    raise ValueError("Probe quá dài")
                if stdout.channel.recv_exit_status() != 0:
                    raise ValueError("Probe thất bại")
                return validate_sample(json.loads(payload), d["interfaces"])
            finally:
                stdout.channel.close()
        except CollectionError:
            self.close()
            raise
        except (ValueError, json.JSONDecodeError):
            raise CollectionError("unknown", "Probe không trả JSON hợp lệ; kiểm tra /opt/netwatch/probe.py") from None
        except Exception as exc:
            self.close()
            # Không đưa repr(exception), URL, username/password vào log/dashboard.
            raise CollectionError("offline", f"Lỗi SSH ({type(exc).__name__}); kiểm tra tuyến, host key và tài khoản") from None


class SNMPCollector:
    def __init__(self, device, timeout, port=161):
        self.device, self.timeout, self.port = device, timeout, port

    def close(self):
        pass

    async def _get(self, community):
        from pysnmp.hlapi.v3arch.asyncio import (SnmpEngine, CommunityData, UdpTransportTarget,
                                               ContextData, ObjectType, ObjectIdentity, get_cmd)
        engine = SnmpEngine()
        try:
            target = await UdpTransportTarget.create((self.device["host"], self.port), timeout=self.timeout, retries=0)
            indication, status, _, bindings = await get_cmd(engine, CommunityData(community, mpModel=1), target,
                ContextData(), ObjectType(ObjectIdentity(EXTEND_OID)), lookupMib=False)
            if indication or status:
                raise ValueError("SNMP không trả dữ liệu")
            value = bindings[0][1]
            if not hasattr(value, "asOctets"):
                raise ValueError("Không có SNMP extend netwatch")
            payload = value.asOctets()
            if len(payload) > 65536:
                raise ValueError("SNMP quá dài")
            return json.loads(payload)
        finally:
            engine.close_dispatcher()

    def collect(self):
        community = os.getenv(self.device["credential_prefix"] + "_SNMP_COMMUNITY")
        if not community:
            raise CollectionError("offline", "Thiếu SNMP community trong .env.netwatch")
        try:
            return validate_sample(asyncio.run(self._get(community)), self.device["interfaces"])
        except Exception as exc:
            raise CollectionError("offline", f"Lỗi SNMP ({type(exc).__name__}); kiểm tra UDP 161 và extend") from None
