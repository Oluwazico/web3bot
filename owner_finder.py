"""
Owner Finder Orchestrator
Combines Telegram + Twitter finders to get the best owner contact.
"""

import asyncio
import aiohttp
from telegram_finder import find_telegram_owner, format_tg_contact
from finders.twitter_finder  import find_twitter_owner,  format_twitter_contact
from utils.config import logger


async def find_owner(project: dict) -> dict:
    """
    Given a project dict with socials, finds the owner/founder.
    Returns enriched project with owner info added.
    """
    socials = project.get("socials", {})
    owner   = {
        "telegram": None,
        "twitter":  None,
        "found":    False,
    }

    async with aiohttp.ClientSession() as session:
        tasks = []

        tg_url = socials.get("telegram")
        tw_url = socials.get("twitter")

        if tg_url:
            tasks.append(find_telegram_owner(session, tg_url))
        else:
            tasks.append(asyncio.coroutine(lambda: {})())

        if tw_url:
            tasks.append(find_twitter_owner(session, tw_url))
        else:
            tasks.append(asyncio.coroutine(lambda: {})())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        tg_owner = results[0] if not isinstance(results[0], Exception) else {}
        tw_owner = results[1] if not isinstance(results[1], Exception) else {}

        if tg_owner and tg_owner.get("username"):
            owner["telegram"] = tg_owner
            owner["found"]    = True

        if tw_owner and tw_owner.get("handle"):
            owner["twitter"] = tw_owner
            owner["found"]   = True

    project["owner"] = owner
    return project


def format_project_card(project: dict) -> str:
    """
    Formats a clean Telegram message card for a new project.
    """
    name     = project.get("name", "Unknown")
    symbol   = project.get("symbol", "???")
    chain    = project.get("chain", "unknown").upper()
    contract = project.get("contract", "N/A")
    source   = project.get("source", "unknown")
    dex_url  = project.get("dex_url", "")
    socials  = project.get("socials", {})
    owner    = project.get("owner", {})
    liq      = project.get("liquidity_usd", 0)

    # Socials
    tg_link  = socials.get("telegram") or "❌"
    tw_link  = socials.get("twitter")  or "❌"
    dc_link  = socials.get("discord")  or "❌"
    web_link = socials.get("website")  or "❌"

    # Owner contacts
    tg_owner = format_tg_contact(owner.get("telegram")) if owner.get("telegram") else "❌ Not found"
    tw_owner = format_twitter_contact(owner.get("twitter")) if owner.get("twitter") else "❌ Not found"

    liq_str  = f"${liq:,.0f}" if liq else "N/A"

    card = f"""
🚨 *NEW PROJECT DETECTED*

📌 *{name}* (${symbol}) — {chain}
🔗 Contract: `{contract}`
💧 Liquidity: {liq_str}
📡 Source: {source}

━━━━━━━━━━━━━━━━
🌐 *SOCIALS*
• Telegram: {tg_link}
• Twitter/X: {tw_link}
• Discord: {dc_link}
• Website: {web_link}

━━━━━━━━━━━━━━━━
👤 *OWNER / FOUNDER*
• Telegram: {tg_owner}
• Twitter/X: {tw_owner}

━━━━━━━━━━━━━━━━
📊 [View on DEX]({dex_url})
""".strip()

    return card
