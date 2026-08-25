Status: confirmed

================================================================
TICKET S7-01 — AWS Foundation, Budget Guardrails & Architecture
================================================================
(FINAL — supersedes both prior versions of this ticket. This
architecture went through three rounds of revision after real
cost/technical research: Fargate+ALB+ElastiCache (original) →
App Runner claimed to avoid NAT Gateway (disproven against AWS's
own docs) → App Runner recommended anyway for smaller real
savings → invalidated once the Celery worker's requirements were
considered (App Runner doesn't cleanly host a non-HTTP background
worker). Final architecture below reflects all of that.)

WHAT TO BUILD:
The account structure, cost guardrails, and infrastructure-as-
code approach everything else in this sprint builds on. No app
deployment yet.

FINAL ARCHITECTURE DECISION:
- Compute: UNIFIED ECS FARGATE — one cluster, two services:
  - Web service (FastAPI + frontend, behind an ALB)
  - Worker service (Celery, no ALB — it doesn't serve HTTP)
  This was chosen over App Runner because this app has a
  non-HTTP background worker that App Runner's single-container,
  HTTP-serving model doesn't cleanly support. A hybrid (App
  Runner for web + Fargate for the worker) was considered and
  rejected — running two different compute platforms for one
  app costs more in operational complexity than the modest ALB
  saving App Runner would have offered.
- Redis: SELF-HOSTED CONTAINER (its own Fargate service, or
  co-located appropriately within the cluster — your call on
  exact placement, justify it), NOT ElastiCache. Real, safe
  saving at this traffic scale.
- NAT: A SINGLE NAT Gateway (not one per AZ). This is a
  deliberate cost/availability tradeoff for a portfolio-scale
  solo project — document it as such in ARCHITECTURE.md, it's
  a legitimate thing to explain in an interview, not something
  to hide.
  DO NOT swap this for a NAT Instance in this ticket. A NAT
  Instance is cheaper (~$3-8/mo vs ~$33-45/mo) but self-managed
  with no AWS-provided failover — real production risk for an
  app about to hold real bank data, on a deployment that hasn't
  been proven stable yet. Ship with the managed NAT Gateway now;
  the NAT Instance swap is an explicit Sprint 8 (or later)
  follow-up ticket once the deployment has run stable for a
  while — log this in verification_debt.md or the migration
  plan now, don't let it get forgotten.
- VPC Endpoints: add an S3 Gateway Endpoint (free, no downside)
  IF the app uses S3 for anything (check first — static assets,
  backups, etc.). Skip Interface Endpoints for ECR/CloudWatch
  for now — marginal benefit at this traffic scale, revisit only
  if NAT data-processing costs turn out to be meaningfully high
  once real usage exists.
- IaC: Terraform (unchanged from earlier decision).

STEP 0 — BEFORE ANYTHING ELSE IS PROVISIONED:
Set up an AWS Budget alert at €50/month, notifying at 50/80/100%
thresholds. First resource created, no exceptions.

BUILD:
- Dedicated IAM user/role for deployment (never root credentials),
  least-privilege policy
- VPC: public subnets (ALB, NAT Gateway) + private subnets (both
  Fargate services, RDS, Redis container) — the standard pattern
  applies fully now since everything is Fargate
- ECR repositories for both the web and worker images
- S3 Gateway Endpoint if applicable (see above)
- Terraform state in an S3 backend, not local

ACCEPTANCE CRITERIA:
- Budget alert is the first resource created, verified active
- VPC, ECR, IAM role, single NAT Gateway all provisioned via
  Terraform
- Nothing app-related deployed yet — foundation only
- No AWS credentials anywhere in git
- A real, itemized monthly cost estimate is produced for this
  exact architecture (single NAT Gateway + Fargate web+worker +
  RDS + self-hosted Redis + minor extras) — don't reuse the
  rough estimates from this decision's back-and-forth, calculate
  fresh against current AWS pricing for the actual instance sizes
  you plan to provision
- The NAT Instance follow-up is logged with a clear closure
  condition (e.g. "after N weeks of stable production operation")

WHEN DONE:
- Show the budget alert configuration
- Show the provisioned foundation resources
- State the final itemized cost estimate
- Confirm the NAT Instance follow-up is logged and where
- Explain: why does the worker service not need an ALB, and
  what would go wrong if one were attached to it anyway?
- Do not start S7-02 until confirmed

