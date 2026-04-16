from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / "backend" / ".env")

APP_NAME = os.getenv("APP_NAME", "ChatAction Desk Backend")
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "chataction_desk.db"))
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "replace_this_token")
API_KEY = os.getenv("API_KEY", "local-dev-key")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SHARED_RULES_PATH = os.getenv("SHARED_RULES_PATH", str(BASE_DIR / "shared" / "default_rules.json"))
