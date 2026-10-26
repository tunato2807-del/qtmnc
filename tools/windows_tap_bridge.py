"""Windows TAP-Windows V9 <-> localhost UDP <-> GNS3 Cloud, without pcap injection."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import ctypes
import socket
import struct
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from device_monitor.ethernet_tunnel import EthernetTunnel, MAX_FRAME

NETWORK_CLASS = "{4D36E972-E325-11CE-BFC1-08002BE10318}"
TAP_GET_MAC = (0x22 << 16) | (1 << 2)
TAP_GET_VERSION = (0x22 << 16) | (2 << 2)
TAP_SET_MEDIA_STATUS = (0x22 << 16) | (6 << 2)


@dataclass(frozen=True)
class TapAdapter:
    name: str
    guid: str

    @property
    def device_path(self):
        return "\\\\.\\Global\\" + self.guid + ".tap"


def canonical_guid(value):
    return "{" + str(uuid.UUID(value.strip("{}"))) + "}"


def find_adapters():
    import winreg
    result = []
    class_path = "SYSTEM\\CurrentControlSet\\Control\\Class\\" + NETWORK_CLASS
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_path) as root:
        index = 0
        while True:
            try:
                child = winreg.EnumKey(root, index)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 259:
                    break
                raise
            index += 1
            if len(child) != 4 or any(char not in "0123456789abcdefABCDEF" for char in child):
                continue
            try:
                with winreg.OpenKey(root, child) as entry:
                    component = winreg.QueryValueEx(entry, "ComponentId")[0].lower()
                    if component != "tap0901":
                        continue
                    guid = canonical_guid(winreg.QueryValueEx(entry, "NetCfgInstanceId")[0])
                connection = "SYSTEM\\CurrentControlSet\\Control\\Network\\" + NETWORK_CLASS + "\\" + guid + "\\Connection"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, connection) as entry:
                    name = winreg.QueryValueEx(entry, "Name")[0]
                result.append(TapAdapter(name, guid))
            except FileNotFoundError:
                continue
    return result


def choose_adapter(adapters, name):
    matches = [adapter for adapter in adapters if adapter.name.casefold() == name.casefold()]
    if len(matches) != 1:
        raise ValueError("Không tìm thấy duy nhất TAP-Windows V9 tên này. Chạy --list và kiểm tra tên adapter.")
    return matches[0]


class WinTap:
    """TAP driver WriteFile indicates incoming frames to NDIS/TCPIP on Windows."""

    def __init__(self, adapter):
        import pywintypes
        import win32con
        import win32event
        import win32file
        self.file, self.event, self.types = win32file, win32event, pywintypes
        self.handle = None
        self.events = []
        try:
            self.handle = win32file.CreateFile(
                adapter.device_path, win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0, None, win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_SYSTEM | win32con.FILE_FLAG_OVERLAPPED, None)
            raw = win32file.DeviceIoControl(self.handle, TAP_GET_MAC, b"", 6)
            self.mac = ":".join(f"{byte:02x}" for byte in raw)
            version = win32file.DeviceIoControl(self.handle, TAP_GET_VERSION, b"", 12)
            self.version = struct.unpack("<III", version)
            self.read_buffer = win32file.AllocateReadBuffer(MAX_FRAME + 1)
            self.read_overlapped = self._overlapped()
            self.write_overlapped = self._overlapped()
            win32file.DeviceIoControl(self.handle, TAP_SET_MEDIA_STATUS, struct.pack("<I", 1), 4)
        except Exception:
            self.close()
            raise

    def _overlapped(self):
        value = self.types.OVERLAPPED()
        value.hEvent = self.event.CreateEvent(None, True, False, None)
        self.events.append(value.hEvent)
        return value

    def _finish(self, status, overlapped, stop):
        if status not in (0, 997):  # NO_ERROR / ERROR_IO_PENDING
            raise OSError(status, "TAP I/O không thực hiện được")
        if status == 997:
            while True:
                outcome = self.event.WaitForSingleObject(overlapped.hEvent, 200)
                if outcome == 0:
                    break
                if outcome != 258:
                    raise OSError("Không chờ được sự kiện TAP")
                if stop.is_set():
                    self.cancel()
                    break
        # Wait for cancellation/completion before the I/O buffer can be reused.
        try:
            return self.file.GetOverlappedResult(self.handle, overlapped, True)
        except self.types.error as exc:
            if stop.is_set() and exc.winerror == 995:
                return None
            raise

    def read(self, stop):
        self.event.ResetEvent(self.read_overlapped.hEvent)
        status, _ = self.file.ReadFile(self.handle, self.read_buffer, self.read_overlapped)
        size = self._finish(status, self.read_overlapped, stop)
        return None if size is None else bytes(self.read_buffer[:size])

    def write(self, frame, stop):
        self.event.ResetEvent(self.write_overlapped.hEvent)
        status, _ = self.file.WriteFile(self.handle, frame, self.write_overlapped)
        size = self._finish(status, self.write_overlapped, stop)
        if size is None:
            return False
        if size != len(frame):
            raise OSError("TAP chỉ nhận một phần frame")
        return True

    def cancel(self):
        if self.handle is not None:
            try:
                self.file.CancelIoEx(self.handle, None)
            except self.types.error as exc:
                if exc.winerror != 1168:  # No pending I/O is already safe.
                    raise

    def close(self):
        if self.handle is not None:
            try:
                self.file.DeviceIoControl(self.handle, TAP_SET_MEDIA_STATUS, struct.pack("<I", 0), 4)
            except Exception:
                pass
            self.handle.Close()
            self.handle = None
        for event in self.events:
            event.Close()
        self.events.clear()


def port(value):
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("Cổng phải trong 1..65535")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", default="GNS3-TAP")
    parser.add_argument("--local-port", type=port, default=30011)
    parser.add_argument("--peer-port", type=port, default=30010)
    parser.add_argument("--list", action="store_true", help="Liệt kê adapter TAP-Windows V9")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("Công cụ này chạy trên Windows; không chạy trên Ubuntu.", file=sys.stderr)
        return 2
    device, tunnel, udp = None, None, None
    try:
        if args.local_port == args.peer_port:
            raise ValueError("Hai cổng UDP phải khác nhau")
        adapters = find_adapters()
        if args.list:
            for adapter in adapters:
                print(f"{adapter.name}  {adapter.guid}")
            if not adapters:
                print("Chưa có TAP-Windows V9. Xem WINDOWS_TAP_GNS3.md.")
            return 0 if adapters else 1
        adapter = choose_adapter(adapters, args.adapter)
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise PermissionError("Mở PowerShell bằng Run as administrator rồi chạy lại")
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        udp.bind(("127.0.0.1", args.local_port))
        device = WinTap(adapter)
        print(f"TAP: {adapter.name}; MAC: {device.mac}; driver: {device.version[0]}.{device.version[1]}")
        print(f"UDP: 127.0.0.1:{args.local_port} <-> GNS3 127.0.0.1:{args.peer_port}")
        print("Giữ cửa sổ này mở. Ctrl+C dừng cầu nối; không cần weak-host hay ARP tĩnh.", flush=True)
        tunnel = EthernetTunnel(device, udp, args.peer_port)
        tunnel.start()
        last_print = 0.0
        while not tunnel.stop.wait(0.25):
            if time.monotonic() - last_print >= 5:
                counts = tunnel.snapshot()
                print(f"TAP -> GNS3: {counts.get('tap_to_gns3', 0)} | GNS3 -> TAP: {counts.get('gns3_to_tap', 0)} | Bỏ qua: {counts.get('dropped', 0)}", flush=True)
                last_print = time.monotonic()
        tunnel.raise_if_failed()
        return 0
    except KeyboardInterrupt:
        print("\nĐã dừng cầu nối TAP.")
        return 0
    except ImportError:
        print("Thiếu pywin32. Chạy setup_windows.cmd --with-tap --install-only.", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Chưa mở được cầu nối ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            if tunnel:
                tunnel.close()
        finally:
            if udp:
                udp.close()
            if device:
                device.close()


if __name__ == "__main__":
    raise SystemExit(main())
