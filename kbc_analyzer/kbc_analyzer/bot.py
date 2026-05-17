import asyncio
import logging
import os
import sys
from calendar import monthrange
from datetime import date

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
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

load_dotenv()
logging.basicConfig(level=logging.WARNING)

WAITING_AUTH_URL, WAITING_NOTE, WAITING_COMPARE_MONTHS = range(3)


def _eb() -> EnableBankingClient:
    return EnableBankingClient(
        app_id=os.getenv("ENABLEBANKING_APP_ID"),
        private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
    )


def _authorized(update: Update) -> bool:
    allowed = os.getenv("TELEGRAM_USER_ID", "")
    return allowed and str(update.effective_user.id) == allowed


def _month_start() -> date:
    return date.today().replace(day=1)


def _month_label(d: date | None = None) -> str:
    return (d or date.today()).strftime("%B %Y")


def _month_ago(n: int) -> date:
    """First day of the month that is n months before the current month."""
    today = date.today()
    total = today.year * 12 + today.month - 1 - n
    return date(total // 12, total % 12 + 1, 1)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            f"1. Open this URL in your browser:\n<code>{url}</code>\n\n"
            "2. Log in with your KBC credentials\n"
            "3. You'll be redirected to <code>https://localhost/callback?code=…</code>\n"
            "   (the page won't load — that's expected)\n\n"
            "4. Copy the full URL from the address bar and paste it here",
            parse_mode="HTML",
        )
        context.user_data["after_auth"] = "analyze"
        return WAITING_AUTH_URL

    context.user_data["account_uids"] = eb.get_cached_uids()
    await update.message.reply_text(
        f"✅ Session active — analyzing <b>{_month_label()}</b>\n\n"
        "💬 Add custom instructions, or /skip:",
        parse_mode="HTML",
    )
    return WAITING_NOTE


async def receive_auth_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        return ConversationHandler.END

    eb = _eb()
    try:
        uids = await asyncio.to_thread(eb.complete_auth, update.message.text)
    except EnableBankingError as e:
        await update.message.reply_text(f"❌ Authorization failed: {e}\n\nSend /analyze to try again.")
        return ConversationHandler.END

    context.user_data["account_uids"] = uids
    after = context.user_data.get("after_auth", "analyze")

    if after == "compare":
        await update.message.reply_text(
            f"✅ {len(uids)} account(s) linked!\n\nHow many months to compare? (2–6)"
        )
        return WAITING_COMPARE_MONTHS

    await update.message.reply_text(
        f"✅ {len(uids)} account(s) linked!\n\n"
        f"Analyzing <b>{_month_label()}</b>\n\n"
        "💬 Add custom instructions, or /skip:",
        parse_mode="HTML",
    )
    return WAITING_NOTE


async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        return ConversationHandler.END
    await _run_analysis(update, context, update.message.text.strip())
    return ConversationHandler.END


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _run_analysis(update, context, None)
    return ConversationHandler.END


async def _run_analysis(
    update: Update, context: ContextTypes.DEFAULT_TYPE, note: str | None
) -> None:
    await update.message.reply_text("⏳ Fetching transactions...")

    eb = _eb()
    account_uids = context.user_data.get("account_uids") or eb.get_cached_uids()
    date_from = _month_start()

    conn = get_connection()
    purge_old_entries(conn)
    all_transactions: list[dict] = []

    for uid in account_uids:
        if already_fetched_today(conn, uid):
            txs = load_transactions(conn, uid, date_from)
        else:
            try:
                txs = await asyncio.to_thread(eb.fetch_transactions, uid, date_from)
            except EnableBankingError as e:
                await update.message.reply_text(f"⚠️ Failed to fetch account {uid[:8]}…: {e}")
                continue
            save_transactions(conn, uid, txs)
        all_transactions.extend(txs)

    conn.close()

    if not all_transactions:
        await update.message.reply_text("No transactions found for this month.")
        return

    await update.message.reply_text(f"🧠 Analyzing {len(all_transactions)} transactions...")

    try:
        analysis = await asyncio.to_thread(analyze, all_transactions, date_from, note)
    except RuntimeError as e:
        await update.message.reply_text(f"❌ Analysis error: {e}")
        return

    for chunk in format_analysis(analysis, _month_label()):
        await update.message.reply_text(chunk, parse_mode="HTML")


