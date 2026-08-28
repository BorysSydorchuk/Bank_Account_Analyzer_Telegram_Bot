Status: done, pending PM confirmation

================================================================
TICKET S8-08 — Sprint 8 Close
================================================================

WHAT TO BUILD:
No new features. Full production verification and
documentation accuracy, same discipline as every prior sprint
close — this one closes the sprint that made real multi-bank
support and real beta access genuinely possible for the first
time.

ITEMS:

1. Full regression sweep against production, with BOTH banks
   and the full beta-access path:
   - KBC connection/sync/categorization/insights
   - ING connection/sync/categorization/insights
   - Registration gated by invite (both register and Google
     sign-in paths)
   - Email verification, password reset
   - Feedback channel
   - Usage guardrails (confirm caps still enforce correctly)
   - Chat, budgets, categories, manual editing — the full
     Sprint 1-7 surface, unchanged by this sprint but worth
     confirming nothing regressed

2. ARCHITECTURE.md full accuracy pass:
   - Multi-bank model (composite-key sessions, bank picker)
   - Usage guardrails
   - Beta invite gating
   - Resend email infrastructure (replacing SES references
     that are now historical, not current)
   - Public route enumeration, current as of this sprint

3. Security spot-check:
   - Confirm the invite-gating can't be bypassed (direct API
     call attempting registration without a valid invite)
   - Confirm usage caps hold under the same real-evidence
     standard as S8-04's original test
   - Re-confirm S6-07's original IDOR sweep still holds with
     two banks' worth of data now in the system

4. Ledger final state:
   - Zero stale entries
   - The users.email case-sensitivity bug (S8-06) — still
     genuinely deferred, re-dated if unchanged, or closed if
     someone picked it up
   - Confirm no entry was silently dropped the way the SES
     entry almost was in S8-05 — a full read-through, not a
     grep for keywords

5. Sprint 8 backlog sweep:
   - Confirm every ticket's real scope (including the S8-05
     insertion and renumbering) is accounted for
   - Carry forward explicitly: any beta users actually
     recruited and invited by this point, or note that this
     remains open and needs Borys's attention before Sprint 9

ACCEPTANCE CRITERIA:
- Full production regression passes, both banks, real evidence
  throughout
- ARCHITECTURE.md accurate
- Security spot-check passes
- Ledger current, full read-through confirmed (not just grep)
- No console errors on any page
- Sprint 8 complete pending PM confirmation

WHEN DONE:
- Production regression results, per surface, both banks
- ARCHITECTURE.md accuracy confirmation
- Security spot-check results
- Ledger state, explicitly confirmed via full read-through
- Beta user recruitment status — how many real people have
  actually been invited so far, if any
- Sprint 8 complete pending PM confirmation

================================================================
WHEN DONE — answered 2026-08-29
================================================================

