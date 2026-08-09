"""S4-01: one-time cleanup for the 78 duplicate transaction pairs created by
Enable Banking issuing a new account_id on every reconnect (see migration
827da7c749b8's docstring for the root cause).

For each external_id that appears more than once, keeps the row with
manually_edited = TRUE if one exists, otherwise the row with the most recent
fetched_at, and deletes the rest. Every deleted row is logged in full to
dedup_deleted_log.json before anything is removed, so a mistake here is
recoverable from the log rather than gone.

Usage (run from /backend, same convention as the other scripts/ modules):
    python -m scripts.deduplicate            # dry run — writes the log, deletes nothing
    python -m scripts.deduplicate --execute  # deletes the rows logged by the dry run

Run the dry run first, read dedup_deleted_log.json, confirm it looks right,
then run --execute. The log is overwritten on both runs, but only --execute
actually touches the transactions table.
"""
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Transaction

LOG_PATH = Path(__file__).parent / "dedup_deleted_log.json"


def _json_default(value):
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Not JSON serializable: {value!r}")


def _row_snapshot(t: Transaction) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "external_id": t.external_id,
        "booking_date": t.booking_date,
        "amount": t.amount,
        "description": t.description,
        "category": t.category,
        "manually_edited": t.manually_edited,
        "fetched_at": t.fetched_at,
    }


def _choose_keeper(rows: list[Transaction]) -> Transaction:
    """manually_edited wins outright — a human decision on a duplicate row
    must never be the copy that gets thrown away. Among rows tied on that (all
    edited, or none), the most recently fetched one wins, since a later fetch
    reflects Enable Banking's most current view of the transaction."""
    edited = [t for t in rows if t.manually_edited]
    candidates = edited if edited else rows
    return max(candidates, key=lambda t: t.fetched_at)


def find_duplicate_groups(db) -> list[list[Transaction]]:
    all_rows = list(db.execute(select(Transaction)).scalars())
    by_external_id: dict[str, list[Transaction]] = defaultdict(list)
    for row in all_rows:
        by_external_id[row.external_id].append(row)
    return [rows for rows in by_external_id.values() if len(rows) > 1]


def main() -> None:
    execute = "--execute" in sys.argv

    db = SessionLocal()
    try:
        groups = find_duplicate_groups(db)

        deleted_log = []
        kept_for_manually_edited = 0
        total_deleted = 0

        for rows in groups:
            keeper = _choose_keeper(rows)
            if keeper.manually_edited:
                kept_for_manually_edited += 1
            losers = [t for t in rows if t.id != keeper.id]

            deleted_log.append(
                {
                    "external_id": keeper.external_id,
                    "kept": _row_snapshot(keeper),
                    "deleted": [_row_snapshot(t) for t in losers],
                }
            )
            total_deleted += len(losers)

            if execute:
                for loser in losers:
                    db.delete(loser)

        LOG_PATH.write_text(json.dumps(deleted_log, indent=2, default=_json_default))

        if execute:
            db.commit()

        print(f"{'EXECUTED' if execute else 'DRY RUN'} — log written to {LOG_PATH}")
        print(f"  Duplicate pairs found:        {len(groups)}")
        print(f"  Rows {'deleted' if execute else 'that would be deleted'}:        {total_deleted}")
        print(f"  Kept due to manually_edited:  {kept_for_manually_edited}")
        if not execute:
            print("\nReview the log above, then re-run with --execute to actually delete these rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
