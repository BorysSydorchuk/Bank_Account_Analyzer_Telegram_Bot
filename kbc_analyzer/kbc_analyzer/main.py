"""Terminal entry point — runs the analyzer interactively in the console.

This is the non-Telegram way to use the tool. Run it with:
    kbc-analyze         (after pip install -e .)
    python -m kbc_analyzer.main

It uses the interactive auth flow (prints a URL, waits for the user to paste back the
redirect URL) rather than the async Telegram bot flow.
"""
import os
import sys
from datetime import date

from dotenv import load_dotenv        # reads .env file into os.environ
from rich.console import Console

from .analysis import analyze
from .cache import (
    already_fetched_today,
    get_connection,
    load_transactions,
    purge_old_entries,
    save_transactions,
)
from .display import display_results
from .enablebanking import EnableBankingClient, EnableBankingError

# Load environment variables from .env before anything else reads them
load_dotenv()
console = Console()


def _month_start() -> date:
    """Return the first day of the current calendar month (e.g. 2026-05-01)."""
    return date.today().replace(day=1)


def main() -> None:
    console.print(
        "[bold green]KBC Expenditure Analyzer[/bold green] "
        "— powered by Enable Banking + Gemini\n"
    )

    # Fail fast if any required credentials are missing before making any API calls
    required_vars = ("ENABLEBANKING_APP_ID", "ENABLEBANKING_PRIVATE_KEY_PATH", "GEMINI_API_KEY")
    missing = [k for k in required_vars if not os.getenv(k)]
    if missing:
        console.print("[red]Missing environment variables:[/red]")
        for k in missing:
            console.print(f"  {k}")
        console.print("\nCreate a .env file — copy .env.example and fill in the values.")
        sys.exit(1)

    # Create the Enable Banking client (no network calls yet — just stores credentials)
    eb = EnableBankingClient(
        app_id=os.getenv("ENABLEBANKING_APP_ID"),
        private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
    )

    # ensure_session() either returns cached UIDs or runs the interactive OAuth flow
    try:
        account_uids = eb.ensure_session()
    except EnableBankingError as e:
        console.print(f"[red]Enable Banking error:[/red] {e}")
        sys.exit(1)

    if not account_uids:
        console.print("[yellow]No accounts found on this session.[/yellow]")
        sys.exit(0)

    console.print(f"[green]✓ Found {len(account_uids)} account(s)[/green]")

    # Always analyze from the first day of the current month to today
    date_from = _month_start()

    conn = get_connection()
    purge_old_entries(conn)  # clean up transactions older than 180 days to keep the DB small

    all_transactions: list[dict] = []

    for account_uid in account_uids:
        if already_fetched_today(conn, account_uid):
            # We already called the API today for this account — use the cached data
            txs = load_transactions(conn, account_uid, date_from)
            console.print(
                f"  Account {account_uid[:8]}… → {len(txs)} transactions [dim](cached)[/dim]"
            )
        else:
            # First fetch today — call the API and save results to the local database
            try:
                txs = eb.fetch_transactions(account_uid, date_from)
            except EnableBankingError as e:
                # If one account fails, continue with the others rather than aborting
                console.print(f"  [red]Failed to fetch account {account_uid[:8]}…: {e}[/red]")
                continue
            save_transactions(conn, account_uid, txs)
            console.print(
                f"  Account {account_uid[:8]}… → {len(txs)} transactions [dim](fetched from API)[/dim]"
            )
        all_transactions.extend(txs)

    conn.close()

    if not all_transactions:
        console.print("[yellow]No transactions found for the selected period.[/yellow]")
        sys.exit(0)

    console.print(f"\n[cyan]Total transactions to analyze: {len(all_transactions)}[/cyan]")

    # Let the user inject custom instructions into the Gemini prompt (optional)
    console.print("\n[dim]Add custom instructions for this analysis, or press Enter to skip:[/dim]")
    extra_note = input("> ").strip()

    try:
        # extra_note or None: pass None instead of empty string to skip the extra_note section
        analysis = analyze(all_transactions, date_from, extra_note or None)
    except RuntimeError as e:
        console.print(f"[red]Analysis error:[/red] {e}")
        sys.exit(1)

    # Render the full analysis as Rich tables in the terminal
    display_results(analysis, date_from.strftime("%B %Y"))


if __name__ == "__main__":
    main()
