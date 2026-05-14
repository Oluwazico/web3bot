"""
Web3 Hunter Bot - Main Bot
Combines platform scraping + Telegram channel monitoring
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

from utils.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_YOUR_USER_ID,
    SCAN_INTERVAL, MAX_PROJECTS_PER_SCAN,
    load_seen, save_seen, mark_seen,
    load_channels, save_channels, logger
)
from scrapers.platforms import fetch_all_platforms
from scrapers.channel_monitor import ChannelMonitor
from finders.owner_finder import find_owner, format_project_card

# Bot state
bot_state = {
    "running":     True,
    "scan_count":  0,
    "found_count": 0,
    "paused":      False,
}

seen_contracts: set = load_seen()
project_queue: asyncio.Queue = asyncio.Queue()


# ── COMMANDS ──────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return
    channels = load_channels()
    ch_list  = "\n".join(f"  - {c}" for c in channels) if channels else "  None yet"
    await update.message.reply_text(
        "*Web3 Hunter Bot is LIVE!*\n\n"
        "I monitor crypto platforms AND your Telegram channels for new projects.\n"
        "When a new project drops I find the owner and DM you everything.\n\n"
        f"*Monitored channels ({len(channels)}):*\n{ch_list}\n\n"
        "Commands:\n"
        "/addchannel @username - Add a channel to monitor\n"
        "/removechannel @username - Remove a channel\n"
        "/channels - List monitored channels\n"
        "/status - Bot stats\n"
        "/pause - Pause scanning\n"
        "/resume - Resume scanning\n"
        "/help - Help",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_channels(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    channels = load_channels()
    if not channels:
        await update.message.reply_text("No channels being monitored yet.\nUse /addchannel @username to add one.")
        return
    ch_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(channels))
    await update.message.reply_text(f"*Monitored Channels ({len(channels)}):*\n{ch_list}", parse_mode=ParseMode.MARKDOWN)


async def cmd_addchannel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /addchannel @channelname")
        return
    channel = args[0].strip()
    if not channel.startswith("@"):
        channel = "@" + channel
    channels = load_channels()
    if channel in channels:
        await update.message.reply_text(f"{channel} is already being monitored.")
        return
    channels.append(channel)
    save_channels(channels)
    await update.message.reply_text(
        f"Added {channel}!\n"
        f"Restart the bot for it to start monitoring this channel.\n"
        f"Total channels: {len(channels)}"
    )


async def cmd_removechannel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /removechannel @channelname")
        return
    channel = args[0].strip()
    if not channel.startswith("@"):
        channel = "@" + channel
    channels = load_channels()
    if channel not in channels:
        await update.message.reply_text(f"{channel} is not in the list.")
        return
    channels.remove(channel)
    save_channels(channels)
    await update.message.reply_text(f"Removed {channel}. Total channels: {len(channels)}")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    status   = "Running" if not bot_state["paused"] else "Paused"
    channels = load_channels()
    await update.message.reply_text(
        f"*Bot Status*\n\n"
        f"Status: {status}\n"
        f"Scans completed: {bot_state['scan_count']}\n"
        f"Projects found: {bot_state['found_count']}\n"
        f"Seen contracts: {len(seen_contracts)}\n"
        f"Monitored channels: {len(channels)}\n"
        f"Scan interval: every {SCAN_INTERVAL}s",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    bot_state["paused"] = True
    await update.message.reply_text("Bot paused. Send /resume to restart.")


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    bot_state["paused"] = False
    await update.message.reply_text("Bot resumed! Scanning again.")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_YOUR_USER_ID:
        return
    await update.message.reply_text(
        "*Web3 Hunter Bot Help*\n\n"
        "*Channel Commands:*\n"
        "/addchannel @name - Add channel to monitor\n"
        "/removechannel @name - Remove channel\n"
        "/channels - List all channels\n\n"
        "*Bot Commands:*\n"
        "/start - Start/info\n"
        "/status - Stats\n"
        "/pause - Pause scanning\n"
        "/resume - Resume\n"
        "/help - This message\n\n"
        "*How it works:*\n"
        "1. Monitors your channels for new project posts\n"
        "2. Also scrapes GMGn, Axiom, Pump.fun, Birdeye etc\n"
        "3. Extracts contract address from messages\n"
        "4. Gets socials from DexScreener\n"
        "5. Finds Telegram admin / Twitter community creator\n"
        "6. Sends you a card with owner contact\n"
        "7. Duplicate contracts are skipped automatically",
        parse_mode=ParseMode.MARKDOWN
    )


# ── BUTTON CALLBACKS ──────────────────────────────────────

async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data.startswith("apply_mod:"):
        contract = data.split(":", 1)[1]
        await query.message.reply_text(
            "*Apply as Moderator - Ready Message:*\n\n"
            "_Hi! I came across your project and I'm very interested in joining as a moderator. "
            "I'm experienced in Web3 community management, TG/Discord moderation, "
            "announcements, and keeping communities engaged. "
            "Are you currently looking for mods?_\n\n"
            f"Contract: `{contract}`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("apply_dev:"):
        contract = data.split(":", 1)[1]
        await query.message.reply_text(
            "*Apply as Developer - Ready Message:*\n\n"
            "_Hi! I saw your project just launched and I'm interested in contributing as a developer. "
            "I have experience in Solidity/Rust smart contracts, Web3 frontend (React + ethers.js), "
            "and DApp development. Happy to share my portfolio. Are you looking for devs?_\n\n"
            f"Contract: `{contract}`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("apply_custom:"):
        contract = data.split(":", 1)[1]
        await query.message.reply_text(
            f"What role do you want to apply for? Reply with a description and I'll draft the message.\n"
            f"Contract: `{contract}`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("skip:"):
        await query.message.reply_text("Skipped.")


# ── PROJECT PROCESSOR ─────────────────────────────────────

async def process_and_send(app: Application, project: dict):
    """Find owner and send DM card for a project."""
    contract = project["contract"]

    # Find owner
    try:
        project = await find_owner(project)
    except Exception as e:
        logger.warning(f"Owner find failed for {contract}: {e}")
        project["owner"] = {"telegram": None, "twitter": None, "found": False}

    card = format_project_card(project)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Shield Apply as Mod",    callback_data=f"apply_mod:{contract[:20]}"),
            InlineKeyboardButton("PC Apply as Dev",        callback_data=f"apply_dev:{contract[:20]}"),
        ],
        [
            InlineKeyboardButton("Pencil Custom Role",     callback_data=f"apply_custom:{contract[:20]}"),
            InlineKeyboardButton("Skip",                   callback_data=f"skip:{contract[:20]}"),
        ]
    ])

    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_YOUR_USER_ID,
            text=card,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        mark_seen(contract, seen_contracts)
        bot_state["found_count"] += 1
    except Exception as e:
        logger.error(f"Failed to send card: {e}")


# ── QUEUE PROCESSOR ───────────────────────────────────────

async def queue_processor(app: Application):
    """Processes projects that come in from channel monitor."""
    logger.info("Queue processor started")
    while True:
        try:
            project = await asyncio.wait_for(project_queue.get(), timeout=1.0)
            if not bot_state["paused"]:
                await process_and_send(app, project)
            project_queue.task_done()
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Queue processor error: {e}")


# ── PLATFORM SCAN LOOP ────────────────────────────────────

async def scan_loop(app: Application):
    """Scrapes platforms every SCAN_INTERVAL seconds."""
    await asyncio.sleep(5)
    logger.info("Platform scan loop started")

    while bot_state["running"]:
        if bot_state["paused"]:
            await asyncio.sleep(10)
            continue

        try:
            logger.info(f"Starting platform scan #{bot_state['scan_count'] + 1}")
            projects = await fetch_all_platforms(seen_contracts)
            bot_state["scan_count"] += 1

            processed = 0
            for project in projects:
                if processed >= MAX_PROJECTS_PER_SCAN:
                    break
                await process_and_send(app, project)
                processed += 1
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Scan loop error: {e}")

        await asyncio.sleep(SCAN_INTERVAL)


# ── MAIN ──────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    if not TELEGRAM_YOUR_USER_ID:
        raise ValueError("TELEGRAM_YOUR_USER_ID not set in .env")

    logger.info("Starting Web3 Hunter Bot...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("status",        cmd_status))
    app.add_handler(CommandHandler("pause",         cmd_pause))
    app.add_handler(CommandHandler("resume",        cmd_resume))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("channels",      cmd_channels))
    app.add_handler(CommandHandler("addchannel",    cmd_addchannel))
    app.add_handler(CommandHandler("removechannel", cmd_removechannel))
    app.add_handler(CallbackQueryHandler(button_callback))

    async def post_init(application: Application):
        # Start platform scraper
        asyncio.create_task(scan_loop(application))
        # Start queue processor (handles channel monitor projects)
        asyncio.create_task(queue_processor(application))
        # Start channel monitor
        monitor = ChannelMonitor(project_queue, seen_contracts)
        asyncio.create_task(monitor.start())
        logger.info("All systems started")

    app.post_init = post_init

    logger.info("Bot polling for commands...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
