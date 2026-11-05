"""Sơ đồ GNS3 mở được ngay, chỉ có SVG drawings; không giả thiết bị đã chạy."""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def preview():
    cards = [
        ("Windows thật", "VS Code · Python · Dashboard", "VMnet8: 192.168.73.1", 30, 215, 290, 135, "#e4edff", "#17365f"),
        ("R1-LINUX", "Ubuntu VMware · IPv4 router", "mgmt0: 192.168.73.10", 430, 185, 340, 225, "#2761ce", "white"),
        ("SW-SERVERS", "Ethernet switch L2", "Servers: 10.10.10.0/24", 870, 100, 300, 135, "#e4edff", "#17365f"),
        ("SRV1-LINUX", "CPU/RAM · SSH/SNMP · HTTP", "lan0: 10.10.10.10", 1260, 100, 330, 135, "#e4edff", "#17365f"),
        ("SW-USERS", "Ethernet switch L2", "Users: 10.20.20.0/24", 870, 425, 300, 135, "#e3f4eb", "#17365f"),
        ("PC01 · VPCS", "10.20.20.10/24", "Gateway: 10.20.20.1", 1260, 365, 330, 125, "#e3f4eb", "#17365f"),
        ("PC02 · VPCS", "10.20.20.20/24", "Gateway: 10.20.20.1", 1260, 535, 330, 125, "#e3f4eb", "#17365f")]
    content = ['<svg xmlns="http://www.w3.org/2000/svg" width="1670" height="980">', '<rect width="1670" height="980" fill="#f6f9fd"/>',
               '<text x="30" y="45" font-family="Arial" font-size="30" font-weight="bold" fill="#17365f">NETWATCH · MẠNG ĐỊNH TUYẾN GNS3</text>',
               '<rect x="30" y="70" width="740" height="64" rx="8" fill="#fff0bc"/>',
               '<text x="45" y="98" font-family="Arial" font-size="20" fill="#755100">BẢN XEM SƠ ĐỒ · Không có VM/thiết bị đang thực thi.</text>',
               '<text x="45" y="122" font-family="Arial" font-size="18" fill="#755100">Lab chạy thật: open_gns3_lab.cmd → liên kết hai VMX của bạn.</text>',
               '<path d="M402 145 V685 Q402 705 422 705 H1607 Q1627 705 1627 685 V85 Q1627 65 1607 65 H422 Q402 65 402 70" fill="none" stroke="#aec1dd" stroke-dasharray="9,7"/>',
               '<text x="920" y="690" font-family="Arial" font-size="20" fill="#466a9d">PHẠM VI GNS3: 2 UBUNTU + 2 SWITCH + 2 VPCS</text>']
    for path in ('M320 282 H430', 'M770 250 L870 168', 'M1170 168 H1260', 'M770 365 L870 492', 'M1170 492 L1260 428', 'M1170 492 L1260 597'):
        content.append(f'<path d="{path}" fill="none" stroke="#567fb7" stroke-width="3"/>')
    from xml.sax.saxutils import escape
    for title, subtitle, address, x, y, w, h, fill, color in cards:
        content.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#bdcfe5"/>')
        for text, dy, size, bold in ((title, 38, 24, "bold"), (subtitle, 73, 19, "normal"), (address, 105, 20, "normal")):
            content.append(f'<text x="{x+18}" y="{y+dy}" font-family="Arial" font-size="{size}" font-weight="{bold}" fill="{color}">{escape(text)}</text>')
    content += ['<text x="449" y="337" font-family="Arial" font-size="20" fill="white">srv0: 10.10.10.1</text>',
                '<text x="449" y="373" font-family="Arial" font-size="20" fill="white">users0: 10.20.20.1</text>',
                '<text x="40" y="386" font-family="Arial" font-size="18" fill="#466a9d">NAT gốc VMware → R1</text>',
                '<text x="40" y="415" font-family="Arial" font-size="18" fill="#466a9d">Không dùng Cloud hoặc TAP.</text>',
                '<text x="30" y="770" font-family="Arial" font-size="24" font-weight="bold" fill="#17365f">BỔ SUNG TỪ BÀI THỰC HÀNH BUỔI 5</text>',
                '<text x="30" y="815" font-family="Arial" font-size="22" fill="#466a9d">Lab 1: CSV/CPU/RAM  |  Lab 2: RTT và mất gói  |  Lab 3: iperf3 nội bộ</text>',
                '<text x="30" y="855" font-family="Arial" font-size="22" fill="#466a9d">Lab 4: HTTP 200 / phản hồi ≤ 3s  |  Lab 6: Wireshark  |  Lab 10: Dashboard + HTML/PDF</text>',
                '<text x="30" y="920" font-family="Arial" font-size="20" fill="#17365f">Hướng dẫn VS Code: docs/00_TAI_BANG_VSCODE.md  ·  Nội dung bổ sung: docs/05_BUOI_5.md</text>', '</svg>']
    return {"name": "NETWATCH_XEM_NGAY", "project_id": str(uuid.uuid4()), "type": "topology", "revision": 9, "version": "2.2.61", "auto_start": False, "auto_close": True, "auto_open": False,
            "scene_width": 1900, "scene_height": 1200, "zoom": 80, "show_interface_labels": False,
            "topology": {"computes": [{"compute_id": "local", "name": "Local", "protocol": "http", "host": "127.0.0.1", "port": 3080}], "nodes": [], "links": [],
                         "drawings": [{"drawing_id": str(uuid.uuid4()), "x": -835, "y": -490, "z": 0, "rotation": 0, "svg": ''.join(content)}]}}


if __name__ == "__main__":
    path = ROOT / "lab/gns3/NETWATCH_XEM_NGAY.gns3"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(path.relative_to(ROOT))
