Status: delivered

================================================================
TICKET S7-03 — RDS & Redis Provisioning + Real Data Migration
================================================================

PRIORITY: This is the ticket that moves your actual real bank
data onto AWS infrastructure for the first time. Same care
standard as S4-01's dedup cleanup — log before you act, verify
counts match exactly, and per S7-01/S7-02's review history,
EVERY claim below needs real committed evidence, not prose
describing that something was done.

WHAT TO BUILD:

Part 1 — Provision:
- RDS PostgreSQL instance (per S7-01's architecture: private
  subnet, smallest reasonable instance size — db.t4g.micro
  or equivalent, single-AZ, no read replicas)
- Security group restricting access to ONLY the Fargate web
  and worker services' security group — never 0.0.0.0/0,
  never a broader CIDR than necessary
- The self-hosted Redis container decision from S7-01 (own
  Fargate service, or co-located appropriately — confirm
  your exact placement and justify it here if not already
  settled in S7-01)
- Redis security group, same restrictive principle as RDS

Part 2 — Prove the migration chain works on a genuinely
fresh target:
- Run the FULL Alembic migration chain against the new RDS
  instance from scratch (empty database → head). This is the
  first time the entire migration history — every migration
  since S2-01's baseline — gets tested against a target that
  isn't the local dev DB's incrementally-evolved history.
  If anything in that chain doesn't apply cleanly to a truly
  fresh database, that's a real finding, not a blocker to
  work around silently.

Part 3 — Migrate real data:
- Dump your real local dev Postgres data
- Restore into RDS
- Verify row counts match EXACTLY, per table, before vs after
  (same discipline as S4-01: log what you're about to do,
  do it, verify, show the real numbers)
- Confirm the encrypted settings (API keys, Fernet-encrypted)
  decrypt correctly after migration — this crossed environments,
  don't assume the SETTINGS_SECRET/encryption round-trip
  survived untested

Part 4 — Confirm Redis-dependent features work against the
new instance:
- Session storage (S6-01)
- sync_lock (S5-05)
- rate_limit (S5-07)
- job_store (background job state)
All of these currently point at local Redis — confirm they
work correctly against the new AWS-hosted Redis, not just
that the container runs.

ACCEPTANCE CRITERIA:
- RDS and Redis provisioned via S7-01's Terraform approach,
  in private subnets, restrictive security groups
- Full migration chain applies cleanly to fresh RDS — real
  `alembic history`/`alembic current` output committed as
  evidence, not a description
- Real data migrated, row counts verified exactly matching
  source, per table — real query output committed, both
  before and after
- A real API key confirmed decrypting correctly post-migration
  — real evidence, not "should work"
- Session/lock/rate-limit/job-store all confirmed working
  against the new Redis — real test output, not assertion
- Local dev stack still works completely untouched — RDS is
  a new target, not a replacement for local dev
- Security groups verified restrictive — real
  `aws ec2 describe-security-groups` output committed showing
  the actual rules, not a description of intended rules
- ARCHITECTURE.md updated with the real RDS/Redis endpoints
  (or their ARNs/identifiers — not literal connection strings
  with credentials)

WHEN DONE — every item below needs REAL committed evidence,
per S7-01/S7-02's established standard, not narration:
- Real migration chain output against fresh RDS
- Real before/after row counts, per table
- Real confirmation of API key decryption post-migration
- Real confirmation of all four Redis-dependent features
  working against AWS Redis
- Real security group rules as committed evidence
- Do not start S7-04 until confirmed

## DELIVERY (2026-08-25)

### Placement decision: Redis as its own Fargate service

Not co-located with web/worker — its own ECS service (`kbc-analyzer-redis`),
own task, no ALB. A web/worker deploy/restart can never take Redis down
with it, and vice versa. Reachable via AWS Cloud Map private DNS
(`redis.kbc-analyzer.internal`), not a raw task IP — IPs change on every
task replacement, a stable name doesn't. No persistent volume: all three
Redis-dependent features are explicitly transient/restart-tolerant by
design (see their own docstrings), same as local dev's `redis:7-alpine`
container, which also has no volume.

### Connectivity note (why this ticket ran the way it did)

RDS and Redis sit in private subnets with **no route from outside AWS at
all** — a security group rule can't fix that, only a route table can,
and private subnets only route outbound via NAT. Every command below ran
from *inside* the VPC, via a temporary `kbc-analyzer-migration-runner`
ECS task (reuses the S7-02 worker image — already has `alembic`,
`psycopg`, `redis-py`), connected to with `aws ecs execute-command`
(ECS Exec), then stopped. Never a persistent service.

### Part 1 — Provisioned (Terraform, real `terraform apply` — see `infra/`)

RDS `db.t4g.micro`, PostgreSQL 16, Single-AZ, 20 GB gp3, private
subnets, deletion protection on, AWS-managed master password (Secrets
Manager, auto-rotated — this project never holds it). Redis as its own
Fargate service with Cloud Map service discovery. Both security groups
allow inbound only from a new `app` security group (a placeholder for
whatever runs the Fargate web/worker services in a later ticket) — zero
CIDR ranges.

**Real `aws ec2 describe-security-groups` output (2026-08-25):**

```
$ aws ec2 describe-security-groups --group-ids sg-0a5edd4f0ba3c0dce
{
    "GroupId": "sg-0a5edd4f0ba3c0dce",
    "Description": "RDS Postgres, inbound 5432 from the app SG only",
    "IpPermissions": [{
        "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
        "UserIdGroupPairs": [{"GroupId": "sg-016088c92a7c160f7"}],
        "IpRanges": [], "Ipv6Ranges": [], "PrefixListIds": []
    }]
}

$ aws ec2 describe-security-groups --group-ids sg-0fe7c9d8fb1dfe17e
{
    "GroupId": "sg-0fe7c9d8fb1dfe17e",
    "Description": "Self-hosted Redis (Fargate), inbound 6379 from the app SG only",
    "IpPermissions": [{
        "IpProtocol": "tcp", "FromPort": 6379, "ToPort": 6379,
        "UserIdGroupPairs": [{"GroupId": "sg-016088c92a7c160f7"}],
        "IpRanges": [], "Ipv6Ranges": [], "PrefixListIds": []
    }]
}
```

No `0.0.0.0/0`, no CIDR range at all — only the app SG, on both.

**Real finding: this AWS account is on Free Tier.** RDS rejected a
7-day backup retention with `FreeTierRestrictionError`; reduced to 1
day. Likely means real spend is lower than S7-01's ~$122/mo estimate for
the first 12 months — not re-priced here, flagged for S7-10.

### Part 2 — Full migration chain against fresh RDS (real, run inside the VPC)

```
$ alembic upgrade head
INFO  Running upgrade  -> 1149a517cb33, baseline transactions table
INFO  Running upgrade 1149a517cb33 -> 2b7c1704a037, add settings table
... [17 migrations total] ...
INFO  Running upgrade 6f1b3d8c4e29 -> 5c9a2e6b8f14, scope external_id uniqueness to user

$ alembic current
5c9a2e6b8f14 (head)

$ alembic history
6f1b3d8c4e29 -> 5c9a2e6b8f14 (head), scope external_id uniqueness to user
... [full chain, 18 revisions total incl. base] ...
<base> -> 1149a517cb33, baseline transactions table
```

Every migration since S2-01's baseline applied cleanly to a genuinely
fresh, empty RDS instance. Zero errors — no finding here.

### Part 3 — Real data migration, row counts, decryption

**Before (local dev, logged first, per S4-01 discipline):**
```
$ docker exec kbc_analyzer-db-1 psql -U kbc -d kbc_analyzer -c "SELECT ... UNION ALL ..."
      t       | count
--------------+-------
 budgets      |     3
 categories   |    10
 insights     |    50
 settings     |     3
 transactions |   366
 users        |     1
```

**Migration method:** `pg_dump -Fc` locally, uploaded to S3 via a
presigned URL (deleted after use, never a public object), downloaded
inside the migration-runner task, `pg_restore --data-only`. First
attempt collided with the schema already created by `alembic upgrade
head` moments earlier (34 "already exists" errors on constraints) —
truncated and redid `--data-only`. RDS's master user isn't a true
superuser, so `--disable-triggers` was rejected
(`permission denied: "RI_ConstraintTrigger..." is a system trigger`) —
worked around by restoring tables individually, in explicit FK-dependency
order (`users` → `categories` → `settings`/`budgets`/`insights` →
`transactions`), rather than trusting the dump's default TOC order,
which doesn't guarantee dependency-safe ordering for a data-only
restore.

**After (RDS, real query, post-restore):**
```
$ psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT ... UNION ALL ..."
      t       | count
--------------+-------
 budgets      |     3
 categories   |    10
 insights     |    50
 settings     |     3
 transactions |   366
 users        |     1
```

Exact match, every table.

**Decryption confirmed (real, no plaintext ever printed):**
```
gemini_api_key: DECRYPT_OK len=39
anthropic_api_key: DECRYPT_OK len=108
```
Both Fernet-encrypted API keys decrypted correctly against the migrated
RDS data, using the same local `SETTINGS_SECRET` — the encryption
round-trip survives the environment crossing.

### Part 4 — Redis-dependent features against AWS Redis (real function calls, not a container health check)

```
=== Redis-dependent feature test results (against AWS Redis) ===
PASS: session.create+get
PASS: session.destroy
PASS: sync_lock.acquire first
PASS: sync_lock.acquire second blocked
PASS: sync_lock.get_holder correct
PASS: sync_lock.release
PASS: job_store.set+get
PASS: job_store.heartbeat_stamped
ALL_PASS
```
Confirmed `REDIS_URL` was genuinely the AWS Redis, not a silent fallback
to the dev default: `printenv REDIS_URL` →
`redis://redis.kbc-analyzer.internal:6379/0`.

**`rate_limit` (S5-07): N/A, not tested.** Per Borys's decision earlier
in this ticket's session — `rate_limit.py` uses slowapi's in-memory
storage, not Redis at all (already documented in `ARCHITECTURE.md`,
flagged three times now without becoming a ticket: S5-07, S6-06, here).
There is nothing to verify against AWS Redis because it never touches
Redis. Tracked as a real Sprint 8 backlog item in `docs/backlog.md` so a
fourth rediscovery becomes "already backlogged," not "flagged again."

### Local dev stack — confirmed untouched

Same 5 containers, same uptime, same row counts as before this ticket
started. RDS is a new target, not a replacement.

### Cleanup performed

Migration-runner task stopped. Temporary S3 dump object deleted. Local
dump file and any scratch file containing `SETTINGS_SECRET` deleted —
nothing with real financial data or secrets left on disk longer than
the migration required.
