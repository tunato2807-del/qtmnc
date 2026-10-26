"""Ethernet byte preservation, real UDP NIO transport and the Windows TAP I/O contract."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import queue
import socket
import struct
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from device_monitor.ethernet_tunnel import EthernetTunnel
import setup_project
from tools.create_gns3_project import tap_project
from tools.windows_tap_bridge import (
    TAP_GET_MAC, TAP_GET_VERSION, TAP_SET_MEDIA_STATUS, TapAdapter, WinTap, canonical_guid, find_adapters,
)

FRAME = bytes.fromhex("ffffffffffff0200000000010806") + bytes(range(28))
REPLY = bytes.fromhex("0200000000010200000000020806") + bytes(reversed(range(28)))


class QueueTap:
    def __init__(self):
        self.outgoing = queue.Queue()
        self.incoming = queue.Queue()

    def read(self, stop):
        try:
            return self.outgoing.get(timeout=0.1)
        except queue.Empty:
            return None

    def write(self, frame, stop):
        self.incoming.put(frame)
        return True

    def cancel(self):
        self.outgoing.put(None)


class DatagramTests(unittest.TestCase):
    def setUp(self):
        self.peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.peer.bind(("127.0.0.1", 0))
        self.peer.settimeout(2)
        self.addCleanup(self.peer.close)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", 0))
        self.addCleanup(self.udp.close)
        self.tap = QueueTap()
        self.bridge = EthernetTunnel(self.tap, self.udp, self.peer.getsockname()[1])
        self.addCleanup(self.bridge.close)

    def test_real_udp_roundtrip_preserves_ethernet_headers_and_payload(self):
        self.bridge.start()
        self.tap.outgoing.put(FRAME)
        payload, source = self.peer.recvfrom(65535)
        self.assertEqual(payload, FRAME)
        self.assertEqual(source, self.udp.getsockname())
        self.peer.sendto(REPLY, source)
        self.assertEqual(self.tap.incoming.get(timeout=2), REPLY)
        self.bridge.raise_if_failed()

    def test_only_configured_local_peer_can_inject_complete_frames(self):
        self.bridge.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rogue:
            rogue.bind(("127.0.0.1", 0))
            rogue.sendto(FRAME, self.udp.getsockname())
        self.peer.sendto(b"short", self.udp.getsockname())
        self.peer.sendto(REPLY, self.udp.getsockname())
        self.assertEqual(self.tap.incoming.get(timeout=2), REPLY)
        self.assertTrue(self.tap.incoming.empty())
        self.assertGreaterEqual(self.bridge.snapshot().get("dropped", 0), 2)

    def test_device_write_failure_stops_the_tunnel_and_is_reported(self):
        self.tap.write = Mock(side_effect=OSError("fixture I/O failure"))
        self.bridge.start()
        self.peer.sendto(REPLY, self.udp.getsockname())
        self.assertTrue(self.bridge.stop.wait(2))
        with self.assertRaises(OSError):
            self.bridge.raise_if_failed()


class TunnelConfigurationTests(unittest.TestCase):
    def test_peer_not_yet_started_does_not_kill_tap_reader(self):
        device = Mock()
        udp = Mock()
        bridge = EthernetTunnel(device, udp, 30010)
        replies = iter([FRAME, REPLY])
        def read(stop):
            try:
                return next(replies)
            except StopIteration:
                stop.set()
                return None
        device.read.side_effect = read
        udp.sendto.side_effect = [ConnectionResetError(), len(REPLY)]
        bridge._tap_to_udp()
        self.assertEqual(bridge.snapshot().get("peer_unavailable"), 1)
        self.assertEqual(bridge.snapshot().get("tap_to_gns3"), 1)
        self.assertTrue(bridge.errors.empty())

    def test_tap_project_requires_both_directions_to_cross_gns3_switch(self):
        data = tap_project({2: "Adapter VMnet2"})
        nodes = data["topology"]["nodes"]
        self.assertEqual(len(nodes), 3)
        self.assertEqual(len(data["topology"]["links"]), 2)
        windows = next(n for n in nodes if n["name"] == "Cloud-WINDOWS")
        linux = next(n for n in nodes if n["name"] == "Cloud-LINUX")
        port = windows["properties"]["ports_mapping"][0]
        self.assertEqual(port["type"], "udp")
        self.assertEqual((port["lport"], port["rhost"], port["rport"]), (30010, "127.0.0.1", 30011))
        self.assertNotIn("interface", port)
        self.assertEqual(linux["properties"]["ports_mapping"][0]["interface"], "Adapter VMnet2")
        self.assertTrue(all(n["compute_id"] == "local" for n in nodes))
        with self.assertRaises(ValueError):
            tap_project(cloud_port=30010, bridge_port=30010)

    def test_tap_guid_is_validated_before_creating_a_device_path(self):
        guid = canonical_guid("AABBCCDD-1122-4333-8444-556677889900")
        adapter = TapAdapter("fixture", guid)
        self.assertEqual(adapter.device_path, "\\\\.\\Global\\{aabbccdd-1122-4333-8444-556677889900}.tap")
        with self.assertRaises(ValueError):
            canonical_guid("unsafe-device-path")

    def test_install_only_with_tap_never_prompts_for_secrets_or_connects_ssh(self):
        out = io.StringIO()
        with patch.object(setup_project, "install_dependencies", return_value=Path("fixture-python")) as install, \
             patch.object(setup_project, "configure_simple") as configure, \
             patch.object(setup_project, "verify_ssh") as verify, \
             patch.object(setup_project.subprocess, "call") as child, redirect_stdout(out):
            self.assertEqual(setup_project.main(["--profile", "simple", "--with-tap", "--install-only"]), 0)
        install.assert_called_once_with(requirements="requirements-tap-windows.txt")
        configure.assert_not_called()
        verify.assert_not_called()
        child.assert_not_called()

    def test_registry_discovery_selects_tap0901_and_ignores_class_metadata(self):
        class Key:
            def __init__(self, values=None):
                self.values = values or {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        root = Key()
        fixture_guid = "{AABBCCDD-1122-4333-8444-556677889900}"
        values = {
            "0000": {"ComponentId": "pci\\fixture"},
            "0001": {"ComponentId": "tap0901", "NetCfgInstanceId": fixture_guid},
        }
        registry = Mock()
        def open_key(parent, path):
            if parent is root:
                if path == "Properties":
                    raise PermissionError("This metadata key must not be opened")
                return Key(values[path])
            if path.endswith("\\Connection"):
                return Key({"Name": "GNS3-TAP"})
            return root
        def enum_key(parent, index):
            if index >= 3:
                raise DriverError(259)
            return ["0000", "0001", "Properties"][index]
        registry.OpenKey.side_effect = open_key
        registry.EnumKey.side_effect = enum_key
        registry.QueryValueEx.side_effect = lambda key, name: (key.values[name], 1)
        with patch.dict(sys.modules, {"winreg": registry}):
            adapters = find_adapters()
        self.assertEqual(adapters, [TapAdapter("GNS3-TAP", canonical_guid(fixture_guid))])


class DriverError(OSError):
    def __init__(self, code):
        super().__init__(code, "fixture driver error")
        self.winerror = code


class TapIOTests(unittest.TestCase):
    """Run on Linux as well: mock only Win32 calls, exercise real WinTap logic."""
    def setUp(self):
        self.file = Mock()
        self.events = Mock()
        self.types = SimpleNamespace(error=DriverError, OVERLAPPED=lambda: SimpleNamespace())
        constants = SimpleNamespace(
            GENERIC_READ=0x80000000, GENERIC_WRITE=0x40000000, OPEN_EXISTING=3,
            FILE_ATTRIBUTE_SYSTEM=4, FILE_FLAG_OVERLAPPED=0x40000000)
        self.handle = Mock()
        self.file.CreateFile.return_value = self.handle
        self.file.AllocateReadBuffer.side_effect = bytearray
        self.events.CreateEvent.side_effect = lambda *a: Mock()
        self.events.WaitForSingleObject.return_value = 0
        def control(handle, code, data, size):
            if code == TAP_GET_MAC:
                return bytes.fromhex("020000000001")
            if code == TAP_GET_VERSION:
                return struct.pack("<III", 9, 26, 0)
            return b"\1"
        self.file.DeviceIoControl.side_effect = control
        modules = {"win32file": self.file, "win32event": self.events,
                   "pywintypes": self.types, "win32con": constants}
        module_patch = patch.dict(sys.modules, modules)
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.tap = WinTap(TapAdapter("fixture", "{00000000-0000-0000-0000-000000000001}"))
        self.addCleanup(self.tap.close)

    def test_open_uses_overlapped_tap_handle_and_media_status_ioctl(self):
        args = self.file.CreateFile.call_args.args
        self.assertTrue(args[5] & 0x40000000)
        self.assertEqual(self.tap.mac, "02:00:00:00:00:01")
        media = [c.args for c in self.file.DeviceIoControl.call_args_list if c.args[1] == TAP_SET_MEDIA_STATUS]
        self.assertEqual(media[0][2:], (struct.pack("<I", 1), 4))

    def test_read_keeps_pending_buffer_until_overlapped_completion(self):
        self.tap.read_buffer[:len(FRAME)] = FRAME
        self.file.ReadFile.return_value = (997, self.tap.read_buffer)
        self.events.WaitForSingleObject.side_effect = [258, 0]
        self.file.GetOverlappedResult.return_value = len(FRAME)
        self.assertEqual(self.tap.read(threading.Event()), FRAME)
        self.file.GetOverlappedResult.assert_called_once_with(self.handle, self.tap.read_overlapped, True)

    def test_incoming_udp_frame_is_written_to_tap_receive_path_unchanged(self):
        self.file.WriteFile.return_value = (0, len(REPLY))
        self.file.GetOverlappedResult.return_value = len(REPLY)
        self.assertTrue(self.tap.write(REPLY, threading.Event()))
        self.file.WriteFile.assert_called_once_with(self.handle, REPLY, self.tap.write_overlapped)
        self.file.GetOverlappedResult.return_value = len(REPLY) - 1
        with self.assertRaises(OSError):
            self.tap.write(REPLY, threading.Event())

    def test_cancelled_read_is_completed_before_buffer_is_released(self):
        stop = threading.Event()
        stop.set()
        self.file.ReadFile.return_value = (997, self.tap.read_buffer)
        self.events.WaitForSingleObject.return_value = 258
        self.file.GetOverlappedResult.side_effect = DriverError(995)
        self.assertIsNone(self.tap.read(stop))
        self.file.CancelIoEx.assert_called_once_with(self.handle, None)
        self.file.GetOverlappedResult.assert_called_once()


if __name__ == "__main__":
    unittest.main()