**Pre-check found before any of the below: S8-07 was never actually
deployed.** Production was still running the `491d698` image (S8-06's
deploy-fix commit) — no Feedback nav item, sidebar still said "KBC
Analyzer." Every commit from `bec958c` through `1c3a445` had been
pushed to git but never built/deployed. Built both images from
`Dockerfile.prod` (verified locally against a real running container
before pushing, learning from S8-06's wrong-Dockerfile incident),
pushed to ECR as `1c3a445`, and applied via a `-target`-scoped
`terraform apply` (full `terraform plan` hit unrelated permission
errors touching budgets/IAM/SES resources this deploy shouldn't have
touched anyway — scoped to exactly `aws_ecs_task_definition.web`,
`aws_ecs_service.web`, `aws_ecs_task_definition.worker`,
`aws_ecs_service.worker`). Both deployments reached `rolloutState:
COMPLETED`. Everything below was tested against this now-current
deployment, not the stale one.

**1. Production regression, both banks, real evidence:**

- **KBC + ING connection/sync/categorization/insights:** real sync run
  against `boris.sydorchuk@gmail.com`'s live account, which holds both
  a real KBC and a real ING connection simultaneously. Real job
  completed (`status: "complete"`), 425 real transactions stored,
  3 newly categorized, 5 real Gemini insights generated. Confirmed via
  direct database query that both institutions genuinely contributed:
  8 distinct real account UIDs (2 known KBC, 6 previously-unseen —
  see the ledger note below), 425 distinct `external_id` values across
  425 rows — zero collisions across a real mixed-institution dataset.
  This closes a real, previously-OPEN ledger item (ING transaction
  data had reported zero accounts through S8-02/S8-03) — full account
  in `docs/verification_debt.md`'s newly-CLOSED entry.
- **Registration gated by invite, both paths:** direct API attempt
  with no invite → real `403 {"detail":"Mymble is currently
  invite-only..."}`. Google sign-in's invite gate is covered by
  `test_new_google_sign_in_without_an_invite_is_rejected` in the
  passing suite (145/145) — a live click-through isn't possible from
  this environment (no real Google account to use), same boundary as
  every other real-credential limitation this sprint.
- **Email verification, password reset:** both endpoints respond
  correctly on the redeployed production (confirmed via a real
  `POST /api/auth/request-password-reset` call). Did not attempt a
  live password change on a real account — genuinely destructive on
  someone's real credentials without a concrete reason to, and both
  flows were already closed with full real-evidence proof in S7-09/
  S8-05 (real email received, real click-through, real login with the
  new password) on code that hasn't changed since.
- **Feedback channel:** sent a real message through the actual
  deployed production UI (not local dev, unlike S8-07's own test) —
  clean success toast, `204` in the backend's own log, no exception.
  Borys confirmed receiving it.
- **Usage guardrails:** seeded a disposable test account to exactly
  50 `usage_events` rows (S8-04's own real-evidence standard), then
  hit the 51st chat request live: `429 {"detail":"You've reached
  today's beta limit for chat messages (50/day). Try again
  tomorrow."}` — exact match. Test account deleted afterward
  (SELECT-before/DELETE/SELECT-after/independent-recheck pattern).
- **Chat, budgets, categories, manual editing:** real chat message
  sent and answered with real grounded numbers; transaction category
  edit UI opened correctly (cancelled without persisting, to avoid
  touching Borys's real categorization data unnecessarily); Settings'
  Bank Connection, AI Provider, and Categories sections all render
  real data correctly. No regressions found.

**No console errors on any page** — checked Dashboard, Chat (after a
real message), Transactions (after opening the edit UI), Settings,
and Feedback (after a real send), all against the live redeployed
production. Zero errors on every page.

**2. ARCHITECTURE.md accuracy pass:**

- **Multi-bank model:** accurate as written, plus one real stale claim
  found and fixed — the "ING has zero linked accounts" note (S8-01/
  S8-02 section and the Invariants section) no longer matches reality;
  both updated with the real S8-08 evidence above.
- **Usage guardrails:** accurate, matches the real 50/day re-test
  above exactly.
- **Beta invite gating:** accurate, unchanged this sprint.
- **Resend/SES:** already correctly framed as historical — SES
  mentions are all past-tense ("switched S8-05 after...", "SES-era"),
  `infra/ses.tf`'s own section already states plainly it's no longer
  the live path. No fix needed.
- **Public route enumeration:** didn't exist — added as a new section
  (compiled by reading every router's actual dependencies, not
  inferred), classifying every route as public / `get_current_user` /
  `require_verified_email`.

**3. Security spot-check:**

- **Invite bypass:** direct `POST /api/auth/register` with no invite
  on production → real `403`, no account created. Cannot be
  bypassed by calling the API directly.
- **Usage caps:** see above — real `429` at exactly the documented
  boundary, real message.
- **IDOR re-sweep with two banks' real data:** created a second real
  user's session, confirmed their own transactions list is correctly
  scoped, then attempted to modify a transaction id known to belong to
  `boris.sydorchuk@gmail.com` → real `404 {"detail":"Transaction not
  found."}` — `crud.update_transaction`'s S6-06 ownership scoping
  holds with real two-bank data now in the system, not just
  structurally.

**4. Ledger final state, full read-through (not grep):**

Read every entry in `docs/verification_debt.md` top to bottom, OPEN
and CLOSED. Found one real, closeable item (the ING entry above) and
moved it to CLOSED with full evidence. Every remaining OPEN entry
re-confirmed and re-dated to 2026-08-29: Enable Banking's stale app
name (still needs Borys's portal login), `users.email` case
sensitivity (still unpicked-up, non-blocking), AWS credit balance
(still needs Borys's Billing Console check), `GOOGLE_CLIENT_SECRET`
rotation (still needs Borys's Console confirmation), date-range
regression tests / sync-lock release / frontend test harness (all
still Tester-agent scope, unchanged), single NAT Gateway (3 days into
the 4-week stability bar, not yet). Nothing was silently dropped —
every entry that existed before this pass still exists after it,
either re-dated OPEN or newly CLOSED with a reason.

**5. Sprint 8 backlog sweep:**

All 8 tickets (S8-01 through S8-08, including the S8-05 insertion and
the resulting renumbering) accounted for. Found and fixed two stale
`Status:` headers that never got updated despite the real work being
done and confirmed elsewhere: **S8-02** (said `in-progress`, actually
completed with real evidence 2026-08-27 — its own named caveat, real
ING data, closed today) and **S8-07** (said `in-progress`, now `done`
— Borys confirmed real feedback-email receipt this session).

**Beta user recruitment status: zero real, external beta users
recruited so far.** Checked directly: production's `beta_invites`
table has exactly 2 rows total — both from this sprint's own testing
(S8-06's pre-check, S8-07's onboarding walkthrough), not real
recruited people. Every "beta tester" who has touched this app so far
is Borys himself or a disposable test account created and deleted in
the course of building/verifying it. **This is a real open item that
needs Borys's attention before Sprint 9** — the mechanism works
end-to-end, but nobody outside this project has actually been invited
yet.

**Sprint 8 complete pending PM confirmation.**

================================================================
ADDENDUM — 2026-08-29, post-close
================================================================

Borys's own real fresh-third-party-registration test (exactly the
kind of check this ticket's regression sweep couldn't fully replace)
found a real, severe bug this close missed: categorization was
completely non-functional for every account except the original
bootstrap one, because nothing ever seeded a new user's `categories`
table. Investigated and fixed as its own ticket,
`docs/tickets/S8-09-fix-missing-category-seeding.md` — not folded in
here, since this file's own write-up above is already the historical
record of what S8-08 itself actually covered and found. Left as a
pointer, not a rewrite, per this ledger's own convention for how
CLOSED entries preserve history.
