"""Send alerts to phone numbers people enter in the dashboard.

Channels
  * sms       : Twilio SMS
  * whatsapp  : Twilio WhatsApp (sandbox works for demos)

If Twilio keys are not configured the message is NOT sent. It is written to the message log
with status "demo", so the whole flow can still be shown to judges without any account.
"""
import asyncio
import logging
import re
import time
from collections import deque
from typing import Callable, Optional

import httpx

from . import config
from . import database as db

log = logging.getLogger("mountainsentinel.notifier")

LEVEL_RANK = {"safe": 0, "watch": 1, "warning": 2, "critical": 3}
_EMOJI_PREFIX = "🔴🟠🟡🟢 "


def normalize_phone(raw: str, default_cc: str = None) -> str:
    """Return the number in international format (+919876543210) or raise ValueError."""
    default_cc = default_cc or config.DEFAULT_COUNTRY_CODE
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        cc = default_cc.lstrip("+")
        if s.startswith(cc) and len(s) >= len(cc) + 10:
            s = "+" + s  # user typed 919876543210
        else:
            s = default_cc + s.lstrip("0")
    if not re.fullmatch(r"\+[1-9]\d{7,14}", s):
        raise ValueError("Enter a valid mobile number, for example 98765 43210 or +91 98765 43210.")
    return s


def mask_phone(phone: str) -> str:
    return phone[:3] + "•" * max(0, len(phone) - 6) + phone[-3:]


def sms_text(alert: dict) -> str:
    title = alert["title"].lstrip(_EMOJI_PREFIX)
    parts = [f"MountainSentinel: {title}."]
    if alert.get("reasons"):
        parts.append(alert["reasons"][0])
    if alert.get("action"):
        parts.append(f"Action: {alert['action']}")
    text = " ".join(parts)
    return text if len(text) <= 300 else text[:297] + "..."


class Notifier:
    def __init__(self):
        self.outbox = deque(maxlen=30)
        self.on_log: Optional[Callable] = None  # called with each new outbox entry

    # ------------------------------------------------------------ status
    @staticmethod
    def configured(channel: str) -> bool:
        if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN):
            return False
        return bool(config.TWILIO_SMS_FROM) if channel == "sms" else bool(config.TWILIO_WHATSAPP_FROM)

    def status(self) -> dict:
        return {"sms": self.configured("sms"), "whatsapp": self.configured("whatsapp")}

    # ------------------------------------------------------------ sending
    async def _twilio(self, to: str, channel: str, body: str) -> None:
        if channel == "whatsapp":
            to_, from_ = f"whatsapp:{to}", config.TWILIO_WHATSAPP_FROM
        else:
            to_, from_ = to, config.TWILIO_SMS_FROM
        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                url,
                auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                data={"To": to_, "From": from_, "Body": body},
            )
        if resp.status_code >= 300:
            try:
                detail = resp.json().get("message", resp.text[:150])
            except Exception:
                detail = resp.text[:150]
            raise RuntimeError(detail)

    async def send(self, sub: dict, body: str) -> dict:
        entry = {
            "ts": time.time(),
            "to": mask_phone(sub["phone"]),
            "name": sub["name"],
            "channel": sub["channel"],
            "preview": body[:160],
        }
        if not self.configured(sub["channel"]):
            entry["status"] = "demo"
            entry["detail"] = "Twilio is not configured, so nothing was sent. This shows what would be sent."
        else:
            try:
                await self._twilio(sub["phone"], sub["channel"], body)
                entry["status"] = "sent"
                entry["detail"] = "Delivered to Twilio."
            except Exception as exc:
                entry["status"] = "failed"
                entry["detail"] = str(exc)[:160]
                log.error("Twilio send failed: %s", exc)
        self.outbox.appendleft(entry)
        if self.on_log:
            try:
                await self.on_log(entry)
            except Exception:
                pass
        return entry

    async def notify(self, alert: dict) -> None:
        """Send an alert to every subscriber whose minimum level it reaches."""
        if alert.get("kind") == "resolved" or LEVEL_RANK.get(alert["level"], 0) < 2:
            return
        subs = [s for s in db.list_subscribers() if LEVEL_RANK[alert["level"]] >= LEVEL_RANK[s["min_level"]]]
        if not subs:
            return
        await asyncio.gather(
            *(self.send(s, sms_text(alert) if s["channel"] == "sms" else alert["message"]) for s in subs),
            return_exceptions=True,
        )
