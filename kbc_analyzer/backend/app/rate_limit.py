"""Basic rate limiting (S5-07) — a ceiling before Sprint 6 exposes this app
publicly, not throttling normal single-user use. Applied only to the
endpoints that cost real money or hit a third-party API on every call:
POST /api/chat, POST /api/transactions/sync, POST /api/analysis/*.

In-memory storage (slowapi's default) — fine for now since `backend` runs
as one uvicorn process (no multi-worker fan-out), so there's only ever one
counter to keep. Keyed on remote address: this app is single-user and has
no concept of a caller identity yet, so IP is the only signal available.
Sprint 6 (real users, real deployment behind a real proxy) should key on
the authenticated user_id instead — IP-based limiting behind a shared
proxy/NAT would otherwise throttle unrelated users together — and probably
move storage to Redis (already in this stack) so limits survive a restart
and are shared correctly if `backend` ever runs with more than one worker.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Generous for a real single user, a real ceiling against a runaway client,
# a stuck retry loop, or (once Sprint 6 ships) casual abuse — not a limit
# anyone using the app normally should ever notice.
CHAT_RATE_LIMIT = "20/minute"
SYNC_RATE_LIMIT = "10/minute"
ANALYSIS_RATE_LIMIT = "10/minute"

# S6-04: deliberately tighter and IP-keyed on purpose, not user-keyed —
# these are the two endpoints most exposed to brute-force/enumeration, and
# the caller has no session yet at the moment they hit either one (that's
# the whole point of hitting them), so there's no user_id to key on even
# if this module already supported it. 5/minute is generous for a real
# person mistyping a password a couple of times, a real ceiling against a
# scripted guessing loop.
LOGIN_RATE_LIMIT = "5/minute"
REGISTER_RATE_LIMIT = "5/minute"
