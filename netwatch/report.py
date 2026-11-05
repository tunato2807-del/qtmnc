"""Báo cáo HTML độc lập, không CDN; có thể in thành PDF từ trình duyệt."""
import argparse
import html
import time
from pathlib import Path

from .config import ROOT, load_inventory
from .storage import Store


def esc(value):
    return html.escape(str(value), quote=True)


def chart(rows, key, label, color="#2761ce", ceiling=None):
    valid = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
    top = ceiling or max(1, max(valid, default=1) * 1.15)
    d, pen = "", False
    for index, row in enumerate(rows):
        value = row.get(key)
        if not isinstance(value, (int, float)):
            pen = False
            continue
        x, y = 20 + 720 * index / max(1, len(rows) - 1), 140 - min(top, max(0, value)) / top * 120
        d += (" L" if pen else " M") + f"{x:.1f} {y:.1f}"
        pen = True
    axis = ""
    if rows:
        start = time.strftime("%H:%M:%S UTC", time.gmtime(rows[0]["at"]))
        end = time.strftime("%H:%M:%S UTC", time.gmtime(rows[-1]["at"]))
        axis = f'<text x="20" y="157" font-size="10">{start}</text><text x="660" y="157" font-size="10">{end}</text>'
    return f'<figure><figcaption>{esc(label)}</figcaption><svg viewBox="0 0 760 165" role="img" aria-label="{esc(label)}"><path d="M20 20 V140 H740" fill="none" stroke="#c8d5e4"/><text x="0" y="140" font-size="10">0</text><text x="0" y="18" font-size="10">{top:.1f}</text>{axis}<path d="{d}" fill="none" stroke="{color}" stroke-width="2.6"/></svg></figure>'


def build_html(store, config):
    mode = "MÔ PHỎNG" if store.demo else "DỮ LIỆU LAB"
    latest, blocks = store.snapshot(), []
    for device in config["devices"]:
        sample = latest.get(device["id"], {})
        rows = store.history(device["id"])
        cpu = sample.get("cpu_pct")
        ram = sample.get("ram_pct")
        numbers = f"CPU: {cpu:.1f}%" if cpu is not None else "CPU: chưa có dữ liệu"
        numbers += f" · RAM: {ram:.1f}%" if ram is not None else " · RAM: chưa có dữ liệu"
        graphs = chart(rows, "cpu_pct", "CPU theo thời gian (%)", ceiling=100) + chart(rows, "ram_pct", "RAM theo thời gian (%)", "#078963", 100)
        sample_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(sample["at"])) if "at" in sample else "Chưa có mẫu"
        blocks.append(f'<section><h2>{esc(device["name"])} — {esc(device["host"])}</h2><p>{esc(numbers)} · Nguồn: {esc(sample.get("source", "Chưa có mẫu"))}<br>Mẫu cuối: {esc(sample_at)}</p>{graphs}</section>')
    network_rows = []
    for value in store.health():
        if value["kind"] == "ping":
            loss, rtt = value.get("packet_loss_pct"), value.get("rtt_avg_ms")
            text = (f"RTT {rtt:.2f} ms" if rtt is not None else "Chưa có RTT") + (f" · mất gói {loss:.1f}%" if loss is not None else " · chưa xác định mất gói")
            blocks.append('<section><h2>' + esc(value["name"]) + '</h2>' + chart(store.health_history(value["id"]), "rtt_avg_ms", "RTT theo thời gian (ms)") + '</section>')
        else:
            text = value.get("detail", "Chưa có dữ liệu")
        network_rows.append('<tr><td>' + esc(value["name"]) + '</td><td>' + esc(value["state"]) + '</td><td>' + esc(text) + '</td><td>' + esc(time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(value["at"]))) + '</td></tr>')
    events = ''.join('<tr><td>' + esc(time.strftime("%H:%M:%S UTC", time.gmtime(e["at"]))) + '</td><td>' + esc(e["device"]) + '</td><td>' + esc(e["state"]) + '</td><td>' + esc(e["message"]) + '</td></tr>' for e in store.events())
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Báo cáo NetWatch</title><style>
body{{font:15px/1.6 Arial,sans-serif;color:#173352;margin:32px auto;max-width:1000px;padding:0 22px}}h1,h2{{color:#2456a9}}h2{{font-size:20px}}section{{break-inside:avoid;border-top:1px solid #dce5f1;padding-top:14px;margin-top:25px}}figure{{margin:12px 0}}figcaption{{font-weight:bold}}svg{{width:100%;max-height:180px}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border:1px solid #dce5f1;padding:8px;text-align:left}}.mode{{padding:12px;background:#fff1c8}}@media print{{body{{font-size:11pt;margin:0;max-width:none}}@page{{size:A4;margin:15mm}}}}
</style></head><body><h1>Báo cáo giám sát NetWatch</h1><p class="mode">{mode} · Xuất lúc {stamp}</p><p>Nguồn: SQLite cục bộ; tối đa 300 mẫu gần nhất cho mỗi biểu đồ. Mẫu thiếu được bỏ trống. Tỷ lệ mất gói ICMP không phải SLA dịch vụ.</p>{''.join(blocks)}<section><h2>Chất lượng mạng và dịch vụ</h2><table><tr><th>Phép đo</th><th>Trạng thái</th><th>Kết quả mẫu cuối</th><th>Thời điểm</th></tr>{''.join(network_rows)}</table></section><section><h2>Sự kiện gần nhất</h2><table><tr><th>Giờ UTC</th><th>Thiết bị</th><th>Trạng thái</th><th>Nội dung</th></tr>{events}</table></section><p>Để lưu PDF: mở file HTML → Ctrl+P → Save as PDF. Bản báo cáo lưu ảnh chụp dữ liệu tại lúc xuất, không tự cập nhật.</p></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data/netwatch.sqlite3")
    parser.add_argument("--inventory", type=Path, default=ROOT / "inventory.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/NetWatch_bao_cao.html")
    args = parser.parse_args()
    if not args.db.exists():
        parser.error("Chưa có database; chạy giám sát lab thật trước hoặc tải báo cáo từ dashboard demo")
    store = Store(args.db)
    try:
        document = build_html(store, load_inventory(args.inventory))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        print("Đã xuất:", args.output.resolve())
    finally:
        store.close()


if __name__ == "__main__":
    main()
