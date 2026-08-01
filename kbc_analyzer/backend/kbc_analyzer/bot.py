"""Telegram bot entry point — async conversational interface for the KBC analyzer.

Run with:
    kbc-bot              (after pip install -e .)
    python -m kbc_analyzer.bot

The bot only responds to the Telegram user ID configured in TELEGRAM_USER_ID (.env),
so it's safe to leave running on a home server or VPS.

Two conversation flows are supported:
  /analyze → optional auth → optional custom note → analysis result
  /compare → optional auth → how many months? → comparison result

python-telegram-bot uses an async event loop. Any call that does blocking I/O
(Enable Banking API, Gemini API, SQLite) must be wrapped in asyncio.to_thread()
so it doesn't block the event loop.
"""
import asyncio
import logging
import os
import sys
from calendar import monthrange   # used to get the last day of a given month
from datetime import date

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,          # the main bot framework object
    CommandHandler,       # handles /command messages
    ConversationHandler,  # manages multi-step conversations (state machines)
    MessageHandler,       # handles plain text messages
    ContextTypes,         # type hints for context.user_data etc.
    filters,              # filter objects to match specific message types
)

from .analysis import analyze, compare
from .cache import (
    already_fetched_month,
    already_fetched_today,
    get_connection,
    load_transactions,
    mark_month_fetched,
    purge_old_entries,
    save_transactions,
)
from .enablebanking import EnableBankingClient, EnableBankingError
from .telegram_output import format_analysis, format_comparison

# Load environment variables from .env (must happen before any os.getenv() calls)
load_dotenv()

# Suppress verbose python-telegram-bot and httpx logs; only show warnings and above
logging.basicConfig(level=logging.WARNING)

# ── Conversation states ────────────────────────────────────────────────────────
# ConversationHandler uses integer state values to track where a conversation is.
# Each state determines which handlers are active and waiting for user input.
WAITING_AUTH_URL, WAITING_NOTE, WAITING_COMPARE_MONTHS = range(3)
# WAITING_AUTH_URL     = 0  user needs to paste back the KBC redirect URL
# WAITING_NOTE         = 1  user can type extra instructions for Gemini (or /skip)
# WAITING_COMPARE_MONTHS = 2  user needs to enter how many months to compare


def _eb() -> EnableBankingClient:
    """Create a fresh EnableBankingClient from current environment variables."""
    return EnableBankingClient(
        app_id=os.getenv("ENABLEBANKING_APP_ID"),
        private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
    )


def _authorized(update: Update) -> bool:
    """Return True only if the message comes from the configured Telegram user.

    This is the single security gate — every handler calls this first and returns
    immediately if the user is not authorized, so random people can't use the bot.
    """
    allowed = os.getenv("TELEGRAM_USER_ID", "")
    return allowed and str(update.effective_user.id) == allowed


def _month_start() -> date:
    """Return the first day of the current calendar month (e.g. 2026-05-01)."""
    return date.today().replace(day=1)


def _month_label(d: date | None = None) -> str:
    """Return a human-readable month label like 'May 2026' for display in messages."""
    return (d or date.today()).strftime("%B %Y")


def _month_ago(n: int) -> date:
    """Return the first day of the month that is n months before the current month.

    Uses total-months arithmetic to handle year boundaries correctly.
    Example: _month_ago(2) in May 2026 → 2026-03-01
    """
    today = date.today()
    # Convert to a total month count (e.g. May 2026 = 2026*12 + 4 = 24316)
    total = today.year * 12 + today.month - 1 - n
    # Convert back to (year, month)
    return date(total // 12, total % 12 + 1, 1)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — show a welcome message with available commands."""
    if not _authorized(update):
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        "<b>KBC Expenditure Analyzer</b>\n\n"
        "/analyze — analyze current month\n"
        "/compare — compare last N months\n"
        "/cancel  — cancel current operation",
        parse_mode="HTML",
    )


