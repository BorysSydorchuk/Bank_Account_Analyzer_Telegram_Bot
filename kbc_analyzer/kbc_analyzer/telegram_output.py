"""Format Analysis and ComparisonResult as Telegram HTML message chunks.

Telegram has a 4096-character per-message limit. This module converts the structured
analysis data into HTML-formatted strings and splits them into chunks that fit within
that limit. Telegram supports a subset of HTML: <b>, <i>, <code>, <pre>, <a>.
"""
import html

from .analysis import Analysis, ComparisonResult

# Safety margin below Telegram's 4096-char limit — leaves room for any formatting overhead
CHUNK_SIZE = 3800


def _e(text: str) -> str:
    """Escape a string for safe inclusion in HTML (converts < > & to entities).

    Any user-controlled text (merchant names, descriptions, etc.) must be escaped
    before being placed inside HTML tags to prevent malformed messages.
    """
    return html.escape(str(text))


def format_analysis(analysis: Analysis, month_label: str) -> list[str]:
    """Convert a single-month Analysis into a list of Telegram HTML message strings.

    Each string in the returned list is one Telegram message (≤ CHUNK_SIZE chars).
    The caller sends them in order.
    """
    # Build the message as a list of self-contained "parts" (sections).
    # _chunk() will then group them into Telegram-sized messages.
    parts: list[str] = []

    # Header
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

    # Category totals — filter to only categories that have a non-zero total, sorted by size
    cats = [
        (c, v) for c, v in sorted(analysis.category_totals.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]
    if cats:
        lines = ["<b>🏷 Spending by Category</b>"]
        for cat, total in cats:
            lines.append(f"  {_e(cat)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # "Other" subcategory breakdown (e.g. Entertainment, Health, Shopping…)
    if analysis.other_subcategory_totals:
        lines = ["<b>Other — Breakdown</b>"]
        for sub, total in sorted(
            analysis.other_subcategory_totals.items(), key=lambda x: x[1], reverse=True
        ):
            if total > 0:
                lines.append(f"  {_e(sub)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # "Traveling" subcategory breakdown (e.g. Transport, Housing, Food…)
    if analysis.traveling_subcategory_totals:
        lines = ["<b>✈️ Traveling — Breakdown</b>"]
        for sub, total in sorted(
            analysis.traveling_subcategory_totals.items(), key=lambda x: x[1], reverse=True
        ):
            if total > 0:
                lines.append(f"  {_e(sub)}: €{total:.2f}")
        parts.append("\n".join(lines))

    # Flagged transactions (anomalies detected by Gemini)
    if analysis.flagged_transactions:
        lines = ["<b>⚑ Flagged Transactions</b>"]
        for ft in sorted(analysis.flagged_transactions, key=lambda x: x.date):
            lines.append(
                f"  {ft.date}  <b>{_e(ft.description[:28])}</b>  {ft.amount:+.2f}€\n"
                f"  ↳ {_e(ft.reason)}"   # ↳ is an arrow indicating the reason line
            )
        parts.append("\n".join(lines))

    # Daily breakdown (compact one-liner per day with top 2 transactions)
    lines = ["<b>📆 Daily Breakdown</b>"]
    for day in sorted(analysis.daily_summary, key=lambda d: d.date):
        # Skip days with no activity (can happen if date range extends to future)
        if day.total_spent == 0 and day.total_received == 0:
            continue
        # Show top 2 transactions by absolute value to stay within line length
        top = sorted(day.transactions, key=lambda t: abs(t.amount), reverse=True)[:2]
        top_text = " | ".join(
            f"{'⚑ ' if t.flagged else ''}{_e(t.description[:20])} ({t.amount:+.2f}€)"
            for t in top
        )
        lines.append(f"  <b>{day.date}</b>  −€{day.total_spent:.2f} / +€{day.total_received:.2f}")
        if top_text:
            lines.append(f"  {top_text}")
    parts.append("\n".join(lines))

    # Summary totals
    net = analysis.total_received - analysis.total_spent
    sign = "+" if net >= 0 else ""  # manually add + sign since Python doesn't for positive floats
    parts.append(
        f"<b>💰 Summary</b>\n"
        f"  Spent:    €{analysis.total_spent:.2f}\n"
        f"  Received: €{analysis.total_received:.2f}\n"
        f"  Net:      {sign}€{net:.2f}"
    )

    # Gemini insights (numbered list)
    lines = ["<b>💡 Insights</b>"]
    for i, insight in enumerate(analysis.insights, 1):
        lines.append(f"  {i}. {_e(insight)}")
    parts.append("\n".join(lines))

    # Split into Telegram-sized messages and return
    return _chunk(parts)


def format_comparison(result: ComparisonResult) -> list[str]:
    """Convert a ComparisonResult (multiple months) into a list of Telegram HTML messages."""
    parts: list[str] = []

    parts.append("<b>📊 Monthly Comparison</b>")

    # One block showing totals for each month side by side
    lines = ["<b>💰 Totals per Month</b>"]
    for m in result.month_summaries:
        net = m.total_received - m.total_spent
        sign = "+" if net >= 0 else ""
        lines.append(
            f"  <b>{_e(m.month)}</b>\n"
            f"  Spent €{m.total_spent:.2f} / Received €{m.total_received:.2f} / Net {sign}€{net:.2f}"
        )
    parts.append("\n".join(lines))

    # Collect all categories that appear in any month (for the comparison grid)
    all_cats = sorted({
        cat
        for m in result.month_summaries
        for cat in m.category_totals
        if m.category_totals[cat] > 0
    })
    if all_cats:
        lines = ["<b>🏷 Category Breakdown</b>"]
        for cat in all_cats:
            # Build one row per category showing each month's spend (or "—" if absent)
            row = "  " + _e(cat)
            for m in result.month_summaries:
                total = m.category_totals.get(cat, 0)
                row += f"  |  {m.month}: €{total:.2f}" if total else f"  |  {m.month}: —"
            lines.append(row)
        parts.append("\n".join(lines))

    # Cross-month insights from Gemini
    lines = ["<b>💡 Insights</b>"]
    for i, insight in enumerate(result.insights, 1):
        lines.append(f"  {i}. {_e(insight)}")
    parts.append("\n".join(lines))

    return _chunk(parts)


def _chunk(parts: list[str]) -> list[str]:
    """Pack a list of text sections into Telegram-sized messages (≤ CHUNK_SIZE chars).

    Each section is separated by a blank line. If adding the next section would exceed
    the limit, we start a new message. A section that is itself larger than CHUNK_SIZE
    will be sent alone (no further splitting is done at the character level).
    """
    chunks: list[str] = []
    current = ""
    for part in parts:
        # Try appending this section (with a blank line separator) to the current message
        candidate = (current + "\n\n" + part).strip()
        if len(candidate) <= CHUNK_SIZE:
            current = candidate          # fits — keep building this message
        else:
            if current:
                chunks.append(current)   # save the current message before starting a new one
            current = part               # start a fresh message with this section
    if current:
        chunks.append(current)           # don't forget the last message
    return chunks
