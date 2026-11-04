#!/usr/bin/env python3
"""Tạo project GNS3 local có đường dẫn VMX thật; không thay đổi VMX."""
import argparse
import json
import re
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def read_vmx(path):
    path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower() != ".vmx":
        raise ValueError("Phải chọn file .vmx")
    pairs = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r'\s*([\w.]+)\s*=\s*"(.*?)"', line)
        if match:
            pairs[match[1].lower()] = match[2]
    return path, pairs


def validate_vms(router, server):
    router, r = read_vmx(router)
    server, s = read_vmx(server)
    if router == server:
        raise ValueError("R1 và SRV1 phải là hai full clone khác nhau")
    if r.get("ethernet0.connectiontype", "").lower() != "nat":
        raise ValueError("R1: Network Adapter đầu tiên phải là NAT")
    for index in (1, 2):
        if r.get(f"ethernet{index}.present", "").lower() != "true" or r.get(f"ethernet{index}.connectiontype", "").lower() != "custom":
            raise ValueError(f"R1: Network Adapter {index + 1} phải tồn tại và chọn Custom")
    if s.get("ethernet0.present", "").lower() != "true" or s.get("ethernet0.connectiontype", "").lower() != "custom":
        raise ValueError("SRV1: Network Adapter đầu tiên phải chọn Custom sau khi cài gói")
    for label, values, indices in (("R1", r, (1, 2)), ("SRV1", s, (0,))):
        for index in indices:
            # VMnet1 là mạng đặc biệt: GNS3 buộc cấp một VMnet quản lý mới.
            # VMnet ngoài pool có thể được GNS3 giữ nguyên, gây ghép nhầm cổng.
            vnet = values.get(f"ethernet{index}.vnet", "").lower()
            if vnet and vnet != "vmnet1":
                raise ValueError(f"{label}: trước khi tạo project, card Custom {index + 1} chọn tạm VMnet1 để GNS3 cấp mạng riêng; không chọn VMnet khác")
    return router, server


def project(router, server):
    project_id = str(uuid.uuid4())
    nodes, links = [], []

    def node(name, kind, x, y, properties):
        item = {"node_id": str(uuid.uuid4()), "name": name, "compute_id": "local", "node_type": kind,
                "console_type": "telnet" if kind == "vpcs" else "none", "x": x, "y": y, "z": 1,
                "symbol": ":/symbols/router.svg" if name == "R1-LINUX" else ":/symbols/ethernet_switch.svg" if kind == "ethernet_switch" else ":/symbols/computer.svg",
                "properties": properties, "label": {"text": name, "y": -28, "rotation": 0}}
        nodes.append(item)
        return item["node_id"]

    def vm(path, count):
        return {"vmx_path": str(path), "linked_clone": False, "headless": False, "on_close": "power_off", "adapters": count, "adapter_type": "e1000", "use_any_adapter": False}

    def ports():
        return {"ports_mapping": [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1} for i in range(4)]}

    r1 = node("R1-LINUX", "vmware", -280, -20, vm(router, 3))
    sws = node("SW-SERVERS", "ethernet_switch", 30, -160, ports())
    srv = node("SRV1-LINUX", "vmware", 340, -160, vm(server, 1))
    swu = node("SW-USERS", "ethernet_switch", 30, 150, ports())
    pc1 = node("PC01", "vpcs", 340, 80, {})
    pc2 = node("PC02", "vpcs", 340, 240, {})

    def link(a, aa, ap, b, ba, bp):
        links.append({"link_id": str(uuid.uuid4()), "nodes": [{"node_id": a, "adapter_number": aa, "port_number": ap}, {"node_id": b, "adapter_number": ba, "port_number": bp}]})

    # Adapter 0 của R1 là NAT gốc VMware, giữ nguyên và KHÔNG nối link GNS3.
    link(r1, 1, 0, sws, 0, 0)
    link(sws, 0, 1, srv, 0, 0)
    link(r1, 2, 0, swu, 0, 0)
    link(swu, 0, 1, pc1, 0, 0)
    link(swu, 0, 2, pc2, 0, 0)
    text = "Windows → VMnet8 → R1 mgmt0 192.168.73.10 (NAT gốc, không nối link GNS3)"
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="80"><text x="10" y="28" font-family="Arial" font-size="17" fill="#2454ad">' + escape(text) + '</text><text x="10" y="58" font-family="Arial" font-size="15">SRV: 10.10.10.0/24 | USERS: 10.20.20.0/24 | Linux IPv4 routing</text></svg>'
    return {"name": "NETWATCH_ROUTED", "project_id": project_id, "type": "topology", "revision": 9, "version": "2.2.61",
            "auto_start": False, "auto_close": True, "auto_open": False, "scene_width": 1600, "scene_height": 1000, "zoom": 100,
            "show_interface_labels": True, "topology": {"computes": [{"compute_id": "local", "name": "Local", "host": "127.0.0.1", "protocol": "http", "port": 3080}],
            "nodes": nodes, "links": links, "drawings": [{"drawing_id": str(uuid.uuid4()), "x": -420, "y": -350, "z": 0, "rotation": 0, "svg": svg}]}}


def choose(title):
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        name = filedialog.askopenfilename(title=title, filetypes=[("VMware virtual machine", "*.vmx")])
        root.destroy()
        if name:
            return name
    except Exception:
        pass
    return input(title + " (đường dẫn .vmx): ").strip().strip('"')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router-vmx")
    parser.add_argument("--server-vmx")
    parser.add_argument("--output", type=Path, default=ROOT / "lab/generated/NETWATCH_ROUTED")
    args = parser.parse_args()
    try:
        router, server = validate_vms(args.router_vmx or choose("Chọn R1-LINUX.vmx"), args.server_vmx or choose("Chọn SRV1-LINUX.vmx"))
        if any(router.parent.glob("*.lck")) or any(server.parent.glob("*.lck")):
            raise ValueError("VM đang mở hoặc bị khóa; tắt hai VM trước khi tạo")
        output = args.output.resolve()
        target = output / "NETWATCH_ROUTED.gns3"
        if target.exists():
            raise ValueError("Project đã tồn tại; dùng --output với thư mục mới để giữ lab đang dùng")
        output.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(project(router, server), ensure_ascii=False, indent=2), encoding="utf-8")
        print("Đã tạo:", target)
        print("GNS3 → File → Open → chọn file này. Xem docs/01_GNS3.md trước khi Start.")
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
