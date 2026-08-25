# Backlog

Items flagged as out-of-scope during a ticket, worth doing, but not yet
attached to a sprint ticket. Existing to stop items like the one below
from being re-flagged every time someone happens to touch the same file,
without ever actually getting scheduled. When an item here gets turned
into a real ticket, remove it from this file — `docs/tickets/` becomes
its record from that point on.

## Sprint 8

### Rate limiting: move to Redis, key on `user_id`

`rate_limit.py` uses slowapi's default in-memory storage, keyed by
remote IP address. Fine while `backend` runs as a single uvicorn
process, but two real problems once real users exist: (1) IP-keyed
limiting behind a shared proxy/NAT throttles unrelated users together,
and (2) in-memory storage doesn't survive a restart and isn't shared if
`backend` ever runs with more than one worker (S7's ECS deployment can
scale to multiple tasks).

Fix: a custom slowapi `key_func` that derives the authenticated
`user_id` (`key_func` only receives the raw `Request`, so this means
either duplicating `get_current_user`'s session-cookie lookup outside
it, or a custom function that reads the same cookie directly), storage
backend switched to Redis (already in the stack for session/sync_lock/
job_store).

`/login`/`/register` should very likely stay IP-keyed regardless — a
brute-force attempt against those endpoints has no user identity yet.

**Flagged three times without becoming a ticket:** S5-07 (introduced
the gap, noted for later), S6-06 (full query-scoping ticket — flagged
as out of that ticket's named scope), S7-03 (RDS/Redis migration ticket
— flagged again when its Part 4 assumed rate_limit was already
Redis-backed and it wasn't). Logged here now so a fourth rediscovery
turns into "already backlogged" rather than "flagged again."
