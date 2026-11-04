import os
from urllib.parse import urlparse

import requests


def configured_channels():
    channels = []
    if os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        channels.append("telegram")
    webhook = os.getenv("SLACK_WEBHOOK", "")
    if webhook:
        parsed = urlparse(webhook)
        if parsed.scheme != "https" or parsed.hostname not in ("hooks.slack.com", "hooks.slack-gov.com"):
            raise ValueError("SLACK_WEBHOOK phải là HTTPS webhook của Slack")
        channels.append("slack")
    return channels


def send(item, session):
    channel = item["channel"]
    if channel == "telegram":
        token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            return "Kênh chưa được cấu hình", 300
        response = session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": item["message"]}, timeout=10, allow_redirects=False)
        if response.status_code == 429:
            try:
                return "Giới hạn Telegram 429", float(response.json().get("parameters", {}).get("retry_after", 30))
            except (ValueError, TypeError):
                return "Giới hạn Telegram 429", 30
        if response.status_code != 200:
            return f"Telegram HTTP {response.status_code}", None
        try:
            return (None, None) if response.json().get("ok") is True else ("Telegram từ chối yêu cầu", None)
        except ValueError:
            return "Telegram trả dữ liệu không hợp lệ", None
    if channel == "slack":
        # Kiểm tra lại khi xử lý outbox cũ; không gửi tới URL tùy ý.
        if "slack" not in configured_channels():
            return "Kênh chưa được cấu hình", 300
        response = session.post(os.environ["SLACK_WEBHOOK"], json={"text": item["message"]}, timeout=10, allow_redirects=False)
        if response.status_code == 429:
            try:
                delay = float(response.headers.get("Retry-After", "30"))
            except ValueError:
                delay = 30
            return "Giới hạn Slack 429", delay
        return (None, None) if response.status_code == 200 and response.text.strip() == "ok" else (f"Slack HTTP {response.status_code}", None)
    return "Kênh không hợp lệ", 300


def delivery_loop(store, stop):
    with requests.Session() as session:
        while not stop.is_set():
            item = store.due()
            if not item:
                stop.wait(1)
                continue
            try:
                error, delay = send(item, session)
            except Exception as exc:
                error, delay = f"Lỗi gửi ({type(exc).__name__})", None
            store.delivered(item, error, delay)
            if error:
                print(f"{item['channel']}: {error}; giữ hàng đợi để thử lại", flush=True)
