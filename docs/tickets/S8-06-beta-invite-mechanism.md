Status: done

================================================================
TICKET S8-06 — Beta Invite Mechanism
================================================================

PRE-CHECK: before building anything, confirm the full
registration → verification round-trip genuinely works end to
end for a person who is neither Borys nor liyaberry27@gmail.com
— a real, fresh third-party test if possible, since that's the
actual proof S8-05's fix achieves what the sprint needs. If a
real third person isn't available, at minimum a genuinely fresh
address never previously touched by this project.

WHAT TO BUILD:
- A simple way for Borys to grant beta access to specific real
  people without opening registration to the general public —
  an invite-code system, an admin-granted allowlist, or
  equivalent (your call, justify the choice)
- Should be simple to operate manually (Borys adding a handful
  of people), not an over-engineered general-purpose invite
  system — this is for 10-20 people, not scale

ACCEPTANCE CRITERIA:
- Borys can grant access to a specific real email/person
  without public registration being open to everyone
- Tested with a real invite granted and used end-to-end
- Pre-check's fresh third-party registration confirmed working

WHEN DONE:
- Real evidence of the invite mechanism working end-to-end
- Pre-check registration proof
- Do not start S8-07 until confirmed

================================================================
WHEN DONE — answered 2026-08-28
================================================================

**Pre-check registration proof:** already closed via S8-05 — a real
fresh third party (`lifeliyaberry27@gmail.com`, distinct from
`liyaberry27@gmail.com`, the earlier SES-blocked address) completed a
real, first-time registration end-to-end through Resend. See
`docs/verification_debt.md`'s "Real received-email confirmation for
email verification" entry (CLOSED, S8-05) for the full record,
including the `users.email` case-sensitivity gap that pre-check
surfaced (flagged, not fixed, in S8-06's ARCHITECTURE.md write-up).

**Real evidence of the invite mechanism working end-to-end,** run live
against `https://mymble.be` via `aws ecs execute-command` (ECS Exec,
`kbc-analyzer-cluster` / `kbc-analyzer-web`, task
`7aed951d061d4dab9368ed4b43caa754`) and `curl` against the real API,
2026-08-28:

1. **Negative case — no invite, registration blocked:**
   `POST /api/auth/register` for `s8-06-negative-test@example.com`
   (confirmed via direct DB query to have no `users` or `beta_invites`
   row beforehand) returned `403 {"detail":"Mymble is currently
   invite-only. Ask for an invite if you don't have one yet."}`. No
   account created.

2. **Invite granted for real:** `python -m ops.grant_beta_invite
   money.borys.001@gmail.com` (confirmed clean beforehand — no
   existing `users` or `beta_invites` row) via ECS Exec, output:
   `Granted beta access to money.borys.001@gmail.com
   (invited_at=2026-08-28 18:18:04.016755+00:00)`.

3. **Invite used for real:** `POST /api/auth/register` for the same
   address returned `201 {"id":"09061412-ede8-4b23-89a7-28df1f55b4a1",
   "email":"money.borys.001@gmail.com","email_verified":false}` — a
   real `users` row created on the real production database.

4. **Consumption verified at the DB level:** direct query showed the
   `beta_invites` row for that email with `used_at=2026-08-28
   18:18:09.370353+00:00` and `used_by_user_id` equal to the exact
   user id from step 3 — the invite is tied to the specific account it
   gated, not just marked used in the abstract.

5. **One invite, one account — reuse blocked:** a second
   `POST /api/auth/register` for the same email with a different
   password returned `400 {"detail":"An account with that email
   already exists."}` — clean rejection via the existing-account path,
   no duplicate row, no second consumption of the same invite.

All five steps ran against the real production system with real HTTP
responses and real database state, not local/staging approximations.
Nothing deferred — no `docs/verification_debt.md` entry needed for
this ticket.

**Test account cleanup (same session):** the `money.borys.001@gmail.com`
`users` row created in step 3 was disposable test data, not a real
beta grant — deleted from production immediately after, same pattern
as the S7-05 test-account cleanup: `SELECT` before (`1` row) and after
(`0` rows) the `DELETE`, plus an independent re-confirmation against
the live API on a separate connection — `POST /api/auth/login` for
that address now returns `401 {"detail":"Invalid email or
password."}`. The corresponding `beta_invites` row is untouched
(`ON DELETE SET NULL` on `used_by_user_id`, per ARCHITECTURE.md) — it
still shows `used_at` set, so that email can't be re-registered
without a fresh invite grant. The `s8-06-negative-test@example.com`
address from step 1 never had a `users` row created (registration was
rejected before any account existed), so there was nothing to clean
up there.

**Unexpected during the build (flagged in KEY DECISIONS/commit
messages already, repeated here for visibility):** the production
image for this ticket was first built from `backend/Dockerfile`
(local-dev, no frontend build stage) instead of `Dockerfile.prod`,
which shipped a web container with no `static/` directory — a real
regression, root page 404ing in production, caught and fixed same-day
(`7a5c3f9`, `491d698`). Rebuilding surfaced a second, previously
latent gap: `backend/scripts/` is entirely `.dockerignore`-excluded,
so `grant_beta_invite.py` — this ticket's actual deliverable — would
never have existed inside a real production container even with the
right Dockerfile. Fixed by moving it to a new `backend/ops/`
directory that `Dockerfile.prod` does copy in.

Ready for S8-07 whenever you confirm this one.
