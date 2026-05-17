import sqlite3
from datetime import date, timedelta

DB_FILE = "kbc_transactions.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          TEXT,
            account_id  TEXT,
            date        TEXT,
            amount      REAL,
            description TEXT,
            fetched_on  TEXT,
            PRIMARY KEY (id, account_id)
        );
        CREATE TABLE IF NOT EXISTS fetch_log (
            account_id TEXT,
            fetched_on TEXT,
            PRIMARY KEY (account_id, fetched_on)
        );
        CREATE TABLE IF NOT EXISTS month_fetch_log (
            account_id TEXT,
            month_key  TEXT,
            PRIMARY KEY (account_id, month_key)
        );
    """)
    conn.commit()
    return conn


def already_fetched_today(conn: sqlite3.Connection, account_id: str) -> bool:
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT 1 FROM fetch_log WHERE account_id = ? AND fetched_on = ?",
        (account_id, today),
    ).fetchone()
    return row is not None


def already_fetched_month(conn: sqlite3.Connection, account_id: str, month_key: str) -> bool:
    """Check if a past month (e.g. '2026-04') has already been fully fetched."""
    row = conn.execute(
        "SELECT 1 FROM month_fetch_log WHERE account_id = ? AND month_key = ?",
        (account_id, month_key),
    ).fetchone()
    return row is not None


def mark_month_fetched(conn: sqlite3.Connection, account_id: str, month_key: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO month_fetch_log VALUES (?, ?)",
        (account_id, month_key),
    )
    conn.commit()


def load_transactions(
    conn: sqlite3.Connection,
    account_id: str,
    date_from: date,
    date_to: date | None = None,
) -> list[dict]:
    if date_to is None:
        rows = conn.execute(
            "SELECT id, date, amount, description FROM transactions "
            "WHERE account_id = ? AND date >= ? ORDER BY date",
            (account_id, date_from.isoformat()),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, date, amount, description FROM transactions "
            "WHERE account_id = ? AND date >= ? AND date <= ? ORDER BY date",
            (account_id, date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def save_transactions(conn: sqlite3.Connection, account_id: str, transactions: list[dict]) -> None:
    today = date.today().isoformat()
    conn.executemany(
        "INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?, ?, ?)",
        [
            (t["id"], account_id, t["date"], t["amount"], t["description"], today)
            for t in transactions
        ],
    )
    conn.execute(
        "INSERT OR REPLACE INTO fetch_log VALUES (?, ?)",
        (account_id, today),
    )
    conn.commit()


def purge_old_entries(conn: sqlite3.Connection, keep_days: int = 180) -> None:
    cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
    conn.execute("DELETE FROM transactions WHERE date < ?", (cutoff,))
    conn.execute("DELETE FROM fetch_log WHERE fetched_on < ?", (cutoff,))
    conn.commit()
