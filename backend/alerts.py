"""Build human-readable alerts and deliver them (dashboard, log, Telegram)."""
import logging
import time

import httpx

from . import config

log = logging.getLogger("mountainsentinel.alerts")

EMOJI = {"critical": "🔴", "warning": "🟠", "watch": "🟡", "safe": "🟢"}


def _text(title: str, reasons: list, action: str) -> str:
    lines = [title]
    lines += [f"- {r}" for r in reasons[:3]]
    if action:
        lines.append(f"Action: {action}")
    return "\n".join(lines)


def hazard_alert(node: dict, hazard_label: str, hazard: str, level: str, score: int, reasons: list, action: str) -> dict:
    title = f"{EMOJI[level]} {level.capitalize()}: {hazard_label.lower()} risk at {node['name']} ({score}/100)"
    return {
        "ts": time.time(),
        "kind": "hazard",
        "node_id": node["node_id"],
        "node_name": node["name"],
        "hazard": hazard,
        "level": level,
        "score": score,
        "title": title,
        "message": _text(title, reasons, action),
        "reasons": reasons[:4],
        "action": action,
    }


def resolved_alert(node: dict, hazard_label: str, hazard: str) -> dict:
    title = f"{EMOJI['safe']} Back to normal: {hazard_label.lower()} risk at {node['name']}"
    return {
        "ts": time.time(),
        "kind": "resolved",
        "node_id": node["node_id"],
        "node_name": node["name"],
        "hazard": hazard,
        "level": "safe",
        "score": None,
        "title": title,
        "message": title,
        "reasons": [],
        "action": "",
    }


def hiker_alert(hiker: dict, level: str, title_text: str, reasons: list, action: str) -> dict:
    title = f"{EMOJI[level]} {title_text}"
    return {
        "ts": time.time(),
        "kind": "hiker",
        "node_id": None,
        "node_name": hiker["name"],
        "hazard": "hiker",
        "level": level,
        "score": None,
        "title": title,
        "message": _text(title, reasons, action),
        "reasons": reasons,
        "action": action,
    }


def camera_alert(cam: dict, level: str, title_text: str, reasons: list, action: str, image: str = None) -> dict:
    title = f"{EMOJI[level]} {title_text}"
    return {
        "ts": time.time(),
        "kind": "camera",
        "node_id": None,
        "node_name": cam["name"],
        "hazard": "camera",
        "level": level,
        "score": None,
        "title": title,
        "message": _text(title, reasons, action),
        "reasons": reasons,
        "action": action,
        "image": image,
    }


class Alerter:
    """Sends alerts to Telegram when configured. Never raises: alerts must not crash ingestion."""

    def __init__(self):
        self.telegram_enabled = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        self.sent = 0

    async def send(self, alert: dict) -> None:
        log.warning("ALERT %s", alert["title"])
        if not self.telegram_enabled:
            return
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": alert["message"]})
                if resp.status_code == 200:
                    self.sent += 1
                else:
                    log.error("Telegram error %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            log.error("Telegram send failed: %s", exc)
