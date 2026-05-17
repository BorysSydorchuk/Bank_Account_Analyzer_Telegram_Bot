import os
import sys
from datetime import date

from dotenv import load_dotenv
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

load_dotenv()
console = Console()


def _month_start() -> date:
    return date.today().replace(day=1)


def main() -> None:
    console.print(
        "[bold green]KBC Expenditure Analyzer[/bold green] "
        "— powered by Enable Banking + Gemini\n"
    )

    required_vars = ("ENABLEBANKING_APP_ID", "ENABLEBANKING_PRIVATE_KEY_PATH", "GEMINI_API_KEY")
    missing = [k for k in required_vars if not os.getenv(k)]
    if missing:
        console.print("[red]Missing environment variables:[/red]")
        for k in missing:
            console.print(f"  {k}")
        console.print("\nCreate a .env file — copy .env.example and fill in the values.")
        sys.exit(1)

    eb = EnableBankingClient(
        app_id=os.getenv("ENABLEBANKING_APP_ID"),
        private_key_path=os.getenv("ENABLEBANKING_PRIVATE_KEY_PATH"),
    )

    try:
        account_uids = eb.ensure_session()
    except EnableBankingError as e:
        console.print(f"[red]Enable Banking error:[/red] {e}")
        sys.exit(1)

    if not account_uids:
        console.print("[yellow]No accounts found on this session.[/yellow]")
        sys.exit(0)

    console.print(f"[green]✓ Found {len(account_uids)} account(s)[/green]")

    date_from = _month_start()
    conn = get_connection()
    purge_old_entries(conn)

    all_transactions: list[dict] = []
    for account_uid in account_uids:
        if already_fetched_today(conn, account_uid):
            txs = load_transactions(conn, account_uid, date_from)
            console.print(
                f"  Account {account_uid[:8]}… → {len(txs)} transactions [dim](cached)[/dim]"
            )
        else:
            try:
                txs = eb.fetch_transactions(account_uid, date_from)
            except EnableBankingError as e:
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
    console.print("\n[dim]Add custom instructions for this analysis, or press Enter to skip:[/dim]")
    extra_note = input("> ").strip()

    try:
        analysis = analyze(all_transactions, date_from, extra_note or None)
    except RuntimeError as e:
        console.print(f"[red]Analysis error:[/red] {e}")
        sys.exit(1)

    display_results(analysis, date_from.strftime("%B %Y"))


if __name__ == "__main__":
    main()