## AMENDMENT (2026-08-25)

Borys confirmed S7-01 delivery with three follow-up actions before S7-02
begins:

1. **Raise the budget alert to $150/month, same 50/80/100% thresholds.**
   The ~$122/month full-architecture estimate is accepted as the real
   cost of a deliberately-chosen architecture (unified Fargate + single
   NAT Gateway + ALB + RDS), not something to redesign around.
   Done — `infra/variables.tf`'s `budget_limit_usd` default raised
   50 → 150. By the time this was applied, the live AWS budget was
   already showing $150 (changed outside this session, presumably by
   Borys directly), so `terraform plan` found no drift — reconciled via
   `terraform apply -refresh-only` to persist that into remote state.
   Notification thresholds remain 50/80/100% (percentage-based, so they
   now trigger at $75/$120/$150) — confirmed via
   `aws budgets describe-notifications-for-budget`, all three
   `NotificationState: OK`.
2. **Pre-existing admin IAM user (`KBC_analyser_deploy`, `AdministratorAccess`)
   — Borys will personally check and decide its fate.** No action taken
   by Codee; left exactly as found.
3. **Verify AWS billing currency; recreate the budget in the correct
   currency if not USD.** Verified via AWS's own documentation (not
   assumed): AWS Budgets, Cost Explorer, and the Cost & Usage Report
   always track internally in USD, regardless of what currency an
   account is actually invoiced in — a structural property of those
   services, not a per-account configuration. No currency mismatch risk
   exists; no recreation needed. `ARCHITECTURE.md`'s cost-guardrail entry
   updated to state this as verified fact rather than an open flag.

Actions (1) and (3) are complete. Action (2) is intentionally left to
Borys. Proceeding to S7-02 per his instruction.

## AMENDMENT (2026-08-25) — Reviewer follow-up: WHEN DONE evidence gap

