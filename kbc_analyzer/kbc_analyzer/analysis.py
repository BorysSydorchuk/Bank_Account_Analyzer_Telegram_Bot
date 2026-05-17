"""Gemini AI integration — categorizes transactions and generates spending insights.

Sends transaction data to Google Gemini and asks it to return structured JSON.
Two main entry points:
  - analyze()  → full single-month analysis with daily/weekly breakdown
  - compare()  → month-over-month summary across 2–6 months
"""
import os
from datetime import date

from google import genai              # google-genai SDK (not the older google-generativeai)
from google.genai import types        # config objects like GenerateContentConfig
from pydantic import BaseModel        # data validation and parsing for Gemini's JSON output
from rich.console import Console

console = Console()

# ── Category definitions ───────────────────────────────────────────────────────
# These are injected verbatim into the Gemini prompt. Gemini is instructed to use
# only these exact strings when assigning categories to transactions.

CATEGORIES = (
    "Restaurants and Cafes, Groceries, Traveling, Investing, Savings"
    "Rent/Housing, Income, Transfers, Other"
)

# "Other" is a catch-all; these subcategories further break it down
SUBCATEGORIES_OF_OTHER = ("Entertainment, Health, Shopping, Utilities & Bills, Rest, Subscriptions")

# Traveling expenses are broken into these subcategories
SUBCATEGORIES_OF_TRAVELING = ("Transport, Housing, Food, Entertainment")

# ── System prompt ──────────────────────────────────────────────────────────────
# This is the instruction set sent to Gemini as the "system" message. It defines
# the output format, classification rules, and account-specific business logic.
SYSTEM_PROMPT = f"""You are a personal finance analyst. Analyze the following bank transactions and return a single JSON object — no prose, no markdown.

CATEGORIES (use these exact strings, nothing else):
{CATEGORIES}

SUBCATEGORIES OF OTHER (use only when category is "Other"):
{SUBCATEGORIES_OF_OTHER}

SUBCATEGORIES OF TRAVELING (use only when category is "Traveling"):
{SUBCATEGORIES_OF_TRAVELING}

CLASSIFICATION RULES:
- Negative amounts = money spent (debits)
- Positive amounts = money received (credits)
- total_spent = sum of absolute values of all negative amounts
- total_received = sum of all positive amounts
- category_totals = only include categories that actually appear in the data
- For "Other" and "Traveling", always populate their subcategory totals
- Treat transactions to [REDACTED-IBAN] ([REDACTED-NAME]) as an "Investing" category
- Neglect all the transactions between two observed accounts ([REDACTED-IBAN] to [REDACTED-IBAN] and the other way round)
- Treat transactions to [REDACTED-IBAN] as "Savings" category
- Transactions/payments to "[REDACTED-BUSINESS]" are expenditures on laundry, so its a part of Other/Utilities and Bills


SPENDING RHYTHM:
- Group transactions by day (YYYY-MM-DD) and by week (week number + date range)
- For each day: total spent, total received, list of transactions
- For each week: total spent, total received, busiest day, biggest single transaction

ANOMALY DETECTION:
- Flag every transaction where the absolute amount exceeds €50
- Also flag anything that looks out of pattern (e.g. same merchant charged twice, unusually large amount for its category)

INSIGHTS:
- Provide exactly 5 insights
- Focus on: daily/weekly rhythm patterns, which days of the week you spend most, category trends, flagged anomalies, one concrete suggestion to reduce spending
- Be specific — reference actual amounts, dates, and merchant names from the data

Return JSON with this structure:
{{
  "daily_summary": [
    {{
      "date": "YYYY-MM-DD",
      "total_spent": 0.0,
      "total_received": 0.0,
      "transactions": [
        {{"description": "...", "amount": 0.0, "category": "...", "subcategory": "...", "flagged": false}}
      ]
    }}
  ],
  "weekly_summary": [
    {{
      "week": "W21 (May 19–25)",
      "total_spent": 0.0,
      "total_received": 0.0,
      "busiest_day": "YYYY-MM-DD",
      "biggest_transaction": {{"description": "...", "amount": 0.0, "date": "YYYY-MM-DD"}}
    }}
  ],
  "category_totals": {{}},
  "other_subcategory_totals": {{}},
  "traveling_subcategory_totals": {{}},
  "flagged_transactions": [
    {{"description": "...", "amount": 0.0, "date": "YYYY-MM-DD", "reason": "..."}}
  ],
  "total_spent": 0.0,
  "total_received": 0.0,
  "insights": ["...", "...", "...", "...", "..."]
}}"""


