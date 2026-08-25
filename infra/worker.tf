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
        { name = "REDIS_URL", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/0" },
        { name = "CELERY_BROKER_URL", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/0" },
        { name = "CELERY_RESULT_BACKEND", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/1" },
        { name = "ENABLEBANKING_APP_ID", value = var.enablebanking_app_id },
        { name = "ENABLEBANKING_PRIVATE_KEY_PATH", value = "/tmp/private.pem" },
        { name = "ENABLE_BANKING_OWNER_EMAIL", value = var.enable_banking_owner_email },
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = data.aws_secretsmanager_secret.database_url.arn },
        { name = "SETTINGS_SECRET", valueFrom = data.aws_secretsmanager_secret.settings_secret.arn },
        { name = "EB_PRIVATE_KEY_CONTENT", valueFrom = data.aws_secretsmanager_secret.eb_private_key.arn },
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
