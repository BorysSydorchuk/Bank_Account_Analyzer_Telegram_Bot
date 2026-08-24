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
