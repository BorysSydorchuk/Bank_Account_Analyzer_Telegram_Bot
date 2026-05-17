# KBC Expenditure Analyzer

A personal finance tool that fetches real bank transaction data from KBC Belgium via Open Banking (PSD2), categorizes and analyzes spending using Google Gemini, and delivers results through a Telegram bot.

## Features

- **Real bank data** — connects to KBC Belgium via [Enable Banking](https://enablebanking.com) (PSD2/Open Banking API), no screen scraping
- **AI-powered analysis** — Google Gemini categorizes transactions, detects anomalies, and generates insights
- **Monthly analysis** — daily and weekly breakdowns with flagged large transactions
- **Month-over-month comparison** — compare up to 6 months of spending across categories
- **Telegram bot interface** — conversational UX, results delivered as formatted messages
- **Smart caching** — SQLite cache avoids redundant API calls; past months are fetched once and stored permanently
- **Terminal fallback** — `main.py` for local use without Telegram

## Tech Stack

| Layer | Technology |
|---|---|
| Bank data | Enable Banking API (PSD2), RSA JWT auth |
| AI analysis | Google Gemini 2.0 Flash (structured JSON output) |
| Bot interface | python-telegram-bot 20+ (async, ConversationHandler) |
| Data validation | Pydantic v2 |
| Caching | SQLite via stdlib `sqlite3` |
| Terminal UI | Rich |

## Architecture

```
bot.py              ← Telegram bot entry point (async conversation handlers)
├── enablebanking.py   OAuth2 session management + transaction fetching
├── cache.py           SQLite: transactions + fetch_log + month_fetch_log
├── analysis.py        Gemini integration: per-month analysis + comparison
└── telegram_output.py HTML formatter for Telegram messages

main.py             ← Terminal entry point (same logic, Rich tables output)
└── display.py         Rich table renderer
```

## Setup

### 1. Enable Banking (bank data)

1. Sign up at [enablebanking.com](https://enablebanking.com) → create a **Restricted production application** (free for personal use)
2. Copy your **Application ID** from the portal
3. Download the **RSA private key** (`.pem` file) and place it in the project directory

### 2. Google Gemini (AI analysis)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) → **Create API key** (free tier available)

### 3. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Message [@userinfobot](https://t.me/userinfobot) to get your numeric user ID

### 4. Configuration

```bash
cp .env.example .env
# Fill in all values in .env
```

```env
ENABLEBANKING_APP_ID=your_application_id
ENABLEBANKING_PRIVATE_KEY_PATH=private.pem
GEMINI_API_KEY=AIza...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_USER_ID=123456789
```

### 5. Install and run

```bash
# Install in editable mode (registers kbc-bot and kbc-analyze entry points)
pip install -e .

# Run the Telegram bot
kbc-bot

# Or run the terminal analyzer
kbc-analyze
```

Alternatively, without installing:
```bash
python -m kbc_analyzer.bot      # Telegram bot
python -m kbc_analyzer.main     # terminal
```

## Bot Commands

| Command | Description |
|---|---|
| `/analyze` | Analyze current month's transactions |
| `/compare` | Compare last N months (2–6) side by side |
| `/skip` | Skip optional analysis instructions prompt |
| `/cancel` | Cancel the current operation |

### First-run authorization flow

On first use, `/analyze` will prompt you to authorize KBC access:
1. Open the provided URL in your browser
2. Log in with your KBC credentials
3. You'll be redirected to `https://localhost/callback?code=...` (page won't load — expected)
4. Copy the full URL from the address bar and paste it into the bot

The session is cached for ~90 days; re-authorization is only needed when it expires.

## Project Structure

```
kbc_analyzer/               ← project root (git repo)
├── kbc_analyzer/           ← Python package
│   ├── bot.py              ← Telegram bot entry point
│   ├── main.py             ← terminal entry point
│   ├── enablebanking.py    ← Enable Banking API client (PSD2/OAuth)
│   ├── analysis.py         ← Gemini integration: analysis + comparison
│   ├── cache.py            ← SQLite transaction cache
│   ├── display.py          ← Rich terminal output
│   └── telegram_output.py ← Telegram HTML formatter
├── scripts/                ← dev/debug utilities
│   ├── debug_fetch.py
│   └── inspect_transactions.py
├── tests/
├── pyproject.toml          ← packaging + entry points
├── requirements.txt
├── .env.example
└── .gitignore
```

## Notes

- Only KBC current/savings accounts are accessible via PSD2. Credit cards are not supported by the Open Banking standard.
- The bot only responds to the configured `TELEGRAM_USER_ID` — safe to leave running on a home server or VPS.
- Transaction data is stored locally in `kbc_transactions.db` and never leaves your machine except when sent to the Gemini API for analysis.
