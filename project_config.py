import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

TRAVEL_DB_PATH = PROJECT_ROOT / "travel_new.sqlite"
TRAVEL_DB_BACKUP_PATH = PROJECT_ROOT / "travel2.sqlite"
ORDER_FAQ_PATH = PROJECT_ROOT / "order_faq.md"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
