"""
Telegram Owner Finder
- Joins or previews a Telegram group/channel
- Scans members/admins for Owner or Admin tag
- Returns owner username if found
"""

import re
import aiohttp
from utils.config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Extract @username or t.me/username from a URL
TG_USERNAME_RE = re.compile(r'(?:t\.me/|telegram\.me/)([a-zA-Z0-9_]{5,})', re.IGNORECASE)


async def find_telegram_owner(session: aiohttp.ClientSession, tg_url: str) -> dict:
    """
    Given a Telegram group/channel URL, tries to find the owner.
    Returns: { username, display_name, role, profile_url }
    """
    result = {"username": None, "display_name": None, "role": None, "profile_url": None}

    if not tg_url:
        return result

    # Extract username from URL
    match = TG_USERNAME_RE.search(tg_url)
    if not match:
        return result

    username = match.group(1)

    # Try the widget preview API (no auth needed)
    widget_result = await try_telegram_widget(session, username)
    if widget_result["username"]:
        return widget_result

    # Try preview.telegram.org scrape
    preview_result = await try_telegram_preview(session, username)
    return preview_result


async def try_telegram_widget(session: aiohttp.ClientSession, username: str) -> dict:
    """Try Telegram's embed widget to get group info."""
    result = {"username": None, "display_name": None, "role": None, "profile_url": None}
    try:
        url = f"https://t.me/{username}?embed=1"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return result
            html = await resp.text()

            # Look for owner/admin patterns in the page
            owner_patterns = [
                r'(?:owner|founder|creator)[^<]*@([a-zA-Z0-9_]{5,})',
                r'@([a-zA-Z0-9_]{5,})[^<]*(?:owner|founder|creator)',
            ]
            for pattern in owner_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    found_username = match.group(1)
                    result["username"] = found_username
                    result["role"] = "Owner/Founder"
                    result["profile_url"] = f"https://t.me/{found_username}"
                    return result

    except Exception as e:
        logger.debug(f"Telegram widget error for {username}: {e}")
    return result


async def try_telegram_preview(session: aiohttp.ClientSession, username: str) -> dict:
    """Scrape Telegram preview page for admin/owner info."""
    result = {"username": None, "display_name": None, "role": None, "profile_url": None}
    try:
        url = f"https://t.me/s/{username}"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return result
            html = await resp.text()

            # Look for admin badges and usernames
            # Pattern: username near "owner" or "admin" text
            sections = re.findall(
                r'<div[^>]*class="[^"]*(?:admin|owner|member)[^"]*"[^>]*>(.*?)</div>',
                html, re.IGNORECASE | re.DOTALL
            )
            for section in sections:
                username_match = re.search(r'@([a-zA-Z0-9_]{5,})', section)
                role_match     = re.search(r'(owner|founder|admin|creator)', section, re.IGNORECASE)
                if username_match:
                    result["username"]     = username_match.group(1)
                    result["role"]         = role_match.group(1).title() if role_match else "Admin"
                    result["profile_url"]  = f"https://t.me/{username_match.group(1)}"
                    # Prefer owner over admin
                    if role_match and "owner" in role_match.group(1).lower():
                        return result

            # Fallback: find any @username in the page that isn't the group itself
            all_usernames = re.findall(r'@([a-zA-Z0-9_]{5,})', html)
            for uname in all_usernames:
                if uname.lower() != username.lower():
                    result["username"]    = uname
                    result["role"]        = "Admin (unverified)"
                    result["profile_url"] = f"https://t.me/{uname}"
                    break

    except Exception as e:
        logger.debug(f"Telegram preview error for {username}: {e}")
    return result


def format_tg_contact(owner: dict) -> str:
    if not owner or not owner.get("username"):
        return "❌ Not found"
    role = owner.get("role", "Admin")
    return f"@{owner['username']} ({role})"
