"""Rich terminal output — renders an Analysis object as formatted tables in the console.

Uses the Rich library for colored, box-drawn tables. This module is only used by
main.py (the terminal entry point); the Telegram bot uses telegram_output.py instead.
"""
from rich import box
from rich.console import Console
from rich.table import Table

from .analysis import Analysis  # the Pydantic model returned by analysis.analyze()

console = Console()


def display_results(analysis: Analysis, month_label: str) -> None:
    """Print all analysis sections to the terminal using Rich formatting.

    Args:
        analysis:    The structured result from analysis.analyze().
        month_label: Human-readable month string shown in headings, e.g. "May 2026".
    """
    console.print()
    console.rule("[bold blue]KBC Expenditure Analysis[/bold blue]")

    # ── Daily breakdown ────────────────────────────────────────────────────────
    console.print(f"\n[bold]Daily Breakdown — {month_label}[/bold]\n")

    # Create a table with rounded borders; column widths are fixed to keep layout stable
    daily_table = Table(box=box.ROUNDED, header_style="bold magenta", show_lines=False)
    daily_table.add_column("Date", style="cyan", width=12)
    daily_table.add_column("Spent (€)", justify="right", style="red", width=10)
    daily_table.add_column("Received (€)", justify="right", style="green", width=13)
    daily_table.add_column("Top Transactions", style="white", max_width=55)

    for day in sorted(analysis.daily_summary, key=lambda d: d.date):
        # Show at most 2 transactions per day (sorted by size) to keep the table compact
        top = sorted(day.transactions, key=lambda t: abs(t.amount), reverse=True)[:2]
        top_text = "  |  ".join(
            # Prepend ⚑ flag symbol if Gemini flagged this transaction as anomalous
            f"{'⚑ ' if t.flagged else ''}{t.description[:22]} ({t.amount:+.2f}€)" for t in top
        ) or "—"  # fallback if the day has no transactions
        daily_table.add_row(
            day.date,
            f"{day.total_spent:.2f}",
            f"{day.total_received:.2f}",
            top_text,
        )
    console.print(daily_table)

    # ── Weekly summary ─────────────────────────────────────────────────────────
    if analysis.weekly_summary:
        console.print("\n[bold]Weekly Summary[/bold]\n")
        week_table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=False)
        week_table.add_column("Week", style="cyan", width=20)
        week_table.add_column("Spent (€)", justify="right", style="red", width=10)
        week_table.add_column("Received (€)", justify="right", style="green", width=13)
        week_table.add_column("Busiest Day", style="white", width=12)
        week_table.add_column("Biggest Transaction", style="white", max_width=38)

        for week in analysis.weekly_summary:
            bt = week.biggest_transaction  # shorthand
            week_table.add_row(
                week.week,
                f"{week.total_spent:.2f}",
                f"{week.total_received:.2f}",
                week.busiest_day,
                f"{bt.description[:24]} ({bt.amount:+.2f}€)",
            )
        console.print(week_table)

    # ── Category totals ────────────────────────────────────────────────────────
    console.print("\n[bold]Spending by Category[/bold]\n")
    cat_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
    cat_table.add_column("Category", style="yellow", width=22)
    cat_table.add_column("Amount (€)", justify="right", style="red", width=12)

    # Sort categories by total descending so the biggest spends appear first
    for cat, total in sorted(analysis.category_totals.items(), key=lambda x: x[1], reverse=True):
        if total > 0:  # skip zero-amount categories (shouldn't appear but guard anyway)
            cat_table.add_row(cat, f"{total:.2f}")
    console.print(cat_table)

    # ── Subcategory breakdowns ─────────────────────────────────────────────────
    # "Other" and "Traveling" have their own subcategory breakdowns

    if analysis.other_subcategory_totals:
        console.print("\n[bold]Other — Breakdown[/bold]\n")
        other_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
        other_table.add_column("Subcategory", style="yellow", width=22)
        other_table.add_column("Amount (€)", justify="right", style="red", width=12)
        for sub, total in sorted(
            analysis.other_subcategory_totals.items(), key=lambda x: x[1], reverse=True
        ):
            if total > 0:
                other_table.add_row(sub, f"{total:.2f}")
        console.print(other_table)

    if analysis.traveling_subcategory_totals:
        console.print("\n[bold]Traveling — Breakdown[/bold]\n")
        travel_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
        travel_table.add_column("Subcategory", style="yellow", width=22)
        travel_table.add_column("Amount (€)", justify="right", style="red", width=12)
        for sub, total in sorted(
            analysis.traveling_subcategory_totals.items(), key=lambda x: x[1], reverse=True
        ):
            if total > 0:
                travel_table.add_row(sub, f"{total:.2f}")
        console.print(travel_table)

    # ── Flagged transactions ───────────────────────────────────────────────────
    if analysis.flagged_transactions:
        console.print("\n[bold]Flagged Transactions[/bold]\n")
        flag_table = Table(box=box.SIMPLE, header_style="bold red", show_edge=False)
        flag_table.add_column("Date", style="cyan", width=12)
        flag_table.add_column("Description", style="white", width=28)
        flag_table.add_column("Amount (€)", justify="right", style="red", width=12)
        flag_table.add_column("Reason", style="yellow", max_width=38)
        for ft in sorted(analysis.flagged_transactions, key=lambda x: x.date):
            flag_table.add_row(ft.date, ft.description[:26], f"{ft.amount:+.2f}", ft.reason)
        console.print(flag_table)

    # ── Summary totals ─────────────────────────────────────────────────────────
    console.print("\n[bold]Summary[/bold]")
    console.print(f"  Total spent:    [red]€{analysis.total_spent:.2f}[/red]")
    console.print(f"  Total received: [green]€{analysis.total_received:.2f}[/green]")
    net = analysis.total_received - analysis.total_spent
    # Color the net amount green if positive (more income than expenses), red if negative
    net_color = "green" if net >= 0 else "red"
    console.print(f"  Net:            [{net_color}]€{net:+.2f}[/{net_color}]")

    # ── Insights ───────────────────────────────────────────────────────────────
    console.print("\n[bold]Insights[/bold]")
    for insight in analysis.insights:
        console.print(f"  • {insight}")

    console.print()
