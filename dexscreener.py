"""
DexScreener Scraper
- Fetches latest new token pairs from DexScreener API
- Extracts contract address, name, chain, socials
"""

import aiohttp
import asyncio
from config.config import logger, MIN_LIQUIDITY_USD

DEXSCREENER_NEW_PAIRS = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_SEARCH    = "https://api.dexscreener.com/latest/dex/tokens/{contract}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


async def fetch_new_pairs_dexscreener(session: aiohttp.ClientSession) -> list[dict]:
    """
    Returns a list of new project dicts:
    {
        contract, name, symbol, chain,
        price_usd, liquidity_usd, dex_url,
        socials: { telegram, twitter, discord, website }
    }
    """
    projects = []
    try:
        async with session.get(DEXSCREENER_NEW_PAIRS, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning(f"DexScreener profiles returned {resp.status}")
                return []
            data = await resp.json()

        for item in data[:30]:  # latest 30 token profiles
            contract = item.get("tokenAddress", "").lower()
            chain    = item.get("chainId", "unknown")
            if not contract:
                continue

            socials = extract_socials_from_profile(item)

            # Now get pair data for price/liquidity
            pair_info = await fetch_pair_info(session, contract)

            projects.append({
                "contract":      contract,
                "name":          pair_info.get("name") or item.get("description", "Unknown")[:40],
                "symbol":        pair_info.get("symbol", "???"),
                "chain":         chain,
                "price_usd":     pair_info.get("price_usd", 0),
                "liquidity_usd": pair_info.get("liquidity_usd", 0),
                "dex_url":       f"https://dexscreener.com/{chain}/{contract}",
                "socials":       socials,
                "source":        "dexscreener"
            })

    except Exception as e:
        logger.error(f"DexScreener fetch error: {e}")

    return projects


async def fetch_pair_info(session: aiohttp.ClientSession, contract: str) -> dict:
    """Get price and liquidity for a contract."""
    try:
        url = DEXSCREENER_SEARCH.format(contract=contract)
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return {}
            best = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
            return {
                "name":          best.get("baseToken", {}).get("name", ""),
                "symbol":        best.get("baseToken", {}).get("symbol", ""),
                "price_usd":     float(best.get("priceUsd") or 0),
                "liquidity_usd": float((best.get("liquidity") or {}).get("usd") or 0),
            }
    except Exception as e:
        logger.debug(f"Pair info fetch error for {contract}: {e}")
        return {}


def extract_socials_from_profile(item: dict) -> dict:
    """Extract social links from a DexScreener token profile."""
    socials = {"telegram": None, "twitter": None, "discord": None, "website": None}
    links = item.get("links") or []
    for link in links:
        url   = (link.get("url") or "").lower()
        label = (link.get("label") or link.get("type") or "").lower()
        if "t.me" in url or "telegram" in label:
            socials["telegram"] = link.get("url")
        elif "twitter.com" in url or "x.com" in url or "twitter" in label:
            socials["twitter"] = link.get("url")
        elif "discord" in url or "discord" in label:
            socials["discord"] = link.get("url")
        elif not socials["website"] and ("http" in url):
            if not any(x in url for x in ["t.me", "twitter", "x.com", "discord"]):
                socials["website"] = link.get("url")
    return socials


async def enrich_socials_from_dexscreener(session: aiohttp.ClientSession, contract: str, chain: str) -> dict:
    """
    Called by other scrapers that found a contract but no socials yet.
    Uses DexScreener pair page to find socials.
    """
    socials = {"telegram": None, "twitter": None, "discord": None, "website": None}
    try:
        url = DEXSCREENER_SEARCH.format(contract=contract)
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return socials
            data = await resp.json()
            pairs = data.get("pairs") or []
            for pair in pairs:
                info = pair.get("info") or {}
                for link in (info.get("socials") or []):
                    _type = (link.get("type") or "").lower()
                    val   = link.get("url") or link.get("handle") or ""
                    if _type == "telegram" and not socials["telegram"]:
                        socials["telegram"] = val if val.startswith("http") else f"https://t.me/{val}"
                    elif _type == "twitter" and not socials["twitter"]:
                        socials["twitter"] = val if val.startswith("http") else f"https://twitter.com/{val}"
                for link in (info.get("websites") or []):
                    if not socials["website"]:
                        socials["website"] = link.get("url")
                if any(socials.values()):
                    break
    except Exception as e:
        logger.debug(f"enrich_socials error: {e}")
    return socials
