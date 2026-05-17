import os

from google import genai
from google.genai import types
from pydantic import BaseModel
from rich.console import Console

console = Console()

CATEGORIES = (
    "Restaurants and Cafes, Groceries, Traveling, Investing, Savings"
    "Rent/Housing, Income, Transfers, Other"
)

SUBCATEGORIES_OF_OTHER = ("Entertainment, Health, Shopping, Utilities & Bills, Rest, Subscriptions")

SUBCATEGORIES_OF_TRAVELING = ("Transport, Housing, Food, Entertainment")

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



class TransactionItem(BaseModel):
    description: str
    amount: float
    category: str
    subcategory: str = ""
    flagged: bool = False


class DayEntry(BaseModel):
    date: str
    total_spent: float
    total_received: float
    transactions: list[TransactionItem]


class BiggestTransaction(BaseModel):
    description: str
    amount: float
    date: str


class WeekEntry(BaseModel):
    week: str
    total_spent: float
    total_received: float
    busiest_day: str
    biggest_transaction: BiggestTransaction


class FlaggedTransaction(BaseModel):
    description: str
    amount: float
    date: str
    reason: str


class Analysis(BaseModel):
    daily_summary: list[DayEntry]
    weekly_summary: list[WeekEntry]
    category_totals: dict[str, float]
    other_subcategory_totals: dict[str, float]
    traveling_subcategory_totals: dict[str, float]
    flagged_transactions: list[FlaggedTransaction]
    total_spent: float
    total_received: float
    insights: list[str]


class _KVPair(BaseModel):
    category: str
    amount: float


class _GeminiAnalysis(BaseModel):
    daily_summary: list[DayEntry]
    weekly_summary: list[WeekEntry]
    category_totals: list[_KVPair]
    other_subcategory_totals: list[_KVPair]
    traveling_subcategory_totals: list[_KVPair]
    flagged_transactions: list[FlaggedTransaction]
    total_spent: float
    total_received: float
    insights: list[str]


def _format_transactions(transactions: list[dict]) -> str:
    lines: list[str] = []
    current_date: str | None = None
    for t in sorted(transactions, key=lambda x: x["date"]):
        if t["date"] != current_date:
            current_date = t["date"]
            lines.append(f"\n{current_date}:")
        lines.append(f"  {t['amount']:+.2f} EUR  {t['description'][:60]}")
    return "\n".join(lines)


def analyze(transactions: list[dict], date_from: date, extra_note: str | None = None) -> Analysis:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    tx_text = _format_transactions(transactions)

    console.print(f"[cyan]Sending {len(transactions)} transactions to Gemini for analysis...[/cyan]")

    from datetime import date as _date
    period = f"{date_from.strftime('%B %Y')} to {_date.today().strftime('%B %Y')}"
    user_message = (
        f"Analyze these KBC bank transactions ({period}) "
        f"and return a complete analysis.\n\n{tx_text}"
    )
    if extra_note:
        user_message += f"\n\nAdditional instructions: {extra_note}"

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_GeminiAnalysis,
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    raw = _GeminiAnalysis.model_validate_json(response.text)
    return Analysis(
        daily_summary=raw.daily_summary,
        weekly_summary=raw.weekly_summary,
        category_totals={p.category: p.amount for p in raw.category_totals},
        other_subcategory_totals={p.category: p.amount for p in raw.other_subcategory_totals},
        traveling_subcategory_totals={p.category: p.amount for p in raw.traveling_subcategory_totals},
        flagged_transactions=raw.flagged_transactions,
        total_spent=raw.total_spent,
        total_received=raw.total_received,
        insights=raw.insights,
    )


# --- Monthly comparison ---

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
    month: str
    total_spent: float
    total_received: float
    category_totals: dict[str, float]


class ComparisonResult(BaseModel):
    month_summaries: list[MonthSummary]
    insights: list[str]


class _MonthSummaryGemini(BaseModel):
    month: str
    total_spent: float
    total_received: float
    category_totals: list[_KVPair]


class _ComparisonGemini(BaseModel):
    month_summaries: list[_MonthSummaryGemini]
    insights: list[str]


def compare(months_transactions: dict[str, list[dict]]) -> ComparisonResult:
    """Compare transactions across months. months_transactions keys are 'YYYY-MM' strings."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    sections: list[str] = []
    for month_key in sorted(months_transactions):
        txs = months_transactions[month_key]
        sections.append(f"=== {month_key} ===")
        sections.append(_format_transactions(txs) if txs else "  (no transactions)")

    contents = "Compare these months' KBC bank transactions:\n\n" + "\n\n".join(sections)

    console.print(f"[cyan]Sending {sum(len(v) for v in months_transactions.values())} transactions across {len(months_transactions)} months to Gemini...[/cyan]")

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=COMPARISON_PROMPT,
                response_mime_type="application/json",
                response_schema=_ComparisonGemini,
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    raw = _ComparisonGemini.model_validate_json(response.text)
    return ComparisonResult(
        month_summaries=[
            MonthSummary(
                month=m.month,
                total_spent=m.total_spent,
                total_received=m.total_received,
                category_totals={p.category: p.amount for p in m.category_totals},
            )
            for m in raw.month_summaries
        ],
        insights=raw.insights,
    )