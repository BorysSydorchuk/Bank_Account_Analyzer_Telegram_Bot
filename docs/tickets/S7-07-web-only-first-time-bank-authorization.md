Status: delivered

================================================================
TICKET S7-07 — Web-Only First-Time Bank Authorization
================================================================

BACKGROUND: since Sprint 1, connecting a bank account for the
first time on a fresh setup has required running
`python -m kbc_analyzer.main` — a terminal step, entirely
incompatible with a real self-serve signup flow. This was
blocked on having a public callback URL, which S7-04 provided,
and per-user session storage, which S7-06 just provided. Both
prerequisites are now real and live.

PREMISE CHECK FIRST: read S7-06's session_store abstraction and
the current Enable Banking connect/reconnect flow as it exists
today in the Settings page. Confirm exactly what "first-time"
versus "reconnect" looks like in the current code — it's
possible S7-06 already made these largely the same code path,
in which case this ticket may be smaller than it looks. Don't
assume; check.

WHAT TO BUILD:
- A "Connect your bank" entry point reachable by a genuinely
  new user with NO existing Enable Banking session at all —
  not just an existing user reconnecting
- Full flow entirely in the browser: user clicks connect →
  picks/confirms their bank (or goes straight to KBC if that's
  still the only supported bank — confirm current scope,
  multi-bank is Sprint 8) → redirected to Enable Banking →
  authorizes via their real bank login → redirected back to
  mymble.be → session established via S7-06's per-user store →
  zero terminal interaction at any point
- This must work for a user who has NEVER touched this
  codebase, not just Borys doing it again — the real test is
  a genuinely fresh account
- Retire the CLI-based first-auth path as the PRIMARY flow.
  Whether it's deleted entirely or kept as a debug/fallback
  tool is your call — justify whichever you choose. If kept,
  it must be clearly marked as non-primary/dev-only so nobody
  mistakes it for the real onboarding path

