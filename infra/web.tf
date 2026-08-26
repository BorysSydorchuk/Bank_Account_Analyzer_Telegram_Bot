# A default exists so re-applying this delivery doesn't require typing the
# tag every time — but that's exactly the footgun: a `terraform apply` run
# months from now without an explicit `-var` override would silently
# redeploy THIS commit's image, not whatever's actually current. Always
# pass -var="app_image_tag=<real current sha>" explicitly for any real
# deploy; treat the default as documentation of "what S7-04 shipped," not
# as a safe thing to rely on going forward.
variable "app_image_tag" {
  description = "Git-SHA tag of the kbc-analyzer-web/worker images to run"
  type        = string
  default     = "e8c177d"
}

locals {
  # Written to a file at container start from the eb-private-key secret
  # (S7-02 deliberately never bakes this into the image) — shared by both
  # the web and worker command overrides below.
  materialize_eb_key = "echo \"$EB_PRIVATE_KEY_CONTENT\" > /tmp/private.pem"
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.project_name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = "${aws_ecr_repository.web.repository_url}:${var.app_image_tag}"
      essential = true
      command = [
        "sh", "-c",
        "${local.materialize_eb_key} && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
      ]
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "FRONTEND_ORIGIN", value = "https://mymble.be" },
        { name = "COOKIE_SECURE", value = "true" },
        { name = "REDIS_URL", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/0" },
        { name = "CELERY_BROKER_URL", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/0" },
        { name = "CELERY_RESULT_BACKEND", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/1" },
        { name = "GOOGLE_CLIENT_ID", value = var.google_client_id },
        { name = "GOOGLE_REDIRECT_URI", value = "https://mymble.be/api/auth/google/callback" },
        { name = "EB_REDIRECT_URL", value = "https://mymble.be/api/auth/enable-banking/callback" },
        { name = "ENABLEBANKING_APP_ID", value = var.enablebanking_app_id },
        { name = "ENABLEBANKING_PRIVATE_KEY_PATH", value = "/tmp/private.pem" },
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = data.aws_secretsmanager_secret.database_url.arn },
        { name = "SETTINGS_SECRET", valueFrom = data.aws_secretsmanager_secret.settings_secret.arn },
        { name = "GOOGLE_CLIENT_SECRET", valueFrom = data.aws_secretsmanager_secret.google_client_secret.arn },
        { name = "EB_PRIVATE_KEY_CONTENT", valueFrom = data.aws_secretsmanager_secret.eb_private_key.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "web"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "web" {
  name            = "${var.project_name}-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  enable_execute_command = true

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}
