"""Loopback-only integration tests with real SSH and SNMP protocol libraries."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

import monitor_ssh as m

try:
    import paramiko
except ImportError:
    paramiko = None
try:
    from pysnmp.entity import config as snmp_config, engine
    from pysnmp.entity.rfc3413 import cmdrsp, context
    from pysnmp.carrier.asyncio.dgram import udp
    from pysnmp.proto import rfc1902, rfc1905
    from pysnmp.hlapi.v3arch import asyncio as snmp_api
except ImportError:
    snmp_api = None


@contextmanager
def ssh_device():
    host_key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(3)
    port = listener.getsockname()[1]
    stop = threading.Event()
    transports = []

    class Server(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL if (username, password) == ("fixture", "local-fixture-only") else paramiko.AUTH_FAILED

        def get_allowed_auths(self, username):
            return "password"

        def check_channel_request(self, kind, chanid):
            return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

        def check_channel_exec_request(self, channel, command):
            command = command.decode()
            allowed = {m.SSHCollector.CPU_CMD, "cat /proc/meminfo", "cat /sys/class/net/lo/operstate", "exit"}
            if command not in allowed:
                return False

            def respond():
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, timeout=5)
                    channel.sendall(result.stdout)
                    if result.stderr:
                        channel.send_stderr(result.stderr)
                    channel.send_exit_status(result.returncode)
                finally:
                    channel.close()
            threading.Thread(target=respond, daemon=True).start()
            return True

    def serve():
        try:
            conn, _ = listener.accept()
            transport = paramiko.Transport(conn)
            transports.append(transport)
            transport.add_server_key(host_key)
            transport.start_server(server=Server())
            channels = []
            while not stop.is_set() and transport.is_active():
                channel = transport.accept(0.1)
                if channel:
                    channels.append(channel)
        except (OSError, EOFError, paramiko.SSHException):
            pass
        finally:
            for transport in transports:
                transport.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield port, host_key
    finally:
        stop.set()
        for transport in transports:
            transport.close()
        listener.close()
        worker.join(4)


@unittest.skipIf(paramiko is None, "Install requirements.txt for SSH integration tests")
@unittest.skipUnless(sys.platform.startswith("linux"), "Local SSH fixture executes Linux /proc probes")
class SSHIntegrationTests(unittest.TestCase):
    def test_real_ssh_and_linux_probes(self):
        with tempfile.TemporaryDirectory() as directory, ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            known.write_text(f"[127.0.0.1]:{port} {key.get_name()} {key.get_base64()}\n")
            c = m.Config(host="127.0.0.1", ssh_port=port, ssh_user="fixture",
                         ssh_password="local-fixture-only", known_hosts=str(known),
                         iface="lo", temp_enabled=False, timeout=3)
            sample = m.SSHCollector(c).collect()
            self.assertFalse(sample.errors)
            self.assertTrue(0 <= sample.values["cpu"] <= 100)
            self.assertTrue(0 <= sample.values["ram"] <= 100)
            self.assertIn(sample.values["iface"], {"up", "unknown"})

    def test_untrusted_host_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            known.write_text("")
            c = m.Config(host="127.0.0.1", ssh_port=port, ssh_user="fixture",
                         ssh_password="local-fixture-only", known_hosts=str(known), timeout=3)
            with self.assertRaises(m.DeviceUnavailable):
                m.SSHCollector(c).collect()


@unittest.skipIf(snmp_api is None, "Install requirements-snmp.txt for SNMP integration tests")
class SNMPIntegrationTests(unittest.TestCase):
    def exercise(self, version):
        async def run():
            agent = engine.SnmpEngine()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.setblocking(False)
            transport = udp.UdpTransport().open_server_mode(sock=sock)
            snmp_config.add_transport(agent, udp.DOMAIN_NAME, transport)
            snmp_config.add_v1_system(agent, "fixture", "local-community")
            snmp_config.add_v3_user(agent, "fixture", snmp_api.usmHMACSHAAuthProtocol,
                                   "local-auth-key", snmp_api.usmAesCfb128Protocol, "local-priv-key")
            snmp_config.add_vacm_user(agent, 2, "fixture", "noAuthNoPriv", (1, 3, 6))
            snmp_config.add_vacm_user(agent, 3, "fixture", "authPriv", (1, 3, 6))
            oids = {"cpu": "1.3.6.1.4.1.99999.1.0", "ram": "1.3.6.1.4.1.99999.2.0",
                    "temp": "1.3.6.1.4.1.99999.3.0", "iface": "1.3.6.1.2.1.2.2.1.8.2"}
            fixtures = {tuple(map(int, oids[k].split("."))): v for k, v in
                        {"cpu": 80, "ram": 60, "temp": 65000, "iface": 1}.items()}

            class Instrumentation:
                def read_variables(self, *bindings, **kwargs):
                    return [(name, rfc1902.Integer32(fixtures[tuple(name)])
                             if tuple(name) in fixtures else rfc1905.noSuchInstance)
                            for name, _ in bindings]

            ctx = context.SnmpContext(agent)
            ctx.unregister_context_name(b"")
            ctx.register_context_name(b"", Instrumentation())
            responder = cmdrsp.GetCommandResponder(agent, ctx)
            c = m.Config(host="127.0.0.1", protocol="snmp", snmp_port=port,
                         snmp_version=version, snmp_community="local-community",
                         snmp_user="fixture", snmp_auth_key="local-auth-key",
                         snmp_priv_key="local-priv-key", oids=oids, timeout=1)
            try:
                await transport._lport  # Wait for this test fixture's UDP bind.
                values = await m.SNMPCollector(c)._fetch()
                self.assertEqual(values, {"cpu": "80", "ram": "60", "temp": "65000", "iface": "1"})
            finally:
                responder.close(agent)
                agent.close_dispatcher()
                await asyncio.sleep(0)
        asyncio.run(run())

    def test_real_snmp_v2c_get(self):
        self.exercise("2c")

    def test_real_snmp_v3_authpriv_get(self):
        self.exercise("3")


if __name__ == "__main__":
    unittest.main()
