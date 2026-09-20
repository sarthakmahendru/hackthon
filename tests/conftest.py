"""Test settings must be set BEFORE the app is imported."""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["SIMULATE"] = "false"
os.environ["USE_LIVE_DATA"] = "false"
os.environ["INGEST_API_KEY"] = ""
os.environ["TWILIO_ACCOUNT_SID"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""
