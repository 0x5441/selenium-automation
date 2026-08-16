import logging
import requests
from typing import List, Dict

logger = logging.getLogger(__name__)


def send_telegram_summary(env: Dict[str, str], results: List[Dict]):
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (env.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        logger.info("Telegram credentials not provided; skipping notifications")
        return

    total = len(results)
    success = sum(1 for r in results if r.get("status") == "success")
    failed = total - success
    duration = sum(r.get("duration_seconds") or 0 for r in results)

    text = (
        f"Batch finished\nTotal: {total}\nSuccess: {success}\nFailed: {failed}\nDuration (s): {duration:.1f}"
    )
    # Do not print or log the token
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send telegram notification")
