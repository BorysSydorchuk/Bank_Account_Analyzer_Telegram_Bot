Status: delivered

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
