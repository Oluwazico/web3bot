import os
import sys
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False))
    ]
)
logger = logging.getLogger("web3bot")

# Bot config
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_YOUR_USER_ID = int(os.getenv("TELEGRAM_YOUR_USER_ID", "0"))
SCAN_INTERVAL         = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
MAX_PROJECTS_PER_SCAN = int(os.getenv("MAX_PROJECTS_PER_SCAN", "10"))
MIN_LIQUIDITY_USD     = float(os.getenv("MIN_LIQUIDITY_USD", "0"))
TWITTER_AUTH_TOKEN    = os.getenv("TWITTER_AUTH_TOKEN", "")
TWITTER_CT0           = os.getenv("TWITTER_CT0", "")

# Telethon user account
TELEGRAM_API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE    = os.getenv("TELEGRAM_PHONE", "")

# Channels from .env
_raw = os.getenv("MONITOR_CHANNELS", "")
MONITOR_CHANNELS = [c.strip() for c in _raw.split(",") if c.strip()]

# Persistence
SEEN_FILE     = Path("seen_projects.json")
CHANNELS_FILE = Path("channels.json")

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)), encoding="utf-8")

def mark_seen(contract: str, seen: set):
    seen.add(contract.lower())
    save_seen(seen)

def load_channels() -> list:
    base = list(MONITOR_CHANNELS)
    if CHANNELS_FILE.exists():
        saved = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
        for ch in saved:
            if ch not in base:
                base.append(ch)
    return base

def save_channels(channels: list):
    CHANNELS_FILE.write_text(json.dumps(channels), encoding="utf-8")
