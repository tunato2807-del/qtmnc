from __future__ import annotations

import hashlib
import logging
import time
from .models import Delivery
from .errors import DataError
from .validation import number

LOG = logging.getLogger("device_monitor")

class Channel:
    def __init__(self, kind, target, recipient="", session=None):
        self.kind, self.target, self.recipient = kind, target, recipient
        # Credentials may rotate. Keep pending deliveries attached to the recipient,
        # not the old secret. This application has one Slack destination per state file.
        self.key = "telegram:" + hashlib.sha256(recipient.encode()).hexdigest() if kind == "telegram" else "slack"
        if session is None:
            import requests
            session = requests.Session()
            # The persistent outbox manages retries, including POST and HTTP 429.
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        self.session = session

    def send(self, message):
        url = f"https://api.telegram.org/bot{self.target}/sendMessage" if self.kind == "telegram" else self.target
        payload = {"chat_id": self.recipient, "text": message} if self.kind == "telegram" else {"text": message, "mrkdwn": False}
        try:
            response = self.session.post(url, json=payload, timeout=(5, 10), allow_redirects=False)
            try:
                data = response.json() if self.kind == "telegram" else {}
            except ValueError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            if response.status_code == 429:
                params = data.get("parameters", {})
                raw = params.get("retry_after") if isinstance(params, dict) else None
                try:
                    retry_after = number(raw if raw is not None else response.headers.get("Retry-After", 30), 0)
                except DataError:
                    retry_after = 30
                return Delivery(False, "HTTP 429: giới hạn tần suất", retry_after)
            if not 200 <= response.status_code < 300:
                return Delivery(False, f"HTTP {response.status_code}")
            if self.kind == "telegram" and data.get("ok") is not True:
                return Delivery(False, "Telegram chưa xác nhận ok=true")
            if self.kind == "slack" and response.text.strip() != "ok":
                return Delivery(False, "Slack chưa xác nhận ok")
            return Delivery(True)
        except Exception as exc:
            # requests exceptions may expose the token/webhook through their URL.
            return Delivery(False, f"Lỗi gửi ({type(exc).__name__})")

    def close(self):
        self.session.close()


class Dispatcher:
    def __init__(self, store, channels, view=None):
        self.store, self.channels = store, channels
        self.view = view

    def tick(self):
        failures = 0
        for channel in self.channels:
            event = self.store.due(channel.key, time.time())
            if event is None:
                continue
            event_id, message, attempts, _ = event
            if self.view:
                self.view.sending(channel.key)
            result = channel.send(message)
            if result.ok:
                self.store.delivered(event_id)
                if self.view:
                    self.view.delivery(channel.key, result)
                LOG.info("Đã gửi cảnh báo qua %s", channel.kind)
            else:
                self.store.failed(event_id, attempts, result.retry_after)
                if self.view:
                    self.view.delivery(channel.key, result)
                LOG.warning("%s: %s; đã giữ cảnh báo để thử lại", channel.kind, result.reason)
                failures += 1
        return failures

    def run(self, stop):
        try:
            while not stop.is_set():
                self.tick()
                stop.wait(0.5)
        except Exception as exc:
            LOG.error("Luồng gửi cảnh báo dừng (%s); dừng chương trình để tránh mất giám sát", type(exc).__name__)
            stop.set()
