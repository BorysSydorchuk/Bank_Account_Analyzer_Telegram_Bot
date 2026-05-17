from rich import box
from rich.console import Console
from rich.table import Table

from .analysis import Analysis

console = Console()


def display_results(analysis: Analysis, month_label: str) -> None:
    console.print()
    console.rule("[bold blue]KBC Expenditure Analysis[/bold blue]")

    # --- Daily breakdown ---
    console.print(f"\n[bold]Daily Breakdown — {month_label}[/bold]\n")
    daily_table = Table(box=box.ROUNDED, header_style="bold magenta", show_lines=False)
    daily_table.add_column("Date", style="cyan", width=12)
    daily_table.add_column("Spent (€)", justify="right", style="red", width=10)
    daily_table.add_column("Received (€)", justify="right", style="green", width=13)
    daily_table.add_column("Top Transactions", style="white", max_width=55)

    for day in sorted(analysis.daily_summary, key=lambda d: d.date):
        top = sorted(day.transactions, key=lambda t: abs(t.amount), reverse=True)[:2]
        top_text = "  |  ".join(
            f"{'⚑ ' if t.flagged else ''}{t.description[:22]} ({t.amount:+.2f}€)" for t in top
        ) or "—"
        daily_table.add_row(
            day.date,
            f"{day.total_spent:.2f}",
            f"{day.total_received:.2f}",
            top_text,
        )
    console.print(daily_table)

    # --- Weekly summary ---
    if analysis.weekly_summary:
        console.print("\n[bold]Weekly Summary[/bold]\n")
        week_table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=False)
        week_table.add_column("Week", style="cyan", width=20)
        week_table.add_column("Spent (€)", justify="right", style="red", width=10)
        week_table.add_column("Received (€)", justify="right", style="green", width=13)
        week_table.add_column("Busiest Day", style="white", width=12)
        week_table.add_column("Biggest Transaction", style="white", max_width=38)

        for week in analysis.weekly_summary:
            bt = week.biggest_transaction
            week_table.add_row(
                week.week,
                f"{week.total_spent:.2f}",
                f"{week.total_received:.2f}",
                week.busiest_day,
                f"{bt.description[:24]} ({bt.amount:+.2f}€)",
            )
        console.print(week_table)

    # --- Category totals ---
    console.print("\n[bold]Spending by Category[/bold]\n")
    cat_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
    cat_table.add_column("Category", style="yellow", width=22)
    cat_table.add_column("Amount (€)", justify="right", style="red", width=12)

    for cat, total in sorted(analysis.category_totals.items(), key=lambda x: x[1], reverse=True):
        if total > 0:
            cat_table.add_row(cat, f"{total:.2f}")
    console.print(cat_table)

    # --- Subcategory breakdowns ---
    if analysis.other_subcategory_totals:
        console.print("\n[bold]Other — Breakdown[/bold]\n")
        other_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
        other_table.add_column("Subcategory", style="yellow", width=22)
        other_table.add_column("Amount (€)", justify="right", style="red", width=12)
        for sub, total in sorted(analysis.other_subcategory_totals.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                other_table.add_row(sub, f"{total:.2f}")
        console.print(other_table)

    if analysis.traveling_subcategory_totals:
        console.print("\n[bold]Traveling — Breakdown[/bold]\n")
        travel_table = Table(box=box.SIMPLE, header_style="bold yellow", show_edge=False)
        travel_table.add_column("Subcategory", style="yellow", width=22)
        travel_table.add_column("Amount (€)", justify="right", style="red", width=12)
        for sub, total in sorted(analysis.traveling_subcategory_totals.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                travel_table.add_row(sub, f"{total:.2f}")
        console.print(travel_table)

    # --- Flagged transactions ---
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

    # --- Summary ---
    console.print("\n[bold]Summary[/bold]")
    console.print(f"  Total spent:    [red]€{analysis.total_spent:.2f}[/red]")
    console.print(f"  Total received: [green]€{analysis.total_received:.2f}[/green]")
    net = analysis.total_received - analysis.total_spent
    net_color = "green" if net >= 0 else "red"
    console.print(f"  Net:            [{net_color}]€{net:+.2f}[/{net_color}]")

    # --- Insights ---
    console.print("\n[bold]Insights[/bold]")
    for insight in analysis.insights:
        console.print(f"  • {insight}")

    console.print()
