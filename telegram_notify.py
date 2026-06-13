import os
import requests
from logger import get_logger

log = get_logger(__name__)

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text):
    """Send a Telegram message. No-op (logged) if token/chat id are not set.

    Never raises — notification failures must not break the pipeline.
    """
    if not _BOT_TOKEN or not _CHAT_ID:
        log.warning("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing), skipping notification")
        return

    url = f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": _CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        log.info("Telegram notification sent")
    except requests.exceptions.RequestException as e:
        log.warning(f"Failed to send Telegram notification: {e}")