# ── /compare ──────────────────────────────────────────────────────────────────

async def cmd_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data["after_auth"] = "compare"
        return WAITING_AUTH_URL

    context.user_data["account_uids"] = eb.get_cached_uids()
    await update.message.reply_text("How many months to compare? (2–6)")
    return WAITING_COMPARE_MONTHS


async def receive_compare_months(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        return ConversationHandler.END

    try:
        n = int(update.message.text.strip())
        if not 2 <= n <= 6:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a number between 2 and 6.")
        return WAITING_COMPARE_MONTHS

    await _run_comparison(update, context, n)
    return ConversationHandler.END


async def _run_comparison(
    update: Update, context: ContextTypes.DEFAULT_TYPE, n_months: int
) -> None:
    await update.message.reply_text(f"⏳ Fetching {n_months} months of transactions...")

    eb = _eb()
    account_uids = context.user_data.get("account_uids") or eb.get_cached_uids()
    today = date.today()

    months: list[tuple[date, date]] = []
    for i in range(n_months - 1, -1, -1):
        first = _month_ago(i)
        last = date(first.year, first.month, monthrange(first.year, first.month)[1])
        if last > today:
            last = today
        months.append((first, last))

    conn = get_connection()
    purge_old_entries(conn)
    months_data: dict[str, list[dict]] = {}

    for date_from, date_to in months:
        month_key = date_from.strftime("%Y-%m")
        is_current = date_to >= today
        all_txs: list[dict] = []

        for uid in account_uids:
            if is_current and already_fetched_today(conn, uid):
                txs = load_transactions(conn, uid, date_from, date_to)
            elif not is_current and already_fetched_month(conn, uid, month_key):
                txs = load_transactions(conn, uid, date_from, date_to)
            else:
                try:
                    txs = await asyncio.to_thread(eb.fetch_transactions, uid, date_from)
                except EnableBankingError as e:
                    await update.message.reply_text(f"⚠️ Failed to fetch {month_key}: {e}")
                    txs = []
                txs = [t for t in txs if date_from.isoformat() <= t["date"] <= date_to.isoformat()]
                if txs:
                    save_transactions(conn, uid, txs)
                if not is_current:
                    mark_month_fetched(conn, uid, month_key)

            all_txs.extend(txs)

        months_data[date_from.strftime("%B %Y")] = all_txs

    conn.close()

    total_txs = sum(len(v) for v in months_data.values())
    await update.message.reply_text(f"🧠 Comparing {total_txs} transactions across {n_months} months...")

    try:
        result = await asyncio.to_thread(compare, months_data)
    except RuntimeError as e:
        await update.message.reply_text(f"❌ Comparison error: {e}")
        return

    for chunk in format_comparison(result):
        await update.message.reply_text(chunk, parse_mode="HTML")


# ── shared ────────────────────────────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    app = Application.builder().token(token).build()

    analyze_conv = ConversationHandler(
        entry_points=[CommandHandler("analyze", cmd_analyze)],
        states={
            WAITING_AUTH_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_url)
            ],
            WAITING_NOTE: [
                CommandHandler("skip", cmd_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_note),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    compare_conv = ConversationHandler(
        entry_points=[CommandHandler("compare", cmd_compare)],
        states={
            WAITING_AUTH_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_auth_url)
            ],
            WAITING_COMPARE_MONTHS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_compare_months)
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(analyze_conv)
    app.add_handler(compare_conv)
    app.run_polling()


if __name__ == "__main__":
    main()
