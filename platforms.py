"""
Multi-Platform Scraper
Monitors: GMGn, Axiom, Fomo.family, Pump.fun, Birdeye, trade.padre.cc, web3.okx
Uses Playwright for JS-heavy pages, aiohttp for API-based ones.
"""

import asyncio
import aiohttp
import json
import re
from playwright.async_api import async_playwright, Browser, BrowserContext
from config import logger
from dexscreener import enrich_socials_from_dexscreener
# ── Regex to extract contract addresses (EVM + Solana) ────
EVM_CA_RE  = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
SOL_CA_RE  = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}


# ═══════════════════════════════════════════════════════════
# PUMP.FUN  (has a public API)
# ═══════════════════════════════════════════════════════════
async def fetch_pumpfun(session: aiohttp.ClientSession) -> list[dict]:
    projects = []
    try:
        url = "https://frontend-api.pump.fun/coins?offset=0&limit=20&sort=created_timestamp&order=DESC&includeNsfw=false"
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            for coin in data:
                contract = coin.get("mint", "").lower()
                if not contract:
                    continue
                socials = {
                    "telegram": coin.get("telegram"),
                    "twitter":  coin.get("twitter"),
                    "discord":  None,
                    "website":  coin.get("website"),
                }
                projects.append({
                    "contract":      contract,
                    "name":          coin.get("name", "Unknown"),
                    "symbol":        coin.get("symbol", "???"),
                    "chain":         "solana",
                    "price_usd":     0,
                    "liquidity_usd": float(coin.get("usd_market_cap") or 0),
                    "dex_url":       f"https://pump.fun/{contract}",
                    "socials":       socials,
                    "source":        "pump.fun"
                })
    except Exception as e:
        logger.error(f"Pump.fun fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# GMGN  (JS-rendered, use Playwright)
# ═══════════════════════════════════════════════════════════
async def fetch_gmgn(context: BrowserContext) -> list[dict]:
    projects = []
    try:
        page = await context.new_page()
        await page.goto("https://gmgn.ai/new-pairs", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Try to grab token rows
        rows = await page.query_selector_all("[class*='token'], [class*='pair'], tr")
        for row in rows[:20]:
            text = await row.inner_text()
            contract = extract_contract(text)
            if contract:
                name = extract_name_from_text(text)
                projects.append({
                    "contract":      contract,
                    "name":          name,
                    "symbol":        "???",
                    "chain":         detect_chain(contract),
                    "price_usd":     0,
                    "liquidity_usd": 0,
                    "dex_url":       f"https://gmgn.ai/sol/token/{contract}",
                    "socials":       {"telegram": None, "twitter": None, "discord": None, "website": None},
                    "source":        "gmgn"
                })
        await page.close()
    except Exception as e:
        logger.error(f"GMGN fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# AXIOM  (JS-rendered)
# ═══════════════════════════════════════════════════════════
async def fetch_axiom(context: BrowserContext) -> list[dict]:
    projects = []
    try:
        page = await context.new_page()

        # Intercept API calls axiom makes internally
        api_data = []
        async def handle_response(response):
            if "tokens" in response.url or "pairs" in response.url or "new" in response.url:
                try:
                    body = await response.json()
                    api_data.append(body)
                except:
                    pass

        page.on("response", handle_response)
        await page.goto("https://axiom.trade", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)

        # Parse intercepted API data
        for blob in api_data:
            items = blob if isinstance(blob, list) else blob.get("data") or blob.get("tokens") or []
            for item in items[:15]:
                contract = (item.get("address") or item.get("mint") or item.get("contract") or "").lower()
                if contract and len(contract) > 20:
                    projects.append({
                        "contract":      contract,
                        "name":          item.get("name") or item.get("symbol") or "Unknown",
                        "symbol":        item.get("symbol", "???"),
                        "chain":         detect_chain(contract),
                        "price_usd":     float(item.get("price") or 0),
                        "liquidity_usd": float(item.get("liquidity") or item.get("marketCap") or 0),
                        "dex_url":       f"https://axiom.trade/meme/{contract}",
                        "socials":       {"telegram": None, "twitter": None, "discord": None, "website": None},
                        "source":        "axiom"
                    })

        await page.close()
    except Exception as e:
        logger.error(f"Axiom fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# FOMO.FAMILY
# ═══════════════════════════════════════════════════════════
async def fetch_fomo_family(context: BrowserContext) -> list[dict]:
    projects = []
    try:
        page = await context.new_page()
        api_data = []

        async def handle_response(response):
            if any(x in response.url for x in ["token", "launch", "new", "api"]):
                try:
                    body = await response.json()
                    api_data.append(body)
                except:
                    pass

        page.on("response", handle_response)
        await page.goto("https://fomo.family", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)

        for blob in api_data:
            items = blob if isinstance(blob, list) else (blob.get("data") or blob.get("tokens") or [])
            for item in items[:15]:
                contract = (item.get("address") or item.get("mint") or item.get("contract") or "").lower()
                if contract and len(contract) > 20:
                    socials = {
                        "telegram": item.get("telegram"),
                        "twitter":  item.get("twitter"),
                        "discord":  item.get("discord"),
                        "website":  item.get("website"),
                    }
                    projects.append({
                        "contract":      contract,
                        "name":          item.get("name", "Unknown"),
                        "symbol":        item.get("symbol", "???"),
                        "chain":         detect_chain(contract),
                        "price_usd":     0,
                        "liquidity_usd": 0,
                        "dex_url":       f"https://fomo.family/token/{contract}",
                        "socials":       socials,
                        "source":        "fomo.family"
                    })

        await page.close()
    except Exception as e:
        logger.error(f"fomo.family fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# BIRDEYE  (has partial public API)
# ═══════════════════════════════════════════════════════════
async def fetch_birdeye(session: aiohttp.ClientSession) -> list[dict]:
    projects = []
    try:
        url = "https://public-api.birdeye.so/defi/tokenlist?sort_by=v24hChangePercent&sort_type=desc&offset=0&limit=20&min_liquidity=100"
        async with session.get(url, headers={**HEADERS, "x-chain": "solana"}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            tokens = (data.get("data") or {}).get("tokens") or []
            for token in tokens:
                contract = (token.get("address") or "").lower()
                if not contract:
                    continue
                projects.append({
                    "contract":      contract,
                    "name":          token.get("name", "Unknown"),
                    "symbol":        token.get("symbol", "???"),
                    "chain":         "solana",
                    "price_usd":     float(token.get("price") or 0),
                    "liquidity_usd": float(token.get("liquidity") or 0),
                    "dex_url":       f"https://birdeye.so/token/{contract}",
                    "socials":       {"telegram": None, "twitter": None, "discord": None, "website": None},
                    "source":        "birdeye"
                })
    except Exception as e:
        logger.error(f"Birdeye fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# PADRE  (trade.padre.cc)
# ═══════════════════════════════════════════════════════════
async def fetch_padre(context: BrowserContext) -> list[dict]:
    projects = []
    try:
        page = await context.new_page()
        api_data = []

        async def handle_response(response):
            try:
                if response.status == 200 and "json" in (response.headers.get("content-type") or ""):
                    body = await response.json()
                    api_data.append(body)
            except:
                pass

        page.on("response", handle_response)
        await page.goto("https://trade.padre.cc", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)

        for blob in api_data:
            items = blob if isinstance(blob, list) else (blob.get("data") or blob.get("tokens") or [])
            for item in items[:15]:
                contract = (item.get("address") or item.get("mint") or "").lower()
                if contract and len(contract) > 20:
                    projects.append({
                        "contract":      contract,
                        "name":          item.get("name", "Unknown"),
                        "symbol":        item.get("symbol", "???"),
                        "chain":         detect_chain(contract),
                        "price_usd":     0,
                        "liquidity_usd": 0,
                        "dex_url":       f"https://trade.padre.cc/token/{contract}",
                        "socials":       {"telegram": None, "twitter": None, "discord": None, "website": None},
                        "source":        "padre"
                    })

        await page.close()
    except Exception as e:
        logger.error(f"Padre fetch error: {e}")
    return projects


# ═══════════════════════════════════════════════════════════
# MASTER FETCH — runs all scrapers
# ═══════════════════════════════════════════════════════════
async def fetch_all_platforms(seen: set) -> list[dict]:
    """
    Runs all platform scrapers, deduplicates by contract,
    enriches missing socials via DexScreener, returns new projects only.
    """
    all_projects = []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )

        async with aiohttp.ClientSession() as session:
            # Run all scrapers concurrently
            results = await asyncio.gather(
                fetch_pumpfun(session),
                fetch_birdeye(session),
                fetch_gmgn(context),
                fetch_axiom(context),
                fetch_fomo_family(context),
                fetch_padre(context),
                return_exceptions=True
            )

            seen_in_batch = set()
            for platform_results in results:
                if isinstance(platform_results, Exception):
                    continue
                for project in platform_results:
                    ca = project["contract"]
                    if ca in seen or ca in seen_in_batch or len(ca) < 20:
                        continue
                    seen_in_batch.add(ca)

                    # Enrich socials if missing
                    soc = project["socials"]
                    if not any(soc.values()):
                        enriched = await enrich_socials_from_dexscreener(session, ca, project["chain"])
                        project["socials"] = enriched

                    all_projects.append(project)

        await browser.close()

    logger.info(f"Found {len(all_projects)} new projects this cycle")
    return all_projects


# ── Helpers ───────────────────────────────────────────────
def extract_contract(text: str) -> str | None:
    evm = EVM_CA_RE.search(text)
    if evm:
        return evm.group().lower()
    sol = SOL_CA_RE.search(text)
    if sol:
        return sol.group()
    return None

def detect_chain(contract: str) -> str:
    if contract.startswith("0x"):
        return "ethereum"
    return "solana"

def extract_name_from_text(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[0][:40] if lines else "Unknown"