# ── /analyze ──────────────────────────────────────────────────────────────────

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the /analyze conversation.

    If the KBC session is still valid, move directly to WAITING_NOTE.
    If not, start the OAuth flow and move to WAITING_AUTH_URL.
    Returns the next conversation state.
    """
    if not _authorized(update):
        return ConversationHandler.END  # end conversation silently for unauthorized users

    eb = _eb()
    if not eb.session_valid():
        # Session expired or doesn't exist — need to re-authorize KBC access
        await update.message.reply_text("⏳ Starting KBC authorization...")
        try:
            # start_auth() is blocking (makes HTTP request) — run in a thread pool
            url = await asyncio.to_thread(eb.start_auth)
        except EnableBankingError as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return ConversationHandler.END

        await update.message.reply_text(
            "🔐 <b>KBC Authorization Required</b>\n\n"
            f"1. Open this URL in your browser:\n<code>{url}</code>\n\n"
            "2. Log in with your KBC credentials\n"
            "3. You'll be redirected to <code>https://localhost/callback?code=…</code>\n"
            "   (the page won't load — that's expected)\n\n"
            "4. Copy the full URL from the address bar and paste it here",
            parse_mode="HTML",
        )
        # Remember that after auth we should continue the analyze flow, not the compare flow
        context.user_data["after_auth"] = "analyze"
        return WAITING_AUTH_URL  # wait for the user to paste the redirect URL

    # Session is valid — skip auth, go straight to asking for optional instructions
    context.user_data["account_uids"] = eb.get_cached_uids()
    await update.message.reply_text(
        f"✅ Session active — analyzing <b>{_month_label()}</b>\n\n"
        "💬 Add custom instructions, or /skip:",
        parse_mode="HTML",
    )
    return WAITING_NOTE


async def receive_auth_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the redirect URL pasted by the user after completing KBC authorization.

    This handler is active in the WAITING_AUTH_URL state for both /analyze and /compare.
    After auth completes, we branch based on context.user_data["after_auth"].
    """
    if not _authorized(update):
        return ConversationHandler.END

    eb = _eb()
    try:
        # complete_auth() is blocking — run in thread pool
        uids = await asyncio.to_thread(eb.complete_auth, update.message.text)
    except EnableBankingError as e:
        await update.message.reply_text(f"❌ Authorization failed: {e}\n\nSend /analyze to try again.")
        return ConversationHandler.END

    context.user_data["account_uids"] = uids
    after = context.user_data.get("after_auth", "analyze")  # which flow triggered auth

    if after == "compare":
        # Auth was triggered by /compare — continue to ask how many months
        await update.message.reply_text(
            f"✅ {len(uids)} account(s) linked!\n\nHow many months to compare? (2–6)"
        )
        return WAITING_COMPARE_MONTHS

    # Auth was triggered by /analyze — continue to ask for optional instructions
    await update.message.reply_text(
        f"✅ {len(uids)} account(s) linked!\n\n"
        f"Analyzing <b>{_month_label()}</b>\n\n"
        "💬 Add custom instructions, or /skip:",
        parse_mode="HTML",
    )
    return WAITING_NOTE


async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the optional custom instruction text the user typed before Gemini analysis."""
    if not _authorized(update):
        return ConversationHandler.END
    # Pass the note text to the analysis runner; strip leading/trailing whitespace
    await _run_analysis(update, context, update.message.text.strip())
    return ConversationHandler.END


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /skip — run analysis without any custom instructions."""
    await _run_analysis(update, context, None)
    return ConversationHandler.END