Reviewer found that S7-01's WHEN DONE answers (resource provisioning proof,
itemized cost estimate) were only ever narrated in chat, never captured as
artifacts in the repo — a real gap against the ticket's own acceptance
criteria ("Show the provisioned foundation resources", "State the final
itemized cost estimate"), not a paperwork nitpick. Fixed for real below,
not retroactively adjusted in the ledger.

### Proof the main Terraform config was actually applied

Confirmed two ways: (1) `terraform state list` in `infra/` shows 20 real
managed resources (not just the 5 in `infra/bootstrap/`), and (2) every
resource ID below was independently re-queried live against AWS on
2026-08-25 (`aws ec2 describe-vpcs`, `describe-nat-gateways`,
`describe-subnets`, `ecr describe-repositories`, `iam get-user`) — not
just read back from Terraform's own state file, which could in principle
be stale or wrong. All came back `available`/present with matching
attributes.

| Resource | ID / ARN | Live-verified attributes |
|---|---|---|
| VPC | `vpc-0ff5461f79e531821` | CIDR `10.0.0.0/16`, State `available` |
| NAT Gateway | `nat-09837d89472437832` | State `available`, in `subnet-0e75497bcd1a73a6f` |
| Public subnet (1a) | `subnet-0e75497bcd1a73a6f` | `10.0.0.0/24`, `eu-central-1a`, public IP on launch |
| Public subnet (1b) | `subnet-00a04d56c7b5ef82e` | `10.0.1.0/24`, `eu-central-1b`, public IP on launch |
| Private subnet (1a) | `subnet-0f95c89b63cf3becd` | `10.0.10.0/24`, `eu-central-1a`, no public IP |
| Private subnet (1b) | `subnet-03bff6a6b9d70b530` | `10.0.11.0/24`, `eu-central-1b`, no public IP |
| ECR repo (web) | `arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-web` | URI `904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-web` |
| ECR repo (worker) | `arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-worker` | URI `904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-worker` |
| IAM deploy user | `arn:aws:iam::904854373619:user/deploy/kbc-analyzer-deploy` | Created `2026-08-24T13:44:05Z` |
| Budget | `arn:aws:budgets::904854373619:budget/kbc-analyzer-monthly-budget` | $150/mo, thresholds 50/80/100%, all `NotificationState: OK` |

Verdict: the main config was genuinely applied on 2026-08-24, not just
planned or narrated. No cover-up needed here — the resources are real;
only the written record of them was missing until now.

### Itemized monthly cost estimate (real line items, not a bare total)

Priced directly against AWS's Price List API for `eu-central-1`
(queried 2026-08-24, not third-party estimates — see method note below).
Sizing assumptions: web Fargate task 0.5 vCPU/1 GB, worker and Redis
tasks at Fargate's floor (0.25 vCPU/0.5 GB) each, all three running
24/7 (730 hrs/month); RDS `db.t4g.micro` Single-AZ with 20 GB gp3
storage; NAT Gateway with ~10 GB/month processed (low-traffic solo
project); ALB with ~1 average LCU (not yet provisioned — arrives in
S7-04, included here because the ticket's acceptance criterion asks for
"this exact architecture," not just what S7-01 itself provisions).

| Component | Rate | Sizing | Monthly cost |
|---|---|---|---|
| NAT Gateway | $0.052/hr + $0.052/GB | 730 hrs + ~10 GB processed | $38.48 |
| Fargate — web | $0.04656/vCPU-hr + $0.00511/GB-hr | 0.5 vCPU / 1 GB, 24/7 | $20.72 |
| Fargate — worker | $0.04656/vCPU-hr + $0.00511/GB-hr | 0.25 vCPU / 0.5 GB, 24/7 | $10.36 |
| Fargate — Redis | $0.04656/vCPU-hr + $0.00511/GB-hr | 0.25 vCPU / 0.5 GB, 24/7 | $10.36 |
| RDS `db.t4g.micro` Single-AZ | $0.019/hr instance + $0.137/GB-mo gp3 | 730 hrs + 20 GB | $16.61 |
| ALB (S7-04, not yet live) | $0.027/hr + $0.008/LCU-hr | 730 hrs + ~1 LCU avg | $25.55 |
| ECR storage | $0.10/GB-mo | ~2 GB | $0.20 |
| S3 (TF state) + DynamoDB (lock) | negligible, near free tier | minimal | $0.05 |
| **Total, full target architecture** | | | **$122.33** |
| **Live today (S7-01 foundation only)** | NAT Gateway + ECR/S3/DynamoDB, no Fargate/RDS/ALB running yet | | **≈$38.53** |

**Pricing method, for reproducibility:** `aws pricing get-products`
against `us-east-1` (the Price List API's endpoint region — it still
returns per-region rates), filtered `Type=TERM_MATCH,Field=regionCode,
Value=eu-central-1`, per service (`AmazonECS` for Fargate, `AmazonRDS`,
`AmazonEC2` for NAT Gateway, `AmazonECR`, `AWSELB` for ALB). Raw query
JSON was written to temp files and deleted after extracting the rates
above — not retained in the repo, since it's derivable from the AWS API
at any time and isn't itself a project artifact worth versioning.

This replaces the bare "$122/month" total that previously existed only
as prose in chat, per Reviewer's finding.

## AMENDMENT (2026-08-25) — Second Reviewer follow-up: raw command output, missing WHEN DONE answer

Second Reviewer pass found the prior amendment's evidence was still
curated/summarized (a markdown table I wrote, not the actual command
output), and that WHEN DONE question 4 (worker/ALB) had never been
answered in this file at all — only narrated in chat. Fixing all four
WHEN DONE items with real, raw evidence below.

### 1. `terraform output` (raw, run 2026-08-25 against the real applied `infra/` state)

```
$ terraform output
budget_arn = "arn:aws:budgets::904854373619:budget/kbc-analyzer-monthly-budget"
deploy_iam_user_arn = "arn:aws:iam::904854373619:user/deploy/kbc-analyzer-deploy"
ecr_web_repository_url = "904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-web"
ecr_worker_repository_url = "904854373619.dkr.ecr.eu-central-1.amazonaws.com/kbc-analyzer-worker"
nat_gateway_id = "nat-09837d89472437832"
private_subnet_ids = [
  "subnet-0f95c89b63cf3becd",
  "subnet-03bff6a6b9d70b530",
]
public_subnet_ids = [
  "subnet-0e75497bcd1a73a6f",
  "subnet-00a04d56c7b5ef82e",
]
vpc_id = "vpc-0ff5461f79e531821"
```

`terraform show` (excerpted to the `id`/`arn` fields per resource, full
output is >600 lines) confirms the same IDs are actually attached to
real managed resources in state, not just declared as outputs:

```
resource "aws_budgets_budget" "monthly_cost" {
    arn = "arn:aws:budgets::904854373619:budget/kbc-analyzer-monthly-budget"
    id  = "904854373619:kbc-analyzer-monthly-budget"
resource "aws_ecr_repository" "web" {
    arn = "arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-web"
    id  = "kbc-analyzer-web"
resource "aws_ecr_repository" "worker" {
    arn = "arn:aws:ecr:eu-central-1:904854373619:repository/kbc-analyzer-worker"
    id  = "kbc-analyzer-worker"
resource "aws_iam_user" "deploy" {
    arn = "arn:aws:iam::904854373619:user/deploy/kbc-analyzer-deploy"
    id  = "kbc-analyzer-deploy"
resource "aws_internet_gateway" "main" {
    arn = "arn:aws:ec2:eu-central-1:904854373619:internet-gateway/igw-0942286b4d3257983"
    id  = "igw-0942286b4d3257983"
    vpc_id = "vpc-0ff5461f79e531821"
resource "aws_nat_gateway" "single" {
    id        = "nat-09837d89472437832"
    subnet_id = "subnet-0e75497bcd1a73a6f"
resource "aws_route_table" "private" {
    id = "rtb-03bb1bab783a3d17e"
    route { cidr_block = "0.0.0.0/0", nat_gateway_id = "nat-09837d89472437832" }
resource "aws_route_table" "public" {
    id = "rtb-0bc37987b57e60606"
    route { cidr_block = "0.0.0.0/0", gateway_id = "igw-0942286b4d3257983" }
```

The route table detail matters: `private` routes `0.0.0.0/0` through the
NAT Gateway, `public` routes it through the Internet Gateway — the
architecture is wired the way it's documented to be, not just present.

### 2. `aws budgets describe-budget` and `describe-notifications-for-budget` (raw, run 2026-08-25)

```
$ aws budgets describe-budget --account-id 904854373619 \
    --budget-name kbc-analyzer-monthly-budget --region us-east-1
{
    "Budget": {
        "BudgetName": "kbc-analyzer-monthly-budget",
        "BudgetLimit": { "Amount": "150.0", "Unit": "USD" },
        "TimeUnit": "MONTHLY",
        "CalculatedSpend": { "ActualSpend": { "Amount": "0.0", "Unit": "USD" } },
        "BudgetType": "COST",
        "LastUpdatedTime": 1787668957.846,
        "HealthStatus": { "Status": "HEALTHY", "LastUpdatedTime": 1787668957.528 }
    }
}

$ aws budgets describe-notifications-for-budget --account-id 904854373619 \
    --budget-name kbc-analyzer-monthly-budget --region us-east-1
{
    "Notifications": [
        { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 100.0, "NotificationState": "OK" },
        { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 50.0,  "NotificationState": "OK" },
        { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 80.0,  "NotificationState": "OK" }
    ]
}
```

$150/mo, HEALTHY, all three thresholds (50/80/100%) present with
`NotificationState: OK` (none tripped — actual spend is $0.00, expected
since no Fargate/RDS/ALB is deployed yet).

### 3. Itemized cost table

Already committed for real in this file's first Reviewer-follow-up
amendment above (2026-08-25) — see "Itemized monthly cost estimate (real
line items, not a bare total)". Independently recomputed and confirmed
correct by the first Reviewer pass (VERDICT: PASS on this specific
criterion, second Reviewer pass raised no new objection to the table
itself — only to items 1, 2, and 4 below). Not duplicated here to avoid
two competing copies of the same table drifting out of sync; that
section is the single source of truth for the cost breakdown.

### 4. Why the worker service doesn't need an ALB, and what breaks if one's attached anyway

An ALB is a Layer 7 HTTP router: it needs a listener (port + protocol)
and a target group it health-checks over HTTP(S). Celery has no HTTP
server inside it — it's a process that polls Redis for jobs and executes
them. There is no request to route *to* and no `/health` endpoint to
poll *for*.

If an ALB were attached to the worker service anyway: its health checks
would get connection-refused or timeouts against the worker's container
port (nothing is listening there), the target would sit permanently
"unhealthy," and the ALB would correctly — but uselessly — stop routing
to it, while still accruing its own ~$20-25/month (base hourly rate plus
LCU usage, see the cost table) for a listener that never receives real
traffic to route in the first place, since nothing external is meant to
reach Celery directly.

This is why S7-01's architecture has the worker service with no ALB at
all, not an ALB with a permanently-failing health check — the omission
is deliberate, not an oversight.
