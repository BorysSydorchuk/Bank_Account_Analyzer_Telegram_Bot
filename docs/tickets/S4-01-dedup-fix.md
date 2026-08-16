Status: confirmed
Source: sprint4_tickets.txt (original)
Shipped as: 3947afe — fix: S4-01 duplicate transaction dedup fix

---

================================================================
TICKET S4-01 — Duplicate Transaction Dedup Fix
================================================================

PRIORITY: Must be first. All statistics, insights, and
category totals are currently inflated by duplicate rows.
Nothing else in Sprint 4 builds on trustworthy data until
this is fixed.

BACKGROUND:
Enable Banking issues a new internal account_id on every
reconnect. Since dedup is keyed on (account_id, external_id),
the same physical transaction gets re-inserted under the new
account_id on every reconnect. 78 duplicate pairs currently
exist across 4 different account_ids for what is physically
one KBC account.

WHAT TO BUILD:

Part 1 — Fix the dedup key going forward:
Change the UNIQUE constraint from:
  UNIQUE (account_id, external_id)
to:
  UNIQUE (external_id)

external_id is Enable Banking's own transaction reference,
guaranteed unique per transaction across the bank — not just
within one account session. Removing account_id from the
constraint means reconnects can never re-insert the same
transaction regardless of what account_id Enable Banking
assigns.

New Alembic migration:
  -- Drop old constraint
  ALTER TABLE transactions
  DROP CONSTRAINT transactions_account_id_external_id_key;

  -- Add new constraint
  ALTER TABLE transactions
  ADD CONSTRAINT transactions_external_id_key UNIQUE (external_id);

Part 2 — Clean up existing 78 duplicate pairs:
Write a one-time migration script (not a migration file —
a standalone Python script at scripts/deduplicate.py) that:

1. Finds all duplicate external_ids (same external_id,
   different account_id rows)
2. For each duplicate pair, keeps the row that has
   manually_edited = TRUE if one exists, otherwise keeps
   the row with the most recent fetched_at
3. Before deleting, logs every deleted row to a file
   (scripts/dedup_deleted_log.json) so nothing is
   permanently lost without a record
4. Deletes the duplicate rows
5. Reports: how many pairs found, how many deleted,
   how many kept due to manually_edited = TRUE

Run the script manually (not automatically) — Borys confirms
the log looks right before deletions are final. Show the
log before deletion and after.

Part 3 — Update the sync upsert logic:
The existing upsert in crud.py uses
ON CONFLICT (account_id, external_id) — update this to
ON CONFLICT (external_id) to match the new constraint.

ACCEPTANCE CRITERIA:
- Migration runs cleanly, new unique constraint in place
- deduplicate.py runs and produces the log file
- After running the script: SELECT count(*) from transactions
  returns the deduplicated count (should be ~329 - 78 = ~251
  unique transactions)
- Running POST /api/transactions/sync after dedup does not
  re-insert any previously-seen transactions
- Manually edited rows are preserved, not deleted
- Statistics and category totals reflect deduplicated data

WHEN DONE:
- Show the dedup log (how many pairs, which were kept)
- Show transaction count before and after
- Show that a re-sync does not re-insert duplicates
- Explain: why external_id alone is safe as a global
  unique key, not just within one account?
- Do not start S4-02 until confirmed