async def _run_analysis(
    update: Update, context: ContextTypes.DEFAULT_TYPE, note: str | None
) -> None:
    """Fetch transactions and send them to Gemini, then send results to the user.

    This is the core logic shared by receive_note() and cmd_skip(). Separated into
    its own function because both paths need the same work done.
    """
    await update.message.reply_text("⏳ Fetching transactions...")

    eb = _eb()
    # Use account UIDs stored during this conversation; fall back to cached file if somehow missing
    account_uids = context.user_data.get("account_uids") or eb.get_cached_uids()
    date_from = _month_start()

    conn = get_connection()
    purge_old_entries(conn)
    all_transactions: list[dict] = []

    for uid in account_uids:
        if already_fetched_today(conn, uid):
            # Already called the API today for this account — use the SQLite cache
            txs = load_transactions(conn, uid, date_from)
        else:
            try:
                # fetch_transactions() makes HTTP requests — must run in thread pool
                txs = await asyncio.to_thread(eb.fetch_transactions, uid, date_from)
            except EnableBankingError as e:
                await update.message.reply_text(f"⚠️ Failed to fetch account {uid[:8]}…: {e}")
                continue  # skip this account but continue with others
            save_transactions(conn, uid, txs)
        all_transactions.extend(txs)

    conn.close()

    if not all_transactions:
        await update.message.reply_text("No transactions found for this month.")
        return

    await update.message.reply_text(f"🧠 Analyzing {len(all_transactions)} transactions...")

    try:
        # analyze() calls the Gemini API — blocking, must run in thread pool
        analysis = await asyncio.to_thread(analyze, all_transactions, date_from, note)
    except RuntimeError as e:
        await update.message.reply_text(f"❌ Analysis error: {e}")
        return

    # format_analysis() returns a list of strings each ≤ 3800 chars (Telegram limit is 4096)
    for chunk in format_analysis(analysis, _month_label()):
        await update.message.reply_text(chunk, parse_mode="HTML")


# ── /compare ──────────────────────────────────────────────────────────────────

async def cmd_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the /compare conversation.

    Same auth-check pattern as /analyze — if the session is valid, ask how many
    months to compare; if not, start the OAuth flow first.
    """
    if not _authorized(update):
        return ConversationHandler.END

    eb = _eb()
    if not eb.session_valid():
        await update.message.reply_text("⏳ Starting KBC authorization...")
        try:
            url = await asyncio.to_thread(eb.start_auth)
        except EnableBankingError as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return ConversationHandler.END

        await update.message.reply_text(
            "🔐 <b>KBC Authorization Required</b>\n\n"
            f"Open this URL:\n<code>{url}</code>\n\n"
            "Paste the redirect URL here after authorizing.",
            parse_mode="HTML",
        )
        # After auth we should continue the compare flow (not analyze)
        context.user_data["after_auth"] = "compare"
        return WAITING_AUTH_URL

    # Session is valid — skip auth, go directly to asking for the month count
    context.user_data["account_uids"] = eb.get_cached_uids()
    await update.message.reply_text("How many months to compare? (2–6)")
    return WAITING_COMPARE_MONTHS


async def receive_compare_months(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the number the user typed for how many months to compare (2–6)."""
    if not _authorized(update):
        return ConversationHandler.END

    try:
        n = int(update.message.text.strip())
        if not 2 <= n <= 6:
            raise ValueError  # trigger the except branch to send an error message
    except ValueError:
        # Stay in the same state and ask again if the input wasn't a valid number in range
        await update.message.reply_text("Please send a number between 2 and 6.")
        return WAITING_COMPARE_MONTHS

    await _run_comparison(update, context, n)
    return ConversationHandler.END