# ── Pydantic models for the public API ────────────────────────────────────────
# These define the shape of the data the rest of the app works with.
# Pydantic validates field types automatically when we construct these objects.

class TransactionItem(BaseModel):
    """One transaction as categorized by Gemini."""
    description: str
    amount: float
    category: str
    subcategory: str = ""    # only filled for "Other" and "Traveling" categories
    flagged: bool = False    # True if Gemini flagged this as anomalous


class DayEntry(BaseModel):
    """Aggregated spending/income for a single calendar day."""
    date: str                              # "YYYY-MM-DD"
    total_spent: float
    total_received: float
    transactions: list[TransactionItem]   # all transactions that occurred on this day


class BiggestTransaction(BaseModel):
    """The largest single transaction within a week (used in WeekEntry)."""
    description: str
    amount: float
    date: str


class WeekEntry(BaseModel):
    """Aggregated spending/income for a calendar week."""
    week: str                              # e.g. "W21 (May 19–25)"
    total_spent: float
    total_received: float
    busiest_day: str                       # the day with the most activity
    biggest_transaction: BiggestTransaction


class FlaggedTransaction(BaseModel):
    """A transaction Gemini identified as anomalous or noteworthy."""
    description: str
    amount: float
    date: str
    reason: str                            # Gemini's explanation of why it was flagged


class Analysis(BaseModel):
    """Complete single-month analysis result returned by analyze()."""
    daily_summary: list[DayEntry]
    weekly_summary: list[WeekEntry]
    category_totals: dict[str, float]              # e.g. {"Groceries": 134.50, ...}
    other_subcategory_totals: dict[str, float]     # breakdown within "Other"
    traveling_subcategory_totals: dict[str, float] # breakdown within "Traveling"
    flagged_transactions: list[FlaggedTransaction]
    total_spent: float
    total_received: float
    insights: list[str]                            # exactly 5 Gemini-generated insights


# ── Internal Gemini response models ───────────────────────────────────────────
# Gemini's structured output (response_schema) doesn't support dict[str, float].
# Workaround: tell Gemini to return category totals as a list of {category, amount} pairs,
# then convert them to a proper dict after parsing.

class _KVPair(BaseModel):
    """A single category→amount mapping used inside Gemini's response."""
    category: str
    amount: float


class _GeminiAnalysis(BaseModel):
    """Mirror of Analysis, but with list[_KVPair] instead of dict[str, float] for totals.
    This is what we send as response_schema to Gemini.
    """
    daily_summary: list[DayEntry]
    weekly_summary: list[WeekEntry]
    category_totals: list[_KVPair]           # Gemini returns this as a list...
    other_subcategory_totals: list[_KVPair]
    traveling_subcategory_totals: list[_KVPair]
    flagged_transactions: list[FlaggedTransaction]
    total_spent: float
    total_received: float
    insights: list[str]


# ── Helper ─────────────────────────────────────────────────────────────────────

def _format_transactions(transactions: list[dict]) -> str:
    """Format a list of transaction dicts as a compact, date-grouped plain-text block.

    This is the text we send to Gemini. Grouping by date makes the prompt easier for
    the model to reason about daily patterns.

    Example output:
        2026-05-01:
          -12.50 EUR  Delhaize
          -3.20 EUR   Coffee corner
        2026-05-02:
          +2500.00 EUR  Salary
    """
    lines: list[str] = []
    current_date: str | None = None
    for t in sorted(transactions, key=lambda x: x["date"]):  # sort chronologically
        if t["date"] != current_date:
            # Print a date header the first time we see a new date
            current_date = t["date"]
            lines.append(f"\n{current_date}:")
        # +/- sign prefix makes spending vs. income immediately obvious
        lines.append(f"  {t['amount']:+.2f} EUR  {t['description'][:60]}")
    return "\n".join(lines)


# ── Single-month analysis ──────────────────────────────────────────────────────

