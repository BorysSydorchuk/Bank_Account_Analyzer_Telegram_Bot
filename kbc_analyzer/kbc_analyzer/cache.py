"""SQLite caching layer — stores fetched transactions locally to avoid hitting the bank API repeatedly."""
import sqlite3
from datetime import date, timedelta

# Path to the local SQLite database file (created automatically on first run)
DB_FILE = "kbc_transactions.db"


def get_connection() -> sqlite3.Connection:
    """Open (or create) the database and ensure all required tables exist."""
    conn = sqlite3.connect(DB_FILE)

    # row_factory makes each row behave like a dict, so we can write row["amount"] instead of row[3]
    conn.row_factory = sqlite3.Row

    # Create the three tables if they don't exist yet (safe to call every time)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          TEXT,       -- bank-assigned transaction reference
            account_id  TEXT,       -- Enable Banking account UID
            date        TEXT,       -- booking date as ISO string (YYYY-MM-DD)
            amount      REAL,       -- signed euro amount: negative = spent, positive = received
            description TEXT,       -- merchant name or sender/recipient
            fetched_on  TEXT,       -- date we downloaded this transaction (for cache expiry)
            PRIMARY KEY (id, account_id)  -- same transaction id can appear on different accounts
        );

        CREATE TABLE IF NOT EXISTS fetch_log (
            -- Records which accounts were fetched on which calendar day.
            -- Used to skip re-fetching the same account more than once per day.
            account_id TEXT,
            fetched_on TEXT,        -- ISO date (YYYY-MM-DD)
            PRIMARY KEY (account_id, fetched_on)
        );

        CREATE TABLE IF NOT EXISTS month_fetch_log (
            -- Records which past months have been fully downloaded per account.
            -- Past months never change, so we only need to fetch them once ever.
            account_id TEXT,
            month_key  TEXT,        -- e.g. "2026-04" (year-month string)
            PRIMARY KEY (account_id, month_key)
        );
    """)
    conn.commit()
    return conn


def already_fetched_today(conn: sqlite3.Connection, account_id: str) -> bool:
    """Return True if we already downloaded transactions for this account today.

    Prevents making an API call more than once per day for the same account.
    """
    today = date.today().isoformat()  # e.g. "2026-05-18"
    row = conn.execute(
        "SELECT 1 FROM fetch_log WHERE account_id = ? AND fetched_on = ?",
        (account_id, today),
    ).fetchone()
    return row is not None  # None means no row found → not fetched yet


def already_fetched_month(conn: sqlite3.Connection, account_id: str, month_key: str) -> bool:
    """Return True if we already fully fetched a past month (e.g. '2026-04').

    Past months are immutable — once all their transactions are cached, we never re-fetch them.
    """
    row = conn.execute(
        "SELECT 1 FROM month_fetch_log WHERE account_id = ? AND month_key = ?",
        (account_id, month_key),
    ).fetchone()
    return row is not None


def mark_month_fetched(conn: sqlite3.Connection, account_id: str, month_key: str) -> None:
    """Permanently mark a past month as fully cached so it won't be re-fetched."""
    conn.execute(
        "INSERT OR REPLACE INTO month_fetch_log VALUES (?, ?)",
        (account_id, month_key),
    )
    conn.commit()


def load_transactions(
    conn: sqlite3.Connection,
    account_id: str,
    date_from: date,
    date_to: date | None = None,  # if None, return everything from date_from to the latest stored
) -> list[dict]:
    """Read cached transactions from the database for one account within a date range."""
    if date_to is None:
        # No upper bound — fetch everything from date_from onwards
        rows = conn.execute(
            "SELECT id, date, amount, description FROM transactions "
            "WHERE account_id = ? AND date >= ? ORDER BY date",
            (account_id, date_from.isoformat()),
        ).fetchall()
    else:
        # Inclusive range: date_from ≤ date ≤ date_to
        rows = conn.execute(
            "SELECT id, date, amount, description FROM transactions "
            "WHERE account_id = ? AND date >= ? AND date <= ? ORDER BY date",
            (account_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchall()

    # Convert sqlite3.Row objects to plain dicts so the rest of the code doesn't depend on sqlite3
    return [dict(r) for r in rows]


def save_transactions(conn: sqlite3.Connection, account_id: str, transactions: list[dict]) -> None:
    """Write freshly fetched transactions to the database and record today's fetch in fetch_log."""
    today = date.today().isoformat()

    # INSERT OR REPLACE overwrites duplicate (id, account_id) pairs — safe to call repeatedly
    conn.executemany(
        "INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?, ?, ?)",
        [
            (t["id"], account_id, t["date"], t["amount"], t["description"], today)
            for t in transactions
        ],
    )

    # Mark that we fetched this account today so already_fetched_today() returns True next call
    conn.execute(
        "INSERT OR REPLACE INTO fetch_log VALUES (?, ?)",
        (account_id, today),
    )
    conn.commit()


def purge_old_entries(conn: sqlite3.Connection, keep_days: int = 180) -> None:
    """Delete transactions and fetch-log entries older than keep_days days.

    Keeps the database from growing indefinitely; 180 days ≈ 6 months of history.
    """
    # Calculate the oldest date we want to keep
    cutoff = (date.today() - timedelta(days=keep_days)).isoformat()

    conn.execute("DELETE FROM transactions WHERE date < ?", (cutoff,))
    conn.execute("DELETE FROM fetch_log WHERE fetched_on < ?", (cutoff,))
    conn.commit()
