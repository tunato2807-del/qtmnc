"""Kiểm thử SSH/SNMP qua socket loopback; không dùng VM hay kênh nhắn tin thật."""
import json
import os
import secrets
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import paramiko

from netwatch.collectors import CollectionError, SSHCollector, SNMPCollector, EXTEND_OID
from netwatch.config import load_inventory
from tests.test_core import sample


class LocalSSH(paramiko.ServerInterface):
    def __init__(self, password):
        self.password = password
        self.event = threading.Event()
        self.command = None

    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL if username == "monitor" and password == self.password else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        self.command = command.decode()
        self.event.set()
        return True


class SSHWireTests(unittest.TestCase):
    def test_strict_pin_and_persistent_connection(self):
        key = paramiko.RSAKey.generate(2048)
        password = secrets.token_urlsafe(24)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(4)
        port = listener.getsockname()[1]
        commands, failures = [], []

        def serve():
            transport = None
            try:
                connection, _ = listener.accept()
                transport = paramiko.Transport(connection)
                transport.add_server_key(key)
                server = LocalSSH(password)
                transport.start_server(server=server)
                for _ in range(2):
                    channel = transport.accept(4)
                    if channel is None or not server.event.wait(4):
                        raise RuntimeError("Thiếu exec")
                    commands.append(server.command)
                    server.event.clear()
                    channel.sendall(json.dumps(sample()).encode())
                    channel.send_exit_status(0)
                    channel.shutdown_write()
            except Exception as exc:
                failures.append(type(exc).__name__)
            finally:
                if transport:
                    # Chờ client đọc hết dữ liệu trước khi đóng transport.
                    while transport.is_active():
                        threading.Event().wait(.05)
                listener.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"R1_SSH_USER": "monitor", "R1_SSH_PASSWORD": password}):
            path = Path(folder) / "known_hosts"
            hosts = paramiko.HostKeys()
            hosts.add(f"[127.0.0.1]:{port}", key.get_name(), key)
            hosts.save(str(path))
            device = {**load_inventory()["devices"][0], "host": "127.0.0.1"}
            collector = SSHCollector(device, 4, known_hosts=path, port=port)
            try:
                self.assertEqual(collector.collect()["cpu_pct"], 40)
                transport = collector.client.get_transport()
                self.assertEqual(collector.collect()["ram_pct"], 35)
                self.assertIs(collector.client.get_transport(), transport)
            finally:
                collector.close()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, failures)
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(cmd.startswith("/usr/bin/python3 /opt/netwatch/probe.py --interfaces ") for cmd in commands))

    def test_unknown_host_rejected_without_auto_add(self):
        device = load_inventory()["devices"][0]
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"R1_SSH_PASSWORD": "not-used"}):
            collector = SSHCollector(device, 2, known_hosts=Path(folder) / "missing")
            with self.assertRaises(CollectionError) as ctx:
                collector.collect()
            self.assertIn("host key", ctx.exception.detail)
            self.assertFalse((Path(folder) / "missing").exists())


class SNMPWireTests(unittest.TestCase):
    def test_real_v2c_get_and_extend_json(self):
        from pyasn1.codec.ber import decoder, encoder
        from pysnmp.proto.api import v2c
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        sock.settimeout(5)
        port = sock.getsockname()[1]
        seen, errors = [], []

        def respond():
            try:
                packet, source = sock.recvfrom(65536)
                request, rest = decoder.decode(packet, asn1Spec=v2c.Message())
                self.assertFalse(rest)
                pdu = v2c.apiMessage.get_pdu(request)
                seen.extend(str(name) for name, value in v2c.apiPDU.get_varbinds(pdu))
                response = v2c.apiMessage.get_response(request)
                rpdu = v2c.apiMessage.get_pdu(response)
                v2c.apiPDU.set_varbinds(rpdu, [(v2c.ObjectIdentifier(EXTEND_OID), v2c.OctetString(json.dumps(sample())))])
                sock.sendto(encoder.encode(response), source)
            except Exception as exc:
                errors.append(repr(exc))
            finally:
                sock.close()

        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        device = {**load_inventory()["devices"][0], "host": "127.0.0.1", "protocol": "snmp"}
        with patch.dict(os.environ, {"R1_SNMP_COMMUNITY": secrets.token_urlsafe(24)}):
            result = SNMPCollector(device, 3, port=port).collect()
        thread.join(5)
        self.assertFalse(errors, errors)
        self.assertEqual(seen, [EXTEND_OID])
        self.assertEqual(result["cpu_pct"], 40)


if __name__ == "__main__":
    unittest.main()
