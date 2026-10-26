"""Bản dễ học: cấu hình -> đọc SSH -> đánh giá -> gửi tin -> lặp lại.

Đọc file này để hiểu luồng chính. Thư mục device_monitor chứa phần xử lý
chi tiết SSH, bảng hiển thị và gửi lại tin khi mất Internet.
"""
import argparse
import logging
from pathlib import Path
import threading
import time

from device_monitor.app import poll
from device_monitor.config import Config, load_environment_file
from device_monitor.collectors.ssh import SSHCollector
from device_monitor.errors import ConfigError
from device_monitor.notifications import Channel, Dispatcher
from device_monitor.storage import Store
from device_monitor.ui import TerminalDashboard

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("device_monitor")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Windows -> GNS3 -> Linux: giám sát SSH")
    parser.add_argument("--env-file", default=str(ROOT / ".env.simple"))
    parser.add_argument("--once", action="store_true", help="Đọc một lần rồi dừng")
    parser.add_argument("--test", action="store_true", help="Gửi tin thử Telegram/Slack")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    channels, worker, view = [], None, None
    stop = threading.Event()
    try:
        # 1. Đọc cấu hình. Mật khẩu/token ở file cục bộ, không viết trong code.
        load_environment_file(args.env_file)
        config = Config.from_env()
        if config.protocol != "ssh" or config.target_os != "linux":
            raise ConfigError("Bản đơn giản dùng MONITOR_PROTOCOL=ssh, MONITOR_OS=linux")
        if config.telegram_token:
            channels.append(Channel("telegram", config.telegram_token, config.telegram_chat))
        if config.slack_webhook:
            channels.append(Channel("slack", config.slack_webhook))
        keys = [channel.key for channel in channels]
        store = Store(config.state_file)
        sender = Dispatcher(store, channels)
        if args.test:
            store.enqueue(keys, f"[TIN THỬ] Windows giám sát Linux {config.host} qua GNS3.")
            sender.tick()
            _, queues = store.display_snapshot(config, keys)
            pending = sum(queue["pending"] for queue in queues.values())
            print("Đã gửi tin thử." if pending == 0 else "Còn tin chờ; chạy lại monitor để tự thử gửi tiếp.")
            return 0 if pending == 0 else 1

        # 2. Chuẩn bị SSH và bảng CPU/RAM/nhiệt độ/interface.
        collector = SSHCollector(config)
        view = TerminalDashboard(config, store, channels, live=not args.once)
        view.start()
        sender = Dispatcher(store, channels, view=view)
        if not args.once:
            # Gửi tin ở luồng riêng để lỗi Internet không chặn việc đọc SSH.
            worker = threading.Thread(target=sender.run, args=(stop,), daemon=True)
            worker.start()

        while not stop.is_set():
            # 3. Đọc SSH, so ngưỡng và lưu tin mới khi trạng thái thay đổi.
            healthy = poll(collector, store, config, keys, view=view)
            if args.once:
                sender.tick()
            # 4. Hiển thị kết quả; luồng gửi sẽ xử lý các tin đang chờ.
            deadline = time.monotonic() + config.interval
            view.schedule(deadline)
            view.show_once()
            if args.once:
                _, queues = store.display_snapshot(config, keys)
                return 0 if healthy and all(q["pending"] == 0 for q in queues.values()) else 1
            stop.wait(max(0, deadline - time.monotonic()))
        return 1
    except KeyboardInterrupt:
        LOG.info("Đã dừng. Tin chưa gửi được giữ lại.")
        return 0
    except ConfigError as exc:
        LOG.error("%s. Chạy setup_windows.cmd --configure để sửa.", exc)
        return 2
    except Exception as exc:
        LOG.error("Chưa chạy được (%s); xem hướng dẫn HUONG_DAN_DON_GIAN.md.", type(exc).__name__)
        return 2
    finally:
        stop.set()
        if worker:
            worker.join(timeout=35)
        if not worker or not worker.is_alive():
            for channel in channels:
                channel.close()
        if view:
            view.stop()


if __name__ == "__main__":
    raise SystemExit(main())
