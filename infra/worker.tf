resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.worker.repository_url}:${var.app_image_tag}"
      essential = true
      command = [
        "sh", "-c",
        "${local.materialize_eb_key} && exec celery -A app.celery_app worker --loglevel=info"
      ]
      environment = [
        { name = "ENABLEBANKING_APP_ID", value = var.enablebanking_app_id },
        { name = "ENABLEBANKING_PRIVATE_KEY_PATH", value = "/tmp/private.pem" },
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = data.aws_secretsmanager_secret.database_url.arn },
        { name = "SETTINGS_SECRET", valueFrom = data.aws_secretsmanager_secret.settings_secret.arn },
        { name = "EB_PRIVATE_KEY_CONTENT", valueFrom = data.aws_secretsmanager_secret.eb_private_key.arn },
        # S10-02: was a plain `environment` value (no auth) until this
        # ticket — now sourced from Secrets Manager, password embedded,
        # same assembled-URL pattern as DATABASE_URL above.
        { name = "REDIS_URL", valueFrom = data.aws_secretsmanager_secret.redis_url.arn },
        { name = "CELERY_BROKER_URL", valueFrom = data.aws_secretsmanager_secret.redis_url.arn },
        { name = "CELERY_RESULT_BACKEND", valueFrom = data.aws_secretsmanager_secret.redis_result_backend_url.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  enable_execute_command = true

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }
}
