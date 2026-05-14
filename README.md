# 🤖 Web3 Hunter Bot

Automatically monitors crypto/Web3 platforms for new projects, finds the owner's contact, and sends it straight to your Telegram DM.

---

## 📦 What's Inside

```
web3bot/
├── run.py                    ← START HERE
├── requirements.txt
├── .env.example              ← Copy to .env and fill in
├── bot/
│   └── main_bot.py           ← Telegram bot + scan loop
├── scrapers/
│   ├── dexscreener.py        ← DexScreener API (socials enrichment)
│   └── platforms.py          ← GMGn, Axiom, Pump.fun, Birdeye, fomo.family, Padre
├── finders/
│   ├── telegram_finder.py    ← Finds Telegram Admin/Owner
│   ├── twitter_finder.py     ← Finds Twitter community creator
│   └── owner_finder.py       ← Orchestrates both + formats card
└── utils/
    └── config.py             ← All settings + seen-projects tracker
```

---

## 🚀 Setup (Step by Step)

### 1. Install Python
Make sure you have Python 3.11+ installed.
```bash
python --version
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure your .env
```bash
cp .env.example .env
```
Open `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` — your bot token from @BotFather
- `TELEGRAM_YOUR_USER_ID` — your personal Telegram user ID

**How to get your Telegram User ID:**
- Message @userinfobot on Telegram — it will reply with your ID

### 4. (Optional) Twitter/X cookies for better owner detection
- Open Twitter in Chrome
- Press F12 → Application → Cookies → twitter.com
- Copy `auth_token` and `ct0` values into your `.env`

### 5. Run the bot
```bash
python run.py
```

---

## 💬 Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Activate the bot |
| `/status` | See scan stats |
| `/pause` | Pause scanning |
| `/resume` | Resume scanning |
| `/help` | Show help |

---

## 📨 What You'll Receive

Every new project triggers a DM card like this:

```
🚨 NEW PROJECT DETECTED

📌 ProjectName ($SYM) — SOLANA
🔗 Contract: 0xabc...
💧 Liquidity: $12,400
📡 Source: pump.fun

━━━━━━━━━━━━━━━━
🌐 SOCIALS
• Telegram: https://t.me/projectname
• Twitter/X: https://twitter.com/projectname
• Discord: ❌
• Website: https://projectname.xyz

━━━━━━━━━━━━━━━━
👤 OWNER / FOUNDER
• Telegram: @devhandle (Owner)
• Twitter/X: @devhandle (Community Creator)

━━━━━━━━━━━━━━━━
📊 View on DEX
```

Then tap:
- **🛡 Apply as Mod** — get a ready-made moderator pitch
- **💻 Apply as Dev** — get a ready-made developer pitch
- **✍️ Custom Role** — describe any role and get a custom message
- **⏭ Skip** — ignore this project

---

## 🔧 Settings (in .env)

| Setting | Default | What it does |
|---------|---------|-------------|
| `SCAN_INTERVAL_SECONDS` | 30 | How often to scan platforms |
| `MAX_PROJECTS_PER_SCAN` | 10 | Max projects per cycle (avoid spam) |
| `MIN_LIQUIDITY_USD` | 1000 | Skip dead/empty projects |

---

## 📡 Platforms Monitored

| Platform | Method |
|----------|--------|
| Pump.fun | API |
| Birdeye | API |
| DexScreener | API (socials enrichment) |
| GMGn | Playwright scrape |
| Axiom | Playwright + API intercept |
| fomo.family | Playwright + API intercept |
| trade.padre.cc | Playwright + API intercept |

---

## ⚠️ Important Notes

1. **Owner finding is not 100%** — some projects hide their founders. The bot gets as close as possible; you fill in the gaps manually.
2. **Twitter scraping** works better with your cookies in `.env`. Without it, it still tries but may get rate limited.
3. **Run on a server 24/7** — for best results use a VPS (DigitalOcean, Hetzner, etc). Running on your laptop means you miss projects when it's off.
4. **Playwright needs Chromium** — make sure you ran `playwright install chromium` during setup.

---

## 🖥 Running 24/7 on a VPS (optional)

```bash
# Install screen
sudo apt install screen

# Start a screen session
screen -S web3bot

# Run the bot
python run.py

# Detach (bot keeps running): Ctrl+A then D
# Reattach later: screen -r web3bot
```

---

## 🆘 Troubleshooting

**Bot not responding?**
- Check your `TELEGRAM_BOT_TOKEN` is correct
- Make sure you messaged the bot first on Telegram

**No projects appearing?**
- Check `bot.log` for errors
- Some platforms may be temporarily down
- Try increasing `SCAN_INTERVAL_SECONDS` to reduce load

**Playwright errors?**
- Run `playwright install chromium` again
- On Linux server: `playwright install-deps chromium`
