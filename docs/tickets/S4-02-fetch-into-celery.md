Status: confirmed
Source: sprint4_tickets.txt (original)
Shipped as: bd927eb — feat: S4-02 move Enable Banking fetch into Celery

---

================================================================
TICKET S4-02 — Move Enable Banking Fetch into Celery
================================================================

WHAT TO BUILD:
Currently POST /api/transactions/sync still does the Enable
Banking fetch synchronously (4-18s) before returning a job_id.
Move the fetch itself into the Celery task so the sync
endpoint returns a job_id in under 500ms.

CURRENT FLOW:
  POST /sync → fetch from Enable Banking (4-18s) →
  store to DB → dispatch Celery task → return job_id

TARGET FLOW:
  POST /sync → create job record → dispatch Celery task →
  return job_id (< 500ms)
  Celery task: fetch → store → categorize → insights

JOB STAGES (update GET /api/jobs/{job_id}):
  "fetching"           → "Fetching transactions from KBC..."
  "storing"            → "Storing N transactions..."
  "categorizing"       → "Categorizing batch X of Y..."
  "generating_insights"→ "Generating insights..."
  "done"               → "Done — N transactions, M insights"

FRONTEND:
Update the polling progress text to show the two new stages.
The sync button should feel instant — no perceptible delay
between click and "Fetching transactions from KBC..."
appearing in the status line.

ACCEPTANCE CRITERIA:
- POST /sync returns job_id in under 500ms (measure it)
- Polling shows "fetching" and "storing" stages before
  "categorizing"
- Full sync completes correctly end-to-end
- Enable Banking auth errors (expired session) surface
  correctly through the job status, not as a sync 401

WHEN DONE:
- Show POST /sync response time (should be < 500ms)
- Show the full polling sequence including the new stages
- Explain: what happens to the job if the Celery worker
  crashes during the fetch stage?
- Do not start S4-03 until confirmed
