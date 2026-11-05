"""Ảnh demo có nhãn rõ ràng; cần Playwright + Chromium trên máy dựng tài liệu."""
import math
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from netwatch.config import load_inventory
from netwatch.storage import Store
from netwatch.web import create_app


def main():
    cfg = load_inventory()
    store = Store(":memory:", demo=True)
    now = time.time()
    for tick in range(60):
        for idx, device in enumerate(cfg["devices"]):
            sample = {"schema": 1, "cpu_pct": round(40 + 24 * math.sin(tick / 5 + idx) + idx * 14, 1), "ram_pct": round(39 + idx * 14 + 3 * math.sin(tick / 12), 1), "temperature_c": None,
                      "interfaces": {name: {"state": "up", "rx_bytes": tick * 1200000, "tx_bytes": tick * 700000, "rx_errors": 0, "tx_errors": 0} for name in device["interfaces"]}}
            store.record(device, cfg, sample, at=now - (59-tick)*15)
            network = {"kind": "ping", "host": device["host"], "sent": 10, "received": 10, "packet_loss_pct": 0, "rtt_avg_ms": round(2.2 + idx + math.sin(tick/4), 2), "error": ""}
            store.record_health("ping-" + device["id"], "ICMP " + device["name"], device["id"], network, True, "Số liệu mô phỏng", at=now - (59-tick)*15)
        store.record_health("http-srv1-web", "Web SRV1", "srv1", {"kind": "http", "status_code": 200, "response_ms": 20 + tick % 10, "error": ""}, True, "HTTP 200 · số liệu mô phỏng", at=now - (59-tick)*15)
    app = create_app(cfg, store, demo=True)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    failures = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}", wait_until="networkidle")
            page.wait_for_function("() => document.getElementById('online').textContent === '2 / 2'")
            assert page.locator("#health-cards article").count() == 3
            assert "HTTP 200" in page.locator("#health-cards").inner_text()
            page.screenshot(path=str(ROOT / "docs/figures/dashboard-demo.png"), full_page=True)
            page.select_option("#device-select", "srv1")
            page.wait_for_function("() => document.getElementById('export').href.includes('srv1')")
            with page.expect_download() as info:
                page.click("#export")
            assert info.value.suggested_filename == "netwatch-srv1.csv"
            with page.expect_download() as report_info:
                page.click("#report-export")
            report_path = ROOT / "docs/report/NetWatch_bao_cao_demo.html"
            report_info.value.save_as(str(report_path))
            assert "MÔ PHỎNG" in report_path.read_text()
            report_page = browser.new_page()
            # Trình duyệt được quản lý có thể chặn file://; render HTML đã đọc,
            # không thay đổi policy và không yêu cầu browser truy cập filesystem.
            report_page.set_content(report_path.read_text(), wait_until="load")
            assert report_page.locator("svg").count() >= 6
            report_page.close()
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(ROOT / "docs/figures/dashboard-mobile-demo.png"), full_page=True)
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
            assert not failures, failures
            browser.close()
        print("Browser: desktop/mobile, ICMP/HTTP, đổi thiết bị, tải CSV/HTML, render báo cáo độc lập, không JS error — đạt.")
    finally:
        server.shutdown()
        thread.join(3)
        store.close()


if __name__ == "__main__":
    main()