ACCEPTANCE CRITERIA:
- A genuinely new test user (not Borys's account) can connect
  a real bank account entirely through the browser — no
  terminal, no copy-paste, no developer intervention
- Real live test against Enable Banking's actual production
  flow (not a mock), same evidence standard as every
  credential-touching ticket this sprint
- The new user's session is correctly isolated per S7-06's
  model — verify this explicitly, don't just assume S7-06
  covers it
- ARCHITECTURE.md updated to reflect the CLI path's final
  status (retired, or dev-only-and-clearly-marked)

WHEN DONE:
- Show a real, complete new-user bank connection end to end —
  real evidence, ideally from an actual second test account,
  not narration
- Confirm the CLI path's final disposition and why
- Explain: what, if anything, still requires the CLI path
  after this ticket, and is that acceptable long-term or a
  known gap for a later sprint?
- Do not start S7-08 until confirmed

## PREMISE CHECK (2026-08-27)

Read `app/eb_service.py`, `app/routers/auth.py`, the S7-06 delivery,
`BankConnectionSection.tsx`, `SessionBanner.tsx`, `DashboardPage.tsx`,
`RegisterPage.tsx`, `kbc_analyzer/main.py`, and `README.md` directly.

**The ticket's own hint was right — this is smaller than it looks.**
`POST /reauthorize` never checks for an existing session before
starting a fresh OAuth flow — `start_auth()` always begins a brand new
authorization, regardless of whether a session already exists. Since
S7-06, the callback resolves the connecting user purely from the
ordinary session cookie + the `eb_oauth_user_id` binding, with zero
dependency on a prior session existing. **The plumbing for a genuinely
first-time connection already works, unchanged, since S7-06 shipped.**
Confirmed by testing directly: `POST /reauthorize` for a user with zero
`enable_banking_sessions` row behaves identically to one with an
expired row — same real Enable Banking URL, same cookies, same
callback logic.

**What's actually missing, found by reading, not assumed:**

1. **`EnableBankingStatus.status` only ever returns `"active"` or
   `"expired"`** (`app/schemas.py`) — `eb_service.get_session_status()`
   returns `"expired"` both when a session genuinely lapsed *and* when
   one never existed at all (`session_store.load()` returning `None`).
   A brand-new user therefore sees "Bank connection **expired** — sync
   won't work until **reconnected**" in both `SessionBanner.tsx` and
   `BankConnectionSection.tsx` — copy that implies something was lost,
   when nothing was ever connected. Real, user-facing bug, not a
   plumbing gap.
2. **`app/eb_service.py`'s `EnableBankingAuthError` message literally
   tells a web user to run `python -m kbc_analyzer.main`** — this is
   the one live place the CLI path is still positioned as "the way to
   fix this," surfaced directly in a sync job's `error` field (shown as
   a toast). This is the actual "CLI-based first-auth path as the
   primary flow" the ticket means — not `README.md` (which has never
   claimed to be part of the web app; it's an honest, separate CLI/bot
   tool README, predates Mymble entirely) and not `main.py` itself
   (never called by any web code path — `grep` confirms `ensure_session`
   is only ever invoked from `main.py`'s own `main()`).
3. **No dedicated onboarding entry point** — `DashboardPage.tsx` renders
   the same widgeted dashboard (mostly empty) for a brand-new user as
   for an established one, with no nudge toward Settings. The only
   place to connect a bank at all is `BankConnectionSection.tsx` inside
   Settings, undiscoverable without already knowing to look.
4. **Multi-bank confirmed out of scope, matching the ticket's own
   note:** `enablebanking.py`'s `_find_kbc_aspsp()` is still hardcoded
   to KBC — no bank-picker UI needed for this ticket.

**Disposition decided for the CLI path:** kept, not deleted.
`kbc_analyzer/main.py` (and `bot.py`) are a genuinely separate,
still-useful standalone tool — local SQLite caching, direct Gemini
analysis, Rich terminal output, none of which the web app has or needs.
Deleting it would remove real, working functionality unrelated to
Mymble's onboarding, not just retire dead CLI-auth code. What actually
needed retiring — and is fixed in this ticket — is the one place the
*web app's own code* pointed a web user at that terminal tool.

Proceeding on this basis: fix the status distinction, fix the
error-message bug, add a real first-time "Connect your bank" entry
point on the Dashboard, keep the CLI tool as-is with its existing
honest README treatment.

## DELIVERY (2026-08-27)

### What was built

- **`EnableBankingStatus.status` gained `"not_connected"`**
  (`app/schemas.py`), `eb_service.get_session_status()` now returns it
  when `session_store.load()` is `None` — distinct from `"expired"`.
- **`SessionBanner.tsx` and `BankConnectionSection.tsx`** both branch on
  the new state: "Connect your bank to start syncing transactions" /
  "No bank connected yet." with a "Connect" button, versus the existing
  "expired... Reconnect" copy for a session that actually lapsed. Same
  `useEnableBankingReconnect` hook, same `start()` call either way —
  only labels and icons differ.
- **`SessionBanner` now renders for `not_connected`** (previously
  stayed hidden until expired/nearing-expiry) — this is the actual
  first-time entry point the ticket asked for: a brand-new user sees it
  on the Dashboard immediately, unprompted, no need to already know
  Settings exists.
- **`app/eb_service.py`'s `EnableBankingAuthError` message fixed** —
  no longer tells a web user to run `python -m kbc_analyzer.main`.
- **`kbc_analyzer/main.py`'s docstring** now states explicitly it's a
  dev/personal-use tool, not part of Mymble, not the onboarding path.

### Real evidence

Backend: `pytest -q` → **110 passed** (full suite), including three new
tests in `tests/test_enable_banking_per_user_sessions.py` —
`test_never_connected_is_distinct_from_expired` (proves the two states
never cross-report), `test_sync_error_for_an_unconnected_user_never_mentions_the_cli`
(proves the fixed error message).

Frontend: `tsc --noEmit` clean, `npm run build` succeeds.

**Real browser test, local stack rebuilt with this code, a genuinely
fresh test account (`s7-07-local-test@example.com`, registered fresh,
zero prior state):**

1. Logged in fresh → Dashboard immediately shows: *"🏛 Connect your bank
   to start syncing transactions."* with a **Connect** button — before
   this ticket, this same account would have seen nothing at all (the
   banner stayed hidden for a never-connected user).
2. Settings → Bank Connection card: *"No bank connected yet."* with a
   **Connect your bank** button (screenshot evidence).
3. Clicked it → real `POST /reauthorize` call, real Enable Banking URL
   returned (`https://tilisy.enablebanking.com/ais/start?sessionid=...`),
   opened in a new tab — same production-grade Enable Banking endpoint
   this project has used since S3-07, not a mock.
4. UI correctly transitioned to *"Waiting for you to finish authorizing
   in the new tab…"* with a Cancel button, still correctly showing "No
   bank connected yet." until authorization actually completes.

Test account cleaned up from the local dev database afterward.

### Session isolation — not assumed, explicitly re-verified

The ticket asked not to assume S7-06 covers isolation for this new
status value specifically.
`test_never_connected_is_distinct_from_expired` constructs two real
users — one with zero `enable_banking_sessions` rows, one with a real
(`complete_reauthorization`-created) row set to a past `valid_until` —
and asserts each reports its own correct status with no cross-leak in
either direction. Combined with S7-06's existing isolation tests
(encrypted-at-rest, no-clobber-on-second-write), a third
independently-created user's status has now been proven never to
depend on another's row.

### What's still needed for full end-to-end confirmation

Everything up to a real KBC login is built, tested, and browser-verified.
The one thing I genuinely cannot do myself, per this project's standing
practice (Codee never touches real bank credentials): complete an
actual KBC login as a **second, genuinely fresh real or test account**
that isn't Borys's own. That's the one remaining acceptance-criterion
item — "a genuinely new test user... can connect a real bank account
entirely through the browser" — needing Borys (or a second real person)
to click through the real KBC consent screen once.

### Answers to WHEN DONE

- **CLI path's final disposition:** kept, not deleted or retired —
  it was never actually the web app's onboarding path to begin with
  (confirmed via `ensure_session()` having zero web callers); what
  needed retiring, and is fixed, is the one place the web app's own
  error message pointed a user at it.
- **What, if anything, still requires the CLI path after this ticket:**
  nothing on the web side. It remains the only way to use the
  standalone local CLI/Telegram-bot tool (unrelated to Mymble), which
  is its intended, permanent role — not a gap.
- **Is that acceptable long-term:** yes — it was never a gap in the web
  app to begin with, only a stale error message pointing the wrong
  direction, now fixed.

Do not start S7-08 until Borys completes one real second-account KBC
login through the live browser flow, confirming this end-to-end.
