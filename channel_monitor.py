"""
Telegram Channel Monitor (Telethon)
- Joins channels as a regular user (read-only)
- Listens for new messages
- Extracts contract address, name, ticker, chain, socials from post text
- Returns parsed project dict same format as platform scrapers
"""

import re
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat
from utils.config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE,
    load_channels, logger
)

# Contract address patterns
EVM_RE  = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
SOL_RE  = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# Ticker pattern like $BULL $PEPE
TICKER_RE = re.compile(r'\$([A-Z]{2,10})\b')

# Chain detection from text
CHAIN_KEYWORDS = {
    "sol": "solana", "solana": "solana",
    "eth": "ethereum", "ethereum": "ethereum", "erc": "ethereum",
    "bsc": "bsc", "bnb": "bsc",
    "base": "base",
    "arb": "arbitrum", "arbitrum": "arbitrum",
    "avax": "avalanche", "avalanche": "avalanche",
    "matic": "polygon", "polygon": "polygon",
}

# Socials extraction
TG_RE   = re.compile(r'https?://t\.me/([a-zA-Z0-9_]+)', re.IGNORECASE)
TW_RE   = re.compile(r'https?://(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)', re.IGNORECASE)
DC_RE   = re.compile(r'https?://discord\.(?:gg|com/invite)/([a-zA-Z0-9_]+)', re.IGNORECASE)
WEB_RE  = re.compile(r'https?://(?!t\.me|twitter\.com|x\.com|discord\.)[^\s]+', re.IGNORECASE)


def parse_project_from_message(text: str, channel_name: str) -> dict | None:
    """
    Parse a Telegram message and extract project info.
    Returns None if no contract address found.
    """
    if not text:
        return None

    # Extract contract address
    contract = None
    chain    = "unknown"

    evm_match = EVM_RE.search(text)
    sol_match = SOL_RE.search(text)

    if evm_match:
        contract = evm_match.group().lower()
        chain    = "ethereum"
    elif sol_match:
        contract = sol_match.group()
        chain    = "solana"

    if not contract:
        return None

    # Detect chain from text keywords
    text_lower = text.lower()
    for keyword, chain_name in CHAIN_KEYWORDS.items():
        if keyword in text_lower:
            chain = chain_name
            break

    # Extract ticker
    ticker_match = TICKER_RE.search(text)
    symbol = ticker_match.group(1) if ticker_match else "???"

    # Extract name — first non-empty line usually has it
    name = "Unknown"
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line) > 2 and not line.startswith("http") and not line.startswith("0x"):
            # Clean up common channel post prefixes
            clean = re.sub(r'[🔥🚀💎🌙⭐🎯🎲]+', '', line).strip()
            clean = re.sub(r'\$[A-Z]+', '', clean).strip()
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean and len(clean) > 2:
                name = clean[:50]
                break

    # Extract socials from the message itself
    tg_matches  = TG_RE.findall(text)
    tw_matches  = TW_RE.findall(text)
    dc_matches  = DC_RE.findall(text)
    web_matches = WEB_RE.findall(text)

    # Filter out common non-project telegram links
    ignore_tg = {"joinchat", "share", "telegram", "madapescalls"}
    tg_links  = [f"https://t.me/{u}" for u in tg_matches if u.lower() not in ignore_tg]
    tw_links  = [f"https://twitter.com/{u}" for u in tw_matches if u.lower() not in ("home", "search", "i")]
    dc_links  = [f"https://discord.gg/{u}" for u in dc_matches]
    web_links = [u for u in web_matches if not any(x in u for x in ["t.me", "twitter", "x.com", "discord", "dexscreener", "pump.fun"])]

    socials = {
        "telegram": tg_links[0]  if tg_links  else None,
        "twitter":  tw_links[0]  if tw_links  else None,
        "discord":  dc_links[0]  if dc_links  else None,
        "website":  web_links[0] if web_links else None,
    }

    return {
        "contract":      contract,
        "name":          name,
        "symbol":        symbol,
        "chain":         chain,
        "price_usd":     0,
        "liquidity_usd": 0,
        "dex_url":       f"https://dexscreener.com/{chain}/{contract}",
        "socials":       socials,
        "source":        f"channel:{channel_name}",
        "raw_text":      text[:500],
    }


class ChannelMonitor:
    """
    Telethon-based channel monitor.
    Runs alongside the main bot and pushes new projects to a queue.
    """

    def __init__(self, project_queue: asyncio.Queue, seen: set):
        self.queue   = project_queue
        self.seen    = seen
        self.client  = None
        self.running = False

    async def start(self):
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            logger.warning("Telethon API credentials not set — channel monitoring disabled")
            return

        self.client = TelegramClient("web3hunter_session", TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await self.client.start(phone=TELEGRAM_PHONE)
        logger.info("Telethon client connected")

        channels = load_channels()
        if not channels:
            logger.warning("No channels configured. Add channels to MONITOR_CHANNELS in .env or use /addchannel")
            return

        # Join channels if not already joined
        for ch in channels:
            try:
                entity = await self.client.get_entity(ch)
                logger.info(f"Monitoring channel: {ch} ({getattr(entity, 'title', ch)})")
            except Exception as e:
                logger.warning(f"Could not access channel {ch}: {e}")

        # Register message handler
        @self.client.on(events.NewMessage(chats=channels))
        async def handle_new_message(event):
            try:
                text         = event.message.text or ""
                channel_name = getattr(event.chat, "username", None) or str(event.chat_id)

                project = parse_project_from_message(text, channel_name)
                if not project:
                    return

                contract = project["contract"]
                if contract in self.seen:
                    logger.info(f"Duplicate skipped: {contract} (already seen)")
                    return

                logger.info(f"New project from channel @{channel_name}: {project['name']} ({project['symbol']})")
                await self.queue.put(project)

            except Exception as e:
                logger.error(f"Channel message handler error: {e}")

        self.running = True
        logger.info(f"Listening to {len(channels)} channel(s)...")
        await self.client.run_until_disconnected()

    async def stop(self):
        self.running = False
        if self.client:
            await self.client.disconnect()

    async def join_channel(self, channel: str) -> bool:
        """Join a new channel dynamically."""
        if not self.client:
            return False
        try:
            await self.client.get_entity(channel)
            return True
        except Exception as e:
            logger.warning(f"Could not join {channel}: {e}")
            return False
