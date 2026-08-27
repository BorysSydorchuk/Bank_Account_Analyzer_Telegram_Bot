# Dedicated deployment identity — never use root or personal credentials
# to push images or manage app infrastructure day-to-day.
#
# Scoped to ECR only for now: that is the only capability this ticket's
# foundation actually needs (S7-02 pushes images). Permissions for ECS,
# RDS, Secrets Manager etc. are added in the tickets that create those
# resources, not granted speculatively now — granting access to
# resources that don't exist yet isn't "least privilege," it's a wider
# blast radius sitting unused.
resource "aws_iam_user" "deploy" {
  name = "${var.project_name}-deploy"
  path = "/deploy/"
}

resource "aws_iam_user_policy" "deploy_ecr" {
  name = "${var.project_name}-deploy-ecr"
  user = aws_iam_user.deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "ECRPushPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = [
          aws_ecr_repository.web.arn,
          aws_ecr_repository.worker.arn
        ]
      }
    ]
  })
}

# S8-02: widened beyond ECR-only, permanently — Borys's call, not a
# one-off. The scoped deploy user now needs to run `terraform apply`
# (which requires read visibility into whatever it refreshes, targeted
# or not) and to actually launch/exec into the migration-runner ECS
# task, not just push images to it. Kept as a *separate* policy from
# deploy_ecr on purpose — easy to audit or revoke independently of the
# original ECR-only grant, which stays exactly as narrow as S7-01 built
# it.
#
# Deliberate shape: broad READ (Describe/Get/List — never a mutating
# verb) across every service this Terraform config touches, so future
# tickets' applies don't need to renegotiate this again; narrow WRITE —
# only ECS task definitions, RunTask/StopTask/DescribeTasks/
# ExecuteCommand on the migration-runner family and this cluster
# specifically, and iam:PassRole restricted to the two roles that
# family actually uses. This user still cannot create, modify, or
# delete RDS, VPC/networking, ALB, Route53, ACM, IAM roles/users, or
# budgets — those stay untouched until a ticket that genuinely needs to
# change them justifies widening again, same philosophy as this file's
# original comment, just extended to what S8-02 actually needs.
resource "aws_iam_user_policy" "deploy_terraform_state" {
  name = "${var.project_name}-deploy-terraform-state"
  user = aws_iam_user.deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformStateBucket"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.project_name}-terraform-state-${data.aws_caller_identity.current.account_id}",
          "arn:aws:s3:::${var.project_name}-terraform-state-${data.aws_caller_identity.current.account_id}/*"
        ]
      },
      {
        Sid      = "TerraformStateLock"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}-terraform-lock"
      }
    ]
  })
}

resource "aws_iam_user_policy" "deploy_infra_read" {
  name = "${var.project_name}-deploy-infra-read"
  user = aws_iam_user.deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadOnlyForTerraformRefresh"
        Effect = "Allow"
        Action = [
          "ecs:Describe*",
          "ecs:List*",
          "ec2:Describe*",
          "rds:Describe*",
          "rds:ListTagsForResource",
          "elasticloadbalancing:Describe*",
          "route53:Get*",
          "route53:List*",
          "acm:Describe*",
          "acm:List*",
          "logs:Describe*",
          "logs:List*",
          "logs:GetLogGroup*",
          "servicediscovery:Get*",
          "servicediscovery:List*",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets",
          # Real gap found applying this for real (2026-08-27): the
          # data "aws_secretsmanager_secret" data source calls
          # GetResourcePolicy too, not just DescribeSecret, to fully
          # resolve — still read-only, never GetSecretValue.
          "secretsmanager:GetResourcePolicy",
          # Same real-gap discovery, found in two rounds (first
          # DescribeRepositories, then ListTagsForResource) — widened to
          # the same Describe*/List* pattern as every other service here
          # rather than adding one action at a time again. deploy_ecr's
          # push/pull-only policy never granted any of this; it only
          # covers layer operations.
          "ecr:Describe*",
          "ecr:List*",
          "budgets:ViewBudget",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetUser",
          "iam:ListUserPolicies",
          "iam:ListAttachedUserPolicies"
        ]
        Resource = "*"
      }
    ]
  })
}

// Managed policy, not inline like deploy_ecr/deploy_terraform_state/
// deploy_infra_read above — real limit hit applying this for real
// (2026-08-27): AWS caps inline user policies at 2048 bytes, and this
// one's five conditioned statements don't fit. Customer-managed
// policies cap at 6144 bytes instead, comfortably enough, at the minor
// cost of one extra attachment resource.
resource "aws_iam_policy" "deploy_migration_runner" {
  name = "${var.project_name}-deploy-migration-runner"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # AWS's ECS task-definition APIs don't support resource-level
        # restriction on Register/Deregister — Resource "*" is the only
        # option; DescribeTaskDefinition is included here rather than
        # deploy_infra_read's broader ecs:Describe* to keep this file's
        # write-adjacent grants grouped together with what they enable.
        Sid    = "ManageMigrationRunnerTaskDefinition"
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DeregisterTaskDefinition",
          "ecs:DescribeTaskDefinition"
        ]
        Resource = "*"
      },
      {
        Sid      = "RunMigrationRunnerTask"
        Effect   = "Allow"
        Action   = "ecs:RunTask"
        Resource = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/${var.project_name}-migration-runner:*"
        Condition = {
          ArnEquals = {
            "ecs:cluster" = aws_ecs_cluster.main.arn
          }
        }
      },
      {
        Sid    = "ManageAndExecIntoTasksOnThisCluster"
        Effect = "Allow"
        Action = [
          "ecs:DescribeTasks",
          "ecs:StopTask",
          "ecs:ExecuteCommand"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "ecs:cluster" = aws_ecs_cluster.main.arn
          }
        }
      },
      {
        Sid    = "SSMExecChannel"
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      },
      {
        # Restricted to exactly the two roles migration-runner (and every
        # other ECS task in this stack) actually uses — not iam:PassRole
        # on "*", which would let this identity hand ECS tasks any role
        # in the account, not just these two.
        Sid    = "PassMigrationRunnerRoles"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "deploy_migration_runner" {
  user       = aws_iam_user.deploy.name
  policy_arn = aws_iam_policy.deploy_migration_runner.arn
}
