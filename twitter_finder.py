"""
Twitter/X Owner Finder
- Visits a Twitter/X project page
- Finds the account that CREATED their community
- Returns the owner's Twitter handle
"""

import re
import aiohttp
from utils.config import logger, TWITTER_AUTH_TOKEN, TWITTER_CT0

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_twitter_headers() -> dict:
    headers = {**HEADERS_BASE}
    if TWITTER_AUTH_TOKEN and TWITTER_CT0:
        headers["Cookie"] = f"auth_token={TWITTER_AUTH_TOKEN}; ct0={TWITTER_CT0}"
        headers["X-Csrf-Token"] = TWITTER_CT0
    return headers


async def find_twitter_owner(session: aiohttp.ClientSession, twitter_url: str) -> dict:
    """
    Given a Twitter/X project URL, tries to find the account owner/creator.
    Returns: { handle, display_name, role, profile_url }
    """
    result = {"handle": None, "display_name": None, "role": None, "profile_url": None}

    if not twitter_url:
        return result

    # Normalize URL and extract handle
    handle = extract_twitter_handle(twitter_url)
    if not handle:
        return result

    # Try community creator lookup
    community_result = await check_community_creator(session, handle)
    if community_result["handle"]:
        return community_result

    # Try profile bio for owner hints
    bio_result = await check_profile_bio(session, handle)
    return bio_result


def extract_twitter_handle(url: str) -> str | None:
    """Extract @handle from a Twitter/X URL."""
    patterns = [
        r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,50})(?:/|$|\?)',
        r'@([a-zA-Z0-9_]{1,50})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            handle = match.group(1)
            if handle.lower() not in ("home", "search", "explore", "i", "settings"):
                return handle
    return None


async def check_community_creator(session: aiohttp.ClientSession, handle: str) -> dict:
    """
    Check if the account has a Community and who created it.
    Twitter communities show "Created by @handle" on their page.
    """
    result = {"handle": None, "display_name": None, "role": None, "profile_url": None}
    try:
        # Visit the profile page
        url = f"https://twitter.com/{handle}"
        async with session.get(url, headers=get_twitter_headers(), timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status not in (200, 301, 302):
                return result
            html = await resp.text()

            # Look for "Created by" pattern which appears in community sections
            patterns = [
                r'[Cc]reated\s+by\s+@([a-zA-Z0-9_]{1,50})',
                r'[Ff]ounded\s+by\s+@([a-zA-Z0-9_]{1,50})',
                r'[Oo]wner[:\s]+@([a-zA-Z0-9_]{1,50})',
                r'[Dd]ev[:\s]+@([a-zA-Z0-9_]{1,50})',
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    found = match.group(1)
                    if found.lower() != handle.lower():
                        result["handle"]      = found
                        result["role"]        = "Community Creator / Owner"
                        result["profile_url"] = f"https://twitter.com/{found}"
                        return result

            # If the account itself is the main account (single dev project)
            # look for personal bio signals
            if re.search(r'(?:founder|dev|builder|creator|owner)', html, re.IGNORECASE):
                result["handle"]      = handle
                result["role"]        = "Project Account (likely founder)"
                result["profile_url"] = f"https://twitter.com/{handle}"

    except Exception as e:
        logger.debug(f"Twitter community check error for {handle}: {e}")
    return result


async def check_profile_bio(session: aiohttp.ClientSession, handle: str) -> dict:
    """Fallback: return the project's own Twitter handle with a note."""
    result = {"handle": None, "display_name": None, "role": None, "profile_url": None}
    try:
        result["handle"]      = handle
        result["role"]        = "Project Twitter (DM for owner)"
        result["profile_url"] = f"https://twitter.com/{handle}"
    except Exception as e:
        logger.debug(f"Twitter profile bio error: {e}")
    return result


def format_twitter_contact(owner: dict) -> str:
    if not owner or not owner.get("handle"):
        return "❌ Not found"
    role = owner.get("role", "Twitter")
    return f"@{owner['handle']} ({role})"