async def _run_comparison(
    update: Update, context: ContextTypes.DEFAULT_TYPE, n_months: int
) -> None:
    """Fetch transactions for the last n_months months and run the comparison analysis."""
    await update.message.reply_text(f"⏳ Fetching {n_months} months of transactions...")

    eb = _eb()
    account_uids = context.user_data.get("account_uids") or eb.get_cached_uids()
    today = date.today()

    # Build a list of (first_day, last_day) tuples for each month we need,
    # from oldest to newest (range counts down from n_months-1 to 0)
    months: list[tuple[date, date]] = []
    for i in range(n_months - 1, -1, -1):
        first = _month_ago(i)
        # monthrange returns (weekday_of_first, number_of_days); [1] is the day count
        last = date(first.year, first.month, monthrange(first.year, first.month)[1])
        # For the current month, cap the end date at today (month isn't over yet)
        if last > today:
            last = today
        months.append((first, last))

    conn = get_connection()
    purge_old_entries(conn)
    months_data: dict[str, list[dict]] = {}  # keyed by "Month YYYY" e.g. "April 2026"

    for date_from, date_to in months:
        month_key = date_from.strftime("%Y-%m")   # e.g. "2026-04" — used as cache key
        is_current = date_to >= today             # True if this is the current in-progress month
        all_txs: list[dict] = []

        for uid in account_uids:
            if is_current and already_fetched_today(conn, uid):
                # Current month, fetched today → use cache
                txs = load_transactions(conn, uid, date_from, date_to)
            elif not is_current and already_fetched_month(conn, uid, month_key):
                # Past month, already fully cached → use cache (never re-fetch past months)
                txs = load_transactions(conn, uid, date_from, date_to)
            else:
                # Need to fetch from the API
                try:
                    txs = await asyncio.to_thread(eb.fetch_transactions, uid, date_from)
                except EnableBankingError as e:
                    await update.message.reply_text(f"⚠️ Failed to fetch {month_key}: {e}")
                    txs = []

                # The API always returns from date_from to today, but we only want this month's range
                txs = [t for t in txs if date_from.isoformat() <= t["date"] <= date_to.isoformat()]

                if txs:
                    save_transactions(conn, uid, txs)

                if not is_current:
                    # Mark past month as permanently cached — no need to fetch again
                    mark_month_fetched(conn, uid, month_key)

            all_txs.extend(txs)

        # Use "April 2026" style key for display; compare() receives this dict
        months_data[date_from.strftime("%B %Y")] = all_txs

    conn.close()

    total_txs = sum(len(v) for v in months_data.values())
    await update.message.reply_text(
        f"🧠 Comparing {total_txs} transactions across {n_months} months..."
    )

    try:
        # compare() calls the Gemini API — blocking, run in thread pool
        result = await asyncio.to_thread(compare, months_data)
    except RuntimeError as e:
        await update.message.reply_text(f"❌ Comparison error: {e}")
        return

    for chunk in format_comparison(result):
        await update.message.reply_text(chunk, parse_mode="HTML")


# ── Shared handlers ────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel — exit whichever conversation is in progress."""
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END  # signals ConversationHandler to reset its state


def main() -> None:
    """Build the bot, register all handlers, and start polling for updates."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    # Application is the top-level object that manages the bot lifecycle
    app = Application.builder().token(token).build()

    # ── /analyze conversation ──────────────────────────────────────────────────
    # A ConversationHandler is a state machine. entry_points start a conversation;
    # states define what handlers are active in each state; fallbacks handle /cancel.
    analyze_conv = ConversationHandler(
        entry_points=[CommandHandler("analyze", cmd_analyze)],
        states={
            WAITING_AUTH_URL: [
                # In this state we expect the user to paste a URL (plain text, not a command)
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_url)
            ],
            WAITING_NOTE: [
                CommandHandler("skip", cmd_skip),                            # skip without a note
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_note),  # note provided
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    # ── /compare conversation ──────────────────────────────────────────────────
    compare_conv = ConversationHandler(
        entry_points=[CommandHandler("compare", cmd_compare)],
        states={
            WAITING_AUTH_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_url)
            ],
            WAITING_COMPARE_MONTHS: [
                # Expect the user to type a number (2–6)
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_compare_months)
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    # Register handlers — order matters: /start is checked before the conversations
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(analyze_conv)
    app.add_handler(compare_conv)

    # Start polling: the bot repeatedly asks Telegram for new messages and dispatches them
    app.run_polling()


if __name__ == "__main__":
    main()
