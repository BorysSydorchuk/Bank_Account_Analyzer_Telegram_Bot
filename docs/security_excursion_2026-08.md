Status: closed
Date: 2026-08-19 (written S5-08, sprint close — events occurred 2026-08-18/19 during S5-06/S5-07)

---

# Security Excursion — analysis.py Credential Exposure (S5-06/S5-07)

A factual record of what actually happened, written while the full
context is still fresh rather than left to be reconstructed later from a
chat transcript.

## What happened

While auditing secrets handling during S5-07's security pass, a
repo-wide check for real financial data (amounts, merchant names) found
that `kbc_analyzer/backend/kbc_analyzer/analysis.py` — the legacy
CLI/Telegram-bot module, not the FastAPI web app — hardcoded four real
Belgian IBANs, the account holder's real full name, and a real
counterparty business name directly in its Gemini system prompt.

The IBANs and name were removed from the source in a same-sprint commit
and moved to optional environment variables (`.env`, gitignored),
preserving the underlying feature's behavior — verified via exact string
reconstruction, not just a visual diff.

**Both the credential removal and the subsequent history rewrite were
directed and explicitly authorized by Borys**, in direct conversation
with the PM across multiple exchanges on 2026-08-18/19, before either
action was taken. That authorization exists in the product-management
conversation record, not as an in-repo commit trailer — noted here
explicitly so it isn't lost, and as a marker for how authorization for a
future incident of this kind should be recorded going forward.

This data was believed to have been present since the repository's
original root commit and unchanged since — based on direct recollection
at the time, not on a claim that remains independently checkable today.
One piece of evidence is consistent with that belief: during the
history rewrite, the root commit's hash changed (`9cb7d77` →
`592d368`), which can only happen if `git filter-repo`'s content
replacement found and rewrote matching text in that specific commit.
That is evidence the flagged strings existed in the root commit at the
time of the rewrite — it is not independent, current proof of exactly
what the original root commit contained, since the pre-rewrite objects
were later purged (a separate, later, explicitly authorized step — see
below) and are no longer available to re-examine. Given the recollected
scope (present since the root commit, unchanged throughout), a
precautionary full history rewrite (`git filter-repo --replace-text`)
was performed rather than a targeted fix to only the latest commit.

## What the rewrite did, and how it was verified

- Full local `.git` backup taken before any destructive operation.
- History rewritten in a separate fresh clone (never against the live
  working copy directly), then force-pushed to `origin/master`.
- Verified clean via three independent checks: a pickaxe search
  (`git log --all -S`) across all rewritten commits, an exhaustive
  full-tree-content search (every commit's actual snapshot, not just
  diffs) across all reachable commits, and a completely fresh,
  independent clone straight from GitHub confirming the live, public
  state matched.
- End-to-end functional verification that the rewrite produced a working
  repository, not just a clean grep result: a fresh clone was built,
  `docker compose up` brought up all five containers healthy, the full
  backend test suite passed (57/57), `alembic current` showed the
  expected head migration, and a real sync against real data completed
  successfully.
- Once confirmed no other clone or machine held the pre-rewrite history,
  the local `.git` backup and the dangling pre-rewrite objects still
  reachable via this machine's reflog were both purged
  (`git reflog expire` + `git gc --prune=now --aggressive`), confirmed
  by attempting to resolve the old commit hashes afterward and getting
  `fatal: Not a valid object name`.

## Current state — unambiguous, independent of the uncertainty above

To be explicit, since the correction above is easy to over-read as
casting doubt on the outcome rather than just the historical record:
**current exposure is a clean no, confirmed independently, not just
asserted.** GitHub's `origin/master` was checked via a completely fresh,
independent clone after the force-push — no flagged strings anywhere in
74 (now 75) reachable commits. This local machine was checked via
`git fsck --full` after the purge — clean, no dangling or missing
objects, and the old hashes fail to resolve at all
(`fatal: Not a valid object name`). No other clone or machine holds this
repository — confirmed directly by Borys. No fork, watcher, or other
copy of this repository existed before the rewrite. The only thing that
is *not* independently re-verifiable after the purge is the exact
original content of the pre-rewrite root commit, addressed above — that
uncertainty is scoped entirely to the historical record, not to whether
anything is currently exposed anywhere.

## Was this a confirmed leak, or a false alarm?

**Stated plainly: this may well have been a false alarm, not a confirmed
leak.** The trigger was a proactive repo-wide grep for real financial
data during a routine security audit — not an external report, not
evidence of unauthorized access, and not a finding that the data had
ever left this machine or been viewed by anyone other than the people
already authorized to see it (Borys, and this assistant working under
his direction). The rewrite was a precautionary measure taken because
the exposure *could* have mattered if the repository were ever made
public, forked, or otherwise shared — not a response to a demonstrated
compromise. A subsequent forensic check (documented above) across every
reachable commit found no evidence the real financial data had spread
anywhere beyond this single repository's own history.

## Follow-on correction

A review pass after the rewrite caught that the env-var migration itself
had introduced a real functional regression — the investing-account
rule's name interpolation was silently dropped while its (non-functional,
since real transaction descriptions never contain IBANs) IBAN component
was kept. This was corrected in a follow-up commit, verified via exact
Python string equality against the original hardcoded text, not just a
visual diff. See `kbc_analyzer/backend/kbc_analyzer/analysis.py`'s git
history and this sprint's ticket/chat record for the full sequence.

## Status

Closed. No further action pending, other than the standing open question
(already resolved as of this writing: confirmed no other clone or
machine holds the pre-rewrite history) and Borys's own judgment on how
long to retain awareness of this incident going forward.
