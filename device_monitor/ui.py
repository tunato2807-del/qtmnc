"""Readable terminal dashboard. Rendering never changes monitoring or alert state."""
from collections import deque
import logging
import math
import threading
import time

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

LOGGER = logging.getLogger("device_monitor")
STYLES = {"OK": "green", "ALERT": "bold red", "UNKNOWN": "yellow"}
LABELS = {"OK": "BÌNH THƯỜNG", "ALERT": "CẢNH BÁO", "UNKNOWN": "KHÔNG XÁC ĐỊNH"}


class _Events(logging.Handler):
    def __init__(self, view):
        super().__init__(logging.INFO)
        self.view = view

    def emit(self, record):
        self.view.note(record.levelname, record.getMessage())


class TerminalDashboard:
    def __init__(self, config, store, channels, live=True, console=None):
        self.config, self.store, self.channels = config, store, channels
        self.console = console if console is not None else Console()
        self.use_live = live and self.console.is_terminal and not self.console.is_dumb_terminal
        self.lock = threading.RLock()
        self.values, self.errors, self.states = {}, {}, {}
        self.sources={}
        self.connected = None
        self.busy = False
        self.last_sample = None
        self.deadline = None
        self.connection_error = ""
        self.events = deque(maxlen=4)
        self.last_sent = {}
        self.sending_keys = set()
        self.live = None
        self.started = False
        self.stopped = False
        self.handler = _Events(self)
        self.saved_logging = None

    def start(self):
        self.saved_logging = (LOGGER.propagate, LOGGER.level, logging.getLogger("paramiko").level)
        LOGGER.addHandler(self.handler)
        LOGGER.propagate = False
        LOGGER.setLevel(logging.INFO)
        logging.getLogger("paramiko").setLevel(logging.CRITICAL)
        self.started = True
        if self.use_live:
            self.live = Live(get_renderable=self.render, console=self.console,
                             refresh_per_second=2, redirect_stdout=False, redirect_stderr=False)
            self.live.start(refresh=True)

    def stop(self):
        with self.lock:
            self.stopped = True
            self.busy = False
            self.sending_keys.clear()
        try:
            if self.live:
                self.live.stop()
        finally:
            if self.saved_logging is not None:
                LOGGER.removeHandler(self.handler)
                LOGGER.propagate, level, paramiko_level = self.saved_logging
                LOGGER.setLevel(level)
                logging.getLogger("paramiko").setLevel(paramiko_level)
                self.saved_logging = None
            self.started = False

    def note(self, level, message):
        style = "red" if level in {"ERROR", "CRITICAL"} else "yellow" if level == "WARNING" else "cyan"
        event = (time.time(), message, style)
        with self.lock:
            self.events.append(event)
        if self.started and not self.use_live:
            self.console.print(Text(time.strftime("%H:%M:%S") + "  " + message, style=style))

    def collecting(self):
        with self.lock:
            self.busy = True

    def sample_received(self, sample):
        states, _ = self.store.display_snapshot(self.config, [])
        with self.lock:
            self.values, self.errors, self.states = dict(sample.values), dict(sample.errors), states
            self.sources=dict(sample.sources)
            self.connected = True
            self.busy = False
            self.connection_error = ""
            self.last_sample = time.time()

    def device_failed(self, reason):
        with self.lock:
            self.connected = False
            self.busy = False
            self.connection_error = reason

    def sending(self, key):
        with self.lock:
            self.sending_keys.add(key)

    def delivery(self, key, result):
        with self.lock:
            self.sending_keys.discard(key)
            if result.ok:
                self.last_sent[key] = time.time()

    def schedule(self, deadline):
        with self.lock:
            self.deadline = deadline

    def show_once(self):
        if not self.use_live:
            self.console.print(self.render())

    def render(self):
        with self.lock:
            values, errors, states = dict(self.values), dict(self.errors), dict(self.states)
            sources=dict(self.sources)
            connected, busy, stopped = self.connected, self.busy, self.stopped
            last_sample, deadline = self.last_sample, self.deadline
            connection_error = self.connection_error
            events, last_sent = list(self.events), dict(self.last_sent)
            sending = set(self.sending_keys)
        keys = [channel.key for channel in self.channels]
        try:
            _, queues = self.store.display_snapshot(self.config, keys)
        except Exception:
            queues = None  # Storage unavailable is never displayed as an empty queue.

        header = Text("GIÁM SÁT THIẾT BỊ", style="bold cyan")
        header.append(f"   {self.config.host}   |   {self.config.protocol.upper()} / {self.config.target_os.upper()}")
        status = Text()
        if stopped:
            status.append("ĐÃ DỪNG", style="bold yellow")
        elif connected is False:
            status.append("MẤT KẾT NỐI", style="bold red")
        elif busy:
            status.append("ĐANG LẤY MẪU", style="cyan")
        elif connected:
            status.append("ĐÃ KẾT NỐI", style="green")
        else:
            status.append("ĐANG CHỜ DỮ LIỆU", style="yellow")
        stamp = time.strftime("%H:%M:%S", time.localtime(last_sample)) if last_sample else "--"
        status.append(f"   |   Dữ liệu gần nhất: {stamp}")
        if deadline is not None and not stopped and not busy:
            status.append(f"   |   Lần kiểm tra tiếp: {max(0, math.ceil(deadline - time.monotonic()))}s")
        status.append(f"   |   Chu kỳ: {self.config.interval:g}s")

        metrics = Table(box=box.ROUNDED, expand=True, header_style="bold cyan")
        metrics.add_column("Chỉ số", no_wrap=True)
        metrics.add_column("Giá trị", no_wrap=True)
        wide = self.console.width >= 100
        if wide:
            metrics.add_column("Mức sử dụng", width=18)
        metrics.add_column("Ngưỡng", no_wrap=True)
        metrics.add_column("Nguồn")
        metrics.add_column("Trạng thái")
        rows=[("cpu","CPU"),("ram","RAM"),("temp","Nhiệt độ"),("iface","Interface")]
        if self.config.protocol=="hybrid":
            rows += [("ssh","Kênh SSH"),("snmp","Kênh SNMP")]
        for metric, label in rows:
            value = values.get(metric)
            disabled = metric == "temp" and not self.config.temp_enabled
            stale = connected is False and metric in values
            state = states.get(metric, {}).get("status", "UNKNOWN")
            style = STYLES.get(state, "yellow")
            threshold = f"> {self.config.thresholds[metric]:g}{'°C' if metric == 'temp' else '%'}" if metric in self.config.thresholds else "--"
            if metric=="temp" and ("DEMO" in sources.get(metric,"").upper() or self.config.temp_source=="demo"):
                label += " (MÔ PHỎNG)"
            if disabled:
                shown, threshold, state_text, style = "--", "--", "ĐÃ TẮT", "dim"
            elif metric not in values:
                shown, state_text, style = "--", "CHƯA CÓ DỮ LIỆU", "yellow"
            else:
                shown = ("--" if value is None else str(value).upper() if metric in {"iface","ssh","snmp"}
                         else f"{value:.1f}{'°C' if metric == 'temp' else '%'}")
                state_text = LABELS.get(state, "KHÔNG XÁC ĐỊNH")
                if stale:
                    shown += " (cũ)"
                    state_text, style = "CHƯA CẬP NHẬT", "yellow"
            row = [Text(label + (f" ({self.config.iface})" if metric == "iface" else "")), Text(shown, style=style)]
            if wide:
                row.append(ProgressBar(total=100, completed=value, width=18,
                                       complete_style=style, finished_style=style)
                           if metric in {"cpu", "ram"} and value is not None and not stale else Text("--", style="dim"))
            row += [threshold,Text("--" if disabled else sources.get(metric,self.config.protocol.upper()),style="dim"),Text(state_text, style=style)]
            metrics.add_row(*row)

        notifications = Table(box=None, expand=True, header_style="bold cyan")
        notifications.add_column("Kênh cảnh báo")
        notifications.add_column("Trạng thái gửi")
        notifications.add_column("Đang chờ", justify="right")
        notifications.add_column("Gửi gần nhất", justify="right")
        for channel in self.channels:
            queue = queues.get(channel.key, {}) if queues is not None else None
            if queue is None:
                message, style, pending = "Không đọc được hàng đợi", "red", "?"
            elif queue.get("pending", 0):
                pending = str(queue["pending"])
                seconds = max(0, math.ceil(queue["next_attempt"] - time.time()))
                message = "Đang gửi..." if channel.key in sending else f"Thử lại sau {seconds}s" if queue["attempts"] and seconds else "Đang chờ gửi"
                style = "cyan" if channel.key in sending else "yellow"
            else:
                pending = "0"
                message = "Đã gửi thành công" if channel.key in last_sent else "Không có tin đang chờ"
                style = "green" if channel.key in last_sent else "dim"
            stamp = time.strftime("%H:%M:%S", time.localtime(last_sent[channel.key])) if channel.key in last_sent else "--"
            notifications.add_row(channel.kind.title(), Text(message, style=style), pending, stamp)

        parts = [Panel(Group(header, status), border_style="cyan"), metrics, notifications]
        if connection_error:
            parts.append(Text(connection_error, style="yellow"))
        if errors:
            parts.append(Text("; ".join(f"{key}: {value}" for key, value in errors.items()), style="yellow"))
        if self.use_live:
            lines = [Text(time.strftime("%H:%M:%S", time.localtime(stamp)) + "  " + message, style=style)
                     for stamp, message, style in events]
            parts.append(Panel(Group(*(lines or [Text("Chưa có sự kiện.", style="dim")])),
                               title="Sự kiện gần đây", border_style="dim"))
        limits = " · ".join(f"{name.upper()} ≤ {limit - self.config.recovery_margin:g}{'°C' if name == 'temp' else '%'}"
                            for name, limit in self.config.thresholds.items() if name != "temp" or self.config.temp_enabled)
        parts.append(Text("Ngưỡng phục hồi: " + limits, style="dim"))
        parts.append(Text("Ctrl+C để dừng. Tin chưa gửi được giữ trên đĩa để thử lại.", style="dim"))
        return Group(*parts)
