"""All settings come from environment variables (or a .env file). See .env.example."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "mountainsentinel.db"))

SIMULATE = _flag("SIMULATE", "true")
SIM_INTERVAL_S = float(os.getenv("SIM_INTERVAL_S", "2"))
USE_LIVE_DATA = _flag("USE_LIVE_DATA", "true")

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "")

ALERT_COOLDOWN_S = float(os.getenv("ALERT_COOLDOWN_S", "20"))
HIKER_OVERDUE_S = float(os.getenv("HIKER_OVERDUE_S", "40"))

# ---- Phone alerts (SMS / WhatsApp through Twilio). Optional: without keys, messages are
# ---- shown in the dashboard "message log" as demo-mode instead of being sent.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "")  # your Twilio phone number, e.g. +15551234567
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox number
DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_COUNTRY_CODE", "+91")  # used when a number has no +country code
MAX_SUBSCRIBERS = int(os.getenv("MAX_SUBSCRIBERS", "25"))
CAMERA_STALE_S = float(os.getenv("CAMERA_STALE_S", "30"))
