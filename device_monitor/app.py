from __future__ import annotations

import argparse
import logging
from pathlib import Path
import threading
import time
from .config import Config, load_environment_file
from .errors import ConfigError, DataError, DeviceUnavailable
from .validation import number, env_number, env_bool
from .models import Sample, Delivery, METRIC_LABELS
from .engine import metric_state
from .storage import Store
from .notifications import Channel, Dispatcher
from .collectors.ssh import SSHCollector, cpu_percent, ram_percent, windows_command, windows_sample
from .collectors.snmp import SNMPCollector
from .collectors.hybrid import HybridCollector

LOG = logging.getLogger("device_monitor")

def make_collector(config):
    if config.protocol=="ssh":
        return SSHCollector(config)
    if config.protocol=="snmp":
        return SNMPCollector(config)
    return HybridCollector(config,SSHCollector(config),SNMPCollector(config))

def poll(collector, store, config, channels, view=None):
    if view:
        view.collecting()
    try:
        sample = collector.collect()
    except DeviceUnavailable as exc:
        store.observe(config, None, channels, connection_error=str(exc))
        if view:
            view.device_failed(str(exc))
        LOG.warning("%s", exc)
        return False
    store.observe(config, sample, channels)
    if view:
        view.sample_received(sample)
    else:
        for metric, value in sample.values.items():
            display = f"{value:.1f}{'°C' if metric == 'temp' else '%'}" if isinstance(value, (int, float)) else value
            if "DEMO" in sample.sources.get(metric,"").upper():
                display = f"{display} [MÔ PHỎNG]"
            LOG.info("%s=%s%s", metric, display if value is not None else "UNKNOWN", f" ({sample.errors[metric]})" if metric in sample.errors else "")
    return not sample.errors and all(metric_state(k, v, {}, config) != "UNKNOWN" for k, v in sample.values.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Giám sát GNS3 / Linux qua SSH, SNMP và cảnh báo Telegram/Slack")
    parser.add_argument("--once", action="store_true", help="Thu thập một lần và thử gửi các cảnh báo đang đến hạn")
    parser.add_argument("--check-config", action="store_true", help="Kiểm tra cấu hình/dependency mà không kết nối thiết bị hay gửi tin")
    parser.add_argument("--test-notifications", action="store_true", help="Tạo tin kiểm thử trong outbox và thử gửi tới các kênh đã cấu hình")
    parser.add_argument("--env-file", help="Chọn file dotenv ưu tiên hơn biến môi trường; mặc định .env cạnh script, ưu tiên biến môi trường")
    parser.add_argument("--display", choices=("auto", "table", "log"), default="auto",
                        help="auto: bảng cập nhật tại chỗ trong Terminal; table: in bảng mỗi chu kỳ; log: dòng log gọn")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    channels, worker, collector = [], None, None
    view = None
    stop = threading.Event()
    try:
        load_environment_file(args.env_file)
        config = Config.from_env()
        if config.telegram_token:
            channels.append(Channel("telegram", config.telegram_token, config.telegram_chat))
        if config.slack_webhook:
            channels.append(Channel("slack", config.slack_webhook))
        keys = [c.key for c in channels]
        if args.test_notifications:
            store=Store(config.state_file)
            store.enqueue(keys,f"[KIỂM THỬ KÊNH CẢNH BÁO]\nThiết bị: {config.host}\nGNS3 Device Monitor: tin kiểm tra do người dùng yêu cầu.")
            failed=Dispatcher(store,channels).tick()
            _,queues=store.display_snapshot(config,keys)
            return 0 if not failed and all(q["pending"]==0 for q in queues.values()) else 1
        collector=make_collector(config)
        if args.check_config:
            LOG.info("Cấu hình và dependency hợp lệ; chưa kiểm tra kết nối hoặc gửi tin")
            return 0
        store = Store(config.state_file)
        if args.display != "log":
            from .ui import TerminalDashboard
            view = TerminalDashboard(config, store, channels, live=args.display == "auto" and not args.once)
            view.start()
        dispatcher = Dispatcher(store, channels, view=view)
        if args.once:
            healthy = poll(collector, store, config, keys, view=view)
            failed = dispatcher.tick()
            if view:
                view.show_once()
            with store.connect() as db:
                pending = sum(db.execute("SELECT COUNT(*) FROM outbox WHERE channel=?", (key,)).fetchone()[0] for key in keys)
            return 0 if healthy and not failed and not pending else 1
        worker = threading.Thread(target=dispatcher.run, args=(stop,), name="notifications", daemon=True)
        worker.start()
        LOG.info("Giám sát %s qua %s mỗi %gs", config.host, config.protocol.upper(), config.interval)
        deadline = time.monotonic()
        while not stop.is_set():
            poll(collector, store, config, keys, view=view)
            deadline += config.interval
            now = time.monotonic()
            if deadline < now:
                LOG.warning("Chu kỳ thu thập vượt thời gian cấu hình; bỏ qua lịch đã trễ")
                deadline = now + config.interval
            if view:
                view.schedule(deadline)
                view.show_once()
            stop.wait(max(0, deadline - now))
        return 1  # Worker failed; let a supervisor restart the monitor.
    except KeyboardInterrupt:
        LOG.info("Đã dừng giám sát; cảnh báo chưa gửi vẫn được lưu")
        return 0
    except (ConfigError, ImportError) as exc:
        LOG.error("%s", str(exc) if isinstance(exc, ConfigError) else "Thiếu dependency; xem requirements và README")
        return 2
    except Exception as exc:
        LOG.error("Lỗi nội bộ (%s); xem cấu hình, quyền ghi state và dependency", type(exc).__name__)
        return 2
    finally:
        stop.set()
        close_collector = getattr(collector, "close", None)
        if close_collector is not None:
            close_collector()
        if worker:
            worker.join(timeout=35)
        if not worker or not worker.is_alive():
            for channel in channels:
                channel.close()
        if view:
            view.stop()
