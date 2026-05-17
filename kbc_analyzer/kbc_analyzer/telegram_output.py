"""Format Analysis and ComparisonResult as Telegram HTML message chunks."""
import html

from .analysis import Analysis, ComparisonResult

CHUNK_SIZE = 3800  # Telegram max is 4096; leave headroom


def _e(text: str) -> str:
    return html.escape(str(text))


def format_analysis(analysis: Analysis, month_label: str) -> list[str]:
    parts: list[str] = []

    parts.append(f"<b>📊 KBC Expenditure — {_e(month_label)}</b>")

    # Weekly summary
    if analysis.weekly_summary:
        lines = ["<b>📅 Weekly Summary</b>"]
        for w in analysis.weekly_summary:
            bt = w.biggest_transaction
            lines.append(
                f"  <b>{_e(w.week)}</b>  "
                f"spent €{w.total_spent:.2f} / received €{w.total_received:.2f}\n"
                f"  Biggest: {_e(bt.description[:28])} ({bt.amount:+.2f}€)"
            )
        parts.append("\n".join(lines))

    # Category totals
    cats = [(c, v) for c, v in sorted(analysis.category_totals.items(), key=lambda x: x[1], reverse=True) if v > 0]
    if cats:
        lines = ["<b>🏷 Spending by Category</b>"]
        for cat, total in cats:
            lines.append(f"  {_e(cat)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # Other subcategories
    if analysis.other_subcategory_totals:
        lines = ["<b>Other — Breakdown</b>"]
        for sub, total in sorted(analysis.other_subcategory_totals.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                lines.append(f"  {_e(sub)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # Traveling subcategories
    if analysis.traveling_subcategory_totals:
        lines = ["<b>✈️ Traveling — Breakdown</b>"]
        for sub, total in sorted(analysis.traveling_subcategory_totals.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                lines.append(f"  {_e(sub)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # Flagged transactions
    if analysis.flagged_transactions:
        lines = ["<b>⚑ Flagged Transactions</b>"]
        for ft in sorted(analysis.flagged_transactions, key=lambda x: x.date):
            lines.append(
                f"  {ft.date}  <b>{_e(ft.description[:28])}</b>  {ft.amount:+.2f}€\n"
                f"  ↳ {_e(ft.reason)}"
            )
        parts.append("\n".join(lines))

    # Daily breakdown
    lines = ["<b>📆 Daily Breakdown</b>"]
    for day in sorted(analysis.daily_summary, key=lambda d: d.date):
        if day.total_spent == 0 and day.total_received == 0:
            continue
        top = sorted(day.transactions, key=lambda t: abs(t.amount), reverse=True)[:2]
        top_text = " | ".join(
            f"{'⚑ ' if t.flagged else ''}{_e(t.description[:20])} ({t.amount:+.2f}€)"
            for t in top
        )
        lines.append(f"  <b>{day.date}</b>  −€{day.total_spent:.2f} / +€{day.total_received:.2f}")
        if top_text:
            lines.append(f"  {top_text}")
    parts.append("\n".join(lines))

    # Summary
    net = analysis.total_received - analysis.total_spent
    sign = "+" if net >= 0 else ""
    parts.append(
        f"<b>💰 Summary</b>\n"
        f"  Spent:    €{analysis.total_spent:.2f}\n"
        f"  Received: €{analysis.total_received:.2f}\n"
        f"  Net:      {sign}€{net:.2f}"
    )

    # Insights
    lines = ["<b>💡 Insights</b>"]
    for i, insight in enumerate(analysis.insights, 1):
        lines.append(f"  {i}. {_e(insight)}")
    parts.append("\n".join(lines))

    return _chunk(parts)


def format_comparison(result: ComparisonResult) -> list[str]:
    parts: list[str] = []

    parts.append("<b>📊 Monthly Comparison</b>")

    lines = ["<b>💰 Totals per Month</b>"]
    for m in result.month_summaries:
        net = m.total_received - m.total_spent
        sign = "+" if net >= 0 else ""
        lines.append(
            f"  <b>{_e(m.month)}</b>\n"
            f"  Spent €{m.total_spent:.2f} / Received €{m.total_received:.2f} / Net {sign}€{net:.2f}"
        )
    parts.append("\n".join(lines))

    all_cats = sorted({cat for m in result.month_summaries for cat in m.category_totals if m.category_totals[cat] > 0})
    if all_cats:
        lines = ["<b>🏷 Category Breakdown</b>"]
        for cat in all_cats:
            row = "  " + _e(cat)
            for m in result.month_summaries:
                total = m.category_totals.get(cat, 0)
                row += f"  |  {m.month}: €{total:.2f}" if total else f"  |  {m.month}: —"
            lines.append(row)
        parts.append("\n".join(lines))

    lines = ["<b>💡 Insights</b>"]
    for i, insight in enumerate(result.insights, 1):
        lines.append(f"  {i}. {_e(insight)}")
    parts.append("\n".join(lines))

    return _chunk(parts)


def _chunk(parts: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + "\n\n" + part).strip()
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks
