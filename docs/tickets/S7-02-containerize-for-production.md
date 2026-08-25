Status: delivered

================================================================
TICKET S7-02 — Containerize for Production & Push to ECR
================================================================

WHAT TO BUILD:
Production-ready container images for BOTH services (web and
worker, per S7-01's unified Fargate decision), pushed to the
two ECR repos S7-01 created. Not running yet — that's S7-03/
S7-04 once RDS/Redis exist to connect to.

WHAT TO BUILD:
- Multi-stage Dockerfiles for backend/frontend if not already
  (smaller production images, no dev dependencies shipped)
- TWO distinct production images: the web image (FastAPI +
  frontend serving) and the worker image (Celery) — confirm
  whether these should be genuinely separate Dockerfiles/
  images or one shared base image with a different CMD/
  entrypoint per service. Either is valid; state and justify
  your choice.
- Confirm the non-root user from S4-09 carries into BOTH
  production images
- Frontend: production build (Vite build output served
  statically, not the dev server) — decide serving approach
  (nginx sidecar within the web task, served by the backend,
  or a separate static host — your call, justify)
- Push both images to their respective ECR repos
  (kbc-analyzer-web, kbc-analyzer-worker) with sensible tags
  (not just `latest` — recommend git-sha-based tags, since
  this project already has good git hygiene to build on)
- CI step or documented manual process to build + push (a
  full CI/CD pipeline is nice-to-have, not required — a
  working, documented sequence is the acceptance bar; note
  if you want to propose GitHub Actions as a follow-up,
  don't build it now)

ACCEPTANCE CRITERIA:
- Both images build successfully, non-root confirmed in both
- Both images pushed to their correct ECR repos, tagged
  sensibly
- Frontend serving approach decided and working locally
  against the production build
- Documented build/push process (even if manual)
- ARCHITECTURE.md updated with the image-build/tagging
  approach and which repo holds which image

WHEN DONE (show real evidence, not descriptions — this
project's Testing Standard applies here as strictly as it
did to S7-01):
- Show successful build output for both images
- Show real `aws ecr describe-images` output (or equivalent)
  confirming both images actually landed in ECR, not just a
  description of having pushed them
- State the frontend serving decision and why
- State the shared-base-image vs. two-Dockerfiles decision
  and why
- Do not start S7-03 until confirmed

## DELIVERY (2026-08-25)

### Decisions

**Shared base image, two build targets (not two independent Dockerfiles):**
one `Dockerfile.prod` with a shared `python-deps` stage (dependencies
installed once — web and worker are guaranteed to run identical
versions, never silently drift apart) and a shared `runtime-base` stage
(non-root user, allowlisted file copy), diverging only in the final
`web`/`worker` stages. This mirrors the existing dev convention already
in `docker-compose.yml`, where `backend` and `celery_worker` already
build from the same `./backend` Dockerfile with only the `command:`
differing. The `web` target isn't byte-identical to `worker` — it
additionally needs the compiled frontend baked in — so genuinely
identical images with only a runtime CMD override (as dev does) wasn't
possible once frontend-serving-by-backend was chosen; a shared base with
two final stages is the closest equivalent that still avoids maintaining
two independent Dockerfiles that could drift.

**Frontend served by the backend, not an nginx sidecar or separate static
host:** S7-01 provisioned exactly two ECR repos (`kbc-analyzer-web`,
`kbc-analyzer-worker`). An nginx-sidecar approach would need a third
image/registry for nginx+frontend, outside S7-01's stated scope, and
would add a second container (and its own vCPU/memory allocation, real
Fargate cost per S7-01's pricing) to the web ECS task for a low-traffic
solo project that doesn't need nginx's performance headroom. FastAPI's
`StaticFiles` plus a small SPA-fallback route (`app/main.py`, guarded by
`static/` existing so local dev is unaffected) is simpler to operate and
cheaper, at the cost of nginx's superior caching/compression — an
acceptable tradeoff at this traffic scale.

### Build output (real, run 2026-08-25)

```
$ docker build -f Dockerfile.prod --target worker -t kbc-analyzer-worker:test .
...
#15 exporting to image
#16 naming to docker.io/library/kbc-analyzer-worker:test done
#16 DONE 9.2s

$ docker build -f Dockerfile.prod --target web -t kbc-analyzer-web:test .
...
#25 [frontend-build 9/9] RUN npm run build
#25 6.589 dist/index.html                     0.73 kB
#25 6.589 dist/assets/index-B51EglKZ.css     48.35 kB
#25 6.589 dist/assets/index-DQSJkXVW.js   1,063.62 kB
#25 DONE 6.7s
#27 naming to docker.io/library/kbc-analyzer-web:test done
```

Both built successfully, no errors.

### Non-root confirmed (real, run against the built images)

```
$ docker run --rm kbc-analyzer-worker:test whoami
appuser
$ docker run --rm --entrypoint python kbc-analyzer-web:test -c "import getpass; print(getpass.getuser())"
appuser
$ docker run --rm --entrypoint id kbc-analyzer-worker:test
uid=100(appuser) gid=101(appgroup) groups=101(appgroup)
```

### No secrets leaked into either image (real, run against the built images)

```
$ docker run --rm --entrypoint sh kbc-analyzer-web:test -c \
    "find /app -iname '*.pem' -o -iname 'eb_session*' -o -iname '.env' -o -iname 'kbc_transactions.db'"
(no output — none found)
$ docker run --rm --entrypoint sh kbc-analyzer-worker:test -c \
    "find /app -iname '*.pem' -o -iname 'eb_session*' -o -iname '.env' -o -iname 'kbc_transactions.db'"
(no output — none found)
```

### Frontend serving verified end to end (real, container run locally)

Ran the `web` image with a syntactically valid but unreachable
`DATABASE_URL` (RDS doesn't exist yet — S7-03), to prove the app starts
and serves static content independently of DB availability, while
`/health` still degrades correctly rather than crashing the process:

```
$ docker run -d --rm -p 18000:8000 -e DATABASE_URL="postgresql+psycopg://user:pass@unreachable-host:5432/db" kbc-analyzer-web:test

$ curl -o /dev/null -w "HTTP %{http_code}\n" http://localhost:18000/
HTTP 200
$ curl -o /dev/null -w "HTTP %{http_code}\n" http://localhost:18000/dashboard/some-client-route
HTTP 200
$ curl -o /dev/null -w "HTTP %{http_code}\n" http://localhost:18000/assets/index-DQSJkXVW.js
HTTP 200
$ curl -w "\nHTTP %{http_code}\n" http://localhost:18000/health
{"message":"Database unavailable. Please try again shortly."}
HTTP 503
```

Root path serves `index.html`, a client-side route falls back to
`index.html` correctly (SPA routing works), the real hashed JS asset
serves — all 200. `/health` correctly returns the CLAUDE.md-mandated
structured 503 rather than crashing the container, confirming the
error-handling contract survives into the production image.

### Worker sanity check (real, container run locally)

```
$ docker run --rm -e CELERY_BROKER_URL="redis://unreachable-host:6379/0" \
    -e DATABASE_URL="postgresql+psycopg://user:pass@unreachable-host:5432/db" \
    kbc-analyzer-worker:test celery -A app.celery_app worker --loglevel=info
...
[tasks]
  . app.tasks.analysis.run_sync_job
  . app.tasks.auth.catch_enable_banking_callback
```

Celery starts cleanly and registers both real tasks; only blocked on
connecting to the deliberately-fake broker, as expected without Redis.

### WATCH OUT FOR

`app/db.py` builds the SQLAlchemy engine eagerly at import time — if
`DATABASE_URL` is malformed or absent, the *entire* process crashes
before serving anything, including static frontend files. Previously
this only affected API functionality; now that the same container also
serves the frontend, a DB misconfiguration in the ECS task definition
would take down the whole site, not just API calls. Not a new bug (this
is inherited behavior from before S7-02), but worth flagging before
S7-03/S7-04 wire up the real `DATABASE_URL` — get that env var right the
first time.

Pushing to ECR next; real `aws ecr describe-images` evidence to follow
in this file once pushed, tagged with this delivery's real git SHA
rather than a placeholder.

### Pushed to ECR — real `aws ecr describe-images` output (2026-08-25)

Tagged and pushed with this delivery's actual git SHA (`c9e7152`, the
commit containing this ticket's code), not a placeholder:

```
$ docker tag kbc-analyzer-web:test    904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-web:c9e7152
$ docker tag kbc-analyzer-worker:test 904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-worker:c9e7152
$ docker push .../kbc-analyzer-web:c9e7152
c9e7152: digest: sha256:b6786213db4777411991ab5932c6f701794c57d0cca912a0d00f6b4b7dc3b988 size: 856
$ docker push .../kbc-analyzer-worker:c9e7152
c9e7152: digest: sha256:dee89756c2dc3604ebfaf6b87df57e8ab18f2cf90ef3e0dc32d7bb6da4a705bb size: 856

$ aws ecr describe-images --repository-name kbc-analyzer-web
{
    "imageDetails": [
        {
            "repositoryName": "kbc-analyzer-web",
            "imageDigest": "sha256:b6786213db4777411991ab5932c6f701794c57d0cca912a0d00f6b4b7dc3b988",
            "imageTags": ["c9e7152"],
            "imageSizeInBytes": 100069111,
            "imagePushedAt": 1787672268.271,
            "imageStatus": "ACTIVE"
        }
        // + 2 untagged attestation/manifest-index sub-artifacts BuildKit
        //   pushes alongside every image — expected, not a finding.
    ]
}

$ aws ecr describe-images --repository-name kbc-analyzer-worker
{
    "imageDetails": [
        {
            "repositoryName": "kbc-analyzer-worker",
            "imageDigest": "sha256:dee89756c2dc3604ebfaf6b87df57e8ab18f2cf90ef3e0dc32d7bb6da4a705bb",
            "imageTags": ["c9e7152"],
            "imageSizeInBytes": 99743219,
            "imagePushedAt": 1787672279.578,
            "imageStatus": "ACTIVE"
        }
        // same, + 2 untagged sub-artifacts
    ]
}
```

Both images ~100 MB, `ACTIVE`, tagged `c9e7152` — real, in ECR, tied to
the exact commit that produced them. S7-02 delivered.
