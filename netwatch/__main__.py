import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from .collectors import enroll
from .config import ROOT, load_inventory
from .service import Service
from .storage import Store
from .web import create_app


def main():
    parser = argparse.ArgumentParser(description="NetWatch — mô hình router Linux trong GNS3")
    parser.add_argument("action", nargs="?", choices=("run", "trust"), default="run")
    parser.add_argument("--inventory", type=Path, default=ROOT / "inventory.json")
    parser.add_argument("--demo", action="store_true", help="Dữ liệu mô phỏng; không SSH, không gửi tin")
    parser.add_argument("--web-only", action="store_true", help="Chỉ đọc DB, không chạy collector")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Cổng phải nằm trong 1024–65535")
    load_dotenv(ROOT / ".env.netwatch", override=False)
    try:
        cfg = load_inventory(args.inventory)
        if args.action == "trust":
            for d in cfg["devices"]:
                if d["protocol"] != "ssh":
                    continue
                print(f"\n{d['name']} ({d['host']}): tại console Ubuntu chạy:")
                print("sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub")
                expected = input("Dán SHA256 từ console (Enter để bỏ qua): ").strip()
                if expected:
                    print("Đã xác minh:", enroll(d["host"], expected, ROOT / ".local/known_hosts"))
            return
        if args.demo and args.web_only:
            parser.error("Chọn demo hoặc web-only")
        store = Store(":memory:" if args.demo else ROOT / "data/netwatch.sqlite3", demo=args.demo)
        service = Service(cfg, store, demo=args.demo)
        if not args.web_only:
            service.start()
        app = create_app(cfg, store, args.demo, service.channels)
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        print(f"Dashboard: http://127.0.0.1:{args.port} | {'MÔ PHỎNG' if args.demo else 'LAB THẬT'}", flush=True)
        print("Ctrl+C để dừng. Mật khẩu/token chỉ đọc từ .env.netwatch.", flush=True)
        try:
            app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)
        finally:
            service.shutdown()
            if all(not t.is_alive() for t in service.threads):
                store.close()
    except (ValueError, OSError, KeyError) as exc:
        print(f"Chưa khởi chạy ({type(exc).__name__}). Kiểm tra inventory, file cấu hình và kết nối.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