def analyze(transactions: list[dict], date_from: date, extra_note: str | None = None) -> Analysis:
    """Send transactions to Gemini and return a fully structured Analysis object.

    Args:
        transactions: List of normalized transaction dicts (id, date, amount, description).
        date_from:    First day of the period being analyzed (used in the prompt context).
        extra_note:   Optional free-text instruction the user can add per run, e.g.
                      "Treat Amazon purchases as Shopping, not Entertainment".
    """
    # Initialize the Gemini client using the API key from the environment
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Convert transaction list to the plain-text format Gemini will read
    tx_text = _format_transactions(transactions)

    console.print(f"[cyan]Sending {len(transactions)} transactions to Gemini for analysis...[/cyan]")

    # Import here to avoid a circular reference at module level
    from datetime import date as _date
    period = f"{date_from.strftime('%B %Y')} to {_date.today().strftime('%B %Y')}"

    # Build the user message that contains the transaction data
    user_message = (
        f"Analyze these KBC bank transactions ({period}) "
        f"and return a complete analysis.\n\n{tx_text}"
    )
    if extra_note:
        # Append any user-provided extra instructions at the end
        user_message += f"\n\nAdditional instructions: {extra_note}"

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",   # fast, cost-effective Gemini model
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,           # our classification rules
                response_mime_type="application/json",      # force JSON output
                response_schema=_GeminiAnalysis,            # validate structure against our model
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    # Parse and validate the JSON response into our internal Gemini model
    raw = _GeminiAnalysis.model_validate_json(response.text)

    # Convert from the internal _GeminiAnalysis (list-based totals) to the public Analysis
    # (dict-based totals) that the rest of the app expects
    return Analysis(
        daily_summary=raw.daily_summary,
        weekly_summary=raw.weekly_summary,
        # Convert list[_KVPair] → dict[str, float] for each totals field
        category_totals={p.category: p.amount for p in raw.category_totals},
        other_subcategory_totals={p.category: p.amount for p in raw.other_subcategory_totals},
        traveling_subcategory_totals={p.category: p.amount for p in raw.traveling_subcategory_totals},
        flagged_transactions=raw.flagged_transactions,
        total_spent=raw.total_spent,
        total_received=raw.total_received,
        insights=raw.insights,
    )


# ── Monthly comparison ─────────────────────────────────────────────────────────

# Simpler prompt for the comparison flow — only needs totals and category breakdowns per month
COMPARISON_PROMPT = f"""You are a personal finance analyst. Compare bank transactions across multiple months.

Use exactly these categories (verbatim): {CATEGORIES}

Rules:
- Negative amounts = money spent, positive = money received
- total_spent = sum of absolute values of negative amounts per month
- total_received = sum of positive amounts per month
- category_totals = only categories that appear in that month's data
- Provide exactly 5 insights focused on month-over-month trends, notable changes,
  recurring patterns, and one concrete suggestion"""


class MonthSummary(BaseModel):
    """Spending summary for one month in a comparison result."""
    month: str                          # e.g. "May 2026"
    total_spent: float
    total_received: float
    category_totals: dict[str, float]   # only categories that had transactions this month


class ComparisonResult(BaseModel):
    """Result of compare() — summaries for each requested month plus cross-month insights."""
    month_summaries: list[MonthSummary]
    insights: list[str]                 # 5 Gemini insights comparing trends across months


# Internal Gemini models for comparison (same dict→list workaround as above)

class _MonthSummaryGemini(BaseModel):
    """Gemini's version of MonthSummary — uses list[_KVPair] for category_totals."""
    month: str
    total_spent: float
    total_received: float
    category_totals: list[_KVPair]      # will be converted to dict after parsing


class _ComparisonGemini(BaseModel):
    """Gemini's response schema for the comparison prompt."""
    month_summaries: list[_MonthSummaryGemini]
    insights: list[str]


def compare(months_transactions: dict[str, list[dict]]) -> ComparisonResult:
    """Compare transactions across multiple months and return a ComparisonResult.

    Args:
        months_transactions: Keys are "YYYY-MM" strings (e.g. "2026-04"), values are
                             lists of transaction dicts for that month.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Build one text block per month, sorted chronologically
    sections: list[str] = []
    for month_key in sorted(months_transactions):
        txs = months_transactions[month_key]
        sections.append(f"=== {month_key} ===")
        # If a month has no transactions, say so explicitly rather than leaving it blank
        sections.append(_format_transactions(txs) if txs else "  (no transactions)")

    # Combine all months into a single prompt message
    contents = "Compare these months' KBC bank transactions:\n\n" + "\n\n".join(sections)

    total_txs = sum(len(v) for v in months_transactions.values())
    console.print(
        f"[cyan]Sending {total_txs} transactions across "
        f"{len(months_transactions)} months to Gemini...[/cyan]"
    )

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=COMPARISON_PROMPT,
                response_mime_type="application/json",
                response_schema=_ComparisonGemini,   # use the list-based internal schema
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    raw = _ComparisonGemini.model_validate_json(response.text)

    # Convert internal Gemini response to the public ComparisonResult
    return ComparisonResult(
        month_summaries=[
            MonthSummary(
                month=m.month,
                total_spent=m.total_spent,
                total_received=m.total_received,
                # Convert list[_KVPair] → dict[str, float]
                category_totals={p.category: p.amount for p in m.category_totals},
            )
            for m in raw.month_summaries
        ],
        insights=raw.insights,
    )
