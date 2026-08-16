Status: confirmed
Source: sprint4_tickets_v2.txt (revised set)
Shipped as: c3d6b69 — feat: S4-04 document insight persistence decision (Option B)

---

================================================================
TICKET S4-04 — Insight Persistence Semantics Decision  (NEW,
                 must precede the comparison feature)
================================================================

BACKGROUND (from the supervision report):
The insights table delete-and-replaces on re-sync of the
same date range. The period-comparison feature (S4-08)
builds on this table. As-is, "history" means "whatever the
latest sync generated," not a record over time — comparing
June vs July after re-syncing June compares fresh June
insights, silently. This must be a deliberate design
decision made BEFORE the comparison feature is built.

WHAT TO BUILD:

Part 1 — Present the decision (do this first, wait for
Borys's answer before implementing):

  Option A — Snapshot semantics: never delete; add a
  generation_number; comparison uses the latest generation
  per range; history of regenerations is queryable later.
  Cost: table grows; needs "latest per range" queries.

  Option B — Current semantics, documented: keep
  delete-and-replace; the comparison feature compares
  STATISTICS (always computed live from transactions —
  deterministic and correct regardless of insight
  regeneration) and shows stored insights as supplementary
  context with a "generated <date>" label.
  Cost: no true insight history until a later sprint.

  PM RECOMMENDATION: Option B. The comparison feature's
  numeric core (statistics deltas) never depended on the
  insights table — statistics are recomputed live. Option
  A builds infrastructure for an insight-history feature
  nobody has asked for yet. Option B ships the comparison
  correctly now and leaves snapshots as a clean future
  addition.

Part 2 — Implement whichever option Borys picks:
  Option A: migration adding generation_number, remove
  the delete, update queries to latest-generation.
  Option B: add generated_at display to the insights
  panel + comparison view; add a code comment at the
  delete site documenting the semantics deliberately;
  update ARCHITECTURE.md Invariants.

ACCEPTANCE CRITERIA:
- Decision presented with tradeoffs, Borys's choice
  recorded before implementation
- Implementation matches the chosen option
- ARCHITECTURE.md updated in the same commit

WHEN DONE:
- State which option was chosen and show the
  implementation
- Explain: why must this decision precede the
  comparison feature rather than follow it?
- Do not start S4-05 until confirmed
