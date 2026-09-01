resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}

# Trusted by ECS itself, used to pull images from ECR and write to
# CloudWatch Logs on the task's behalf — never used by application code.
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# The container's `secrets` field (used by the migration-runner task to
# inject DB_PASSWORD) is resolved by the ECS agent under the *execution*
# role, before the container even starts — not the task role, which only
# applies to code running inside the container. Found empirically: the
# task failed at ResourceInitializationError until this was added here.
resource "aws_iam_role_policy" "ecs_task_execution_read_db_secret" {
  name = "${var.project_name}-execution-read-db-secret"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadRdsManagedSecret"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_db_instance.main.master_user_secret[0].secret_arn
    }]
  })
}

# S7-04: the web/worker task definitions inject SETTINGS_SECRET,
# GOOGLE_CLIENT_SECRET, the Enable Banking private key content, and a
# pre-assembled DATABASE_URL via the container `secrets` field — same
# execution-role mechanism as the RDS secret above, since ECS resolves
# `secrets` before the container starts, under the execution role, not
# the task role. These four were created directly via `aws
# secretsmanager create-secret` (see docs/tickets/S7-04-...), not
# Terraform — their values never touch Terraform state.
data "aws_secretsmanager_secret" "settings_secret" {
  name = "kbc-analyzer/settings-secret"
}

data "aws_secretsmanager_secret" "google_client_secret" {
  name = "kbc-analyzer/google-client-secret"
}

data "aws_secretsmanager_secret" "eb_private_key" {
  name = "kbc-analyzer/eb-private-key"
}

data "aws_secretsmanager_secret" "database_url" {
  name = "kbc-analyzer/database-url"
}

# S8-05: same pattern as the four above — created directly via
# `aws secretsmanager create-secret`, not Terraform, so the real API key
# value never touches Terraform state.
data "aws_secretsmanager_secret" "resend_api_key" {
  name = "kbc-analyzer/resend-api-key"
}

# S9-01: same pattern — created directly via `aws secretsmanager
# create-secret`, real Stripe test-mode secret key never touches Terraform
# state. STRIPE_PUBLISHABLE_KEY is deliberately not here — it's meant to be
# client-visible (Stripe.js reads it in the browser), so it's not a secret
# and doesn't belong in Secrets Manager; wired as plain frontend config
# when S9-05 (Billing UI) actually needs it. STRIPE_WEBHOOK_SECRET is also
# not here yet — S9-03 generates it when the real webhook endpoint is
# created, not before.
data "aws_secretsmanager_secret" "stripe_secret_key" {
  name = "kbc-analyzer/stripe-secret-key"
}

# S10-02: same pattern — created directly via `aws secretsmanager
# create-secret`, real password/URLs never touch Terraform state.
# redis_password is the bare password, injected only into the Redis task
# itself (infra/redis.tf) for its own --requirepass startup flag.
# redis_url/redis_result_backend_url are the full connection strings (db 0
# and db 1 respectively) with that same password already embedded, injected
# into web/worker as REDIS_URL/CELERY_BROKER_URL and CELERY_RESULT_BACKEND —
# ECS `secrets` can only set an env var to a secret's whole value, not
# concatenate a secret into a larger string, so the assembled URL has to be
# its own secret, same reasoning as database_url above.
data "aws_secretsmanager_secret" "redis_password" {
  name = "kbc-analyzer/redis-password"
}

data "aws_secretsmanager_secret" "redis_url" {
  name = "kbc-analyzer/redis-url"
}

data "aws_secretsmanager_secret" "redis_result_backend_url" {
  name = "kbc-analyzer/redis-result-backend-url"
}

resource "aws_iam_role_policy" "ecs_task_execution_read_app_secrets" {
  name = "${var.project_name}-execution-read-app-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ReadAppSecrets"
      Effect = "Allow"
      Action = "secretsmanager:GetSecretValue"
      Resource = [
        data.aws_secretsmanager_secret.settings_secret.arn,
        data.aws_secretsmanager_secret.google_client_secret.arn,
        data.aws_secretsmanager_secret.eb_private_key.arn,
        data.aws_secretsmanager_secret.database_url.arn,
        data.aws_secretsmanager_secret.resend_api_key.arn,
        data.aws_secretsmanager_secret.stripe_secret_key.arn,
        data.aws_secretsmanager_secret.redis_password.arn,
        data.aws_secretsmanager_secret.redis_url.arn,
        data.aws_secretsmanager_secret.redis_result_backend_url.arn,
      ]
    }]
  })
}

# Assumed by application code running *inside* a task — scoped to what
# S7-03's migration-runner task actually needs: ECS Exec's SSM data
# channel (so `aws ecs execute-command` can open a shell), and read-only
# access to the one RDS-managed secret this task needs to connect.
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_exec" {
  name = "${var.project_name}-ecs-exec"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "SSMExecChannel"
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_read_db_secret" {
  name = "${var.project_name}-read-db-secret"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadRdsManagedSecret"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_db_instance.main.master_user_secret[0].secret_arn
    }]
  })
}
