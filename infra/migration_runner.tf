# S7-03: not a permanent service — a one-off task definition used to run
# the Alembic migration, the real data restore, and the Redis-feature
# checks from *inside* the VPC, since RDS/Redis sit in private subnets
# with no route from outside AWS at all (a security-group rule can't fix
# that; only a route table can, and private subnets only route outbound).
# Reuses the S7-02 worker image — it already has alembic, psycopg, and
# redis-py in its venv, so no new image is needed for this. Run via
# `aws ecs run-task`, shelled into via `aws ecs execute-command`, then
# stopped — never a running service; a full app "worker" service with
# its own permanent task definition belongs to a later ticket that
# actually deploys the app (this ticket only needs to prove RDS/Redis
# work, not stand up the application itself).
resource "aws_ecs_task_definition" "migration_runner" {
  family                   = "${var.project_name}-migration-runner"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "migration-runner"
      image     = "${aws_ecr_repository.worker.repository_url}:${var.migration_runner_image_tag}"
      essential = true
      # Overrides the image's default Celery CMD — this task is a shell
      # to exec into, not a running worker. S7-06: materializes the Enable
      # Banking private key first, same as web.tf/worker.tf's real
      # services — this task didn't need to make real Enable Banking API
      # calls before now (S7-03's migration/dump work never touched it),
      # but verifying a real per-user sync does.
      command = ["sh", "-c", "${local.materialize_eb_key} && exec sleep infinity"]
      environment = [
        { name = "DB_HOST", value = aws_db_instance.main.address },
        { name = "DB_PORT", value = tostring(aws_db_instance.main.port) },
        { name = "DB_NAME", value = aws_db_instance.main.db_name },
        { name = "DB_USER", value = aws_db_instance.main.username },
        { name = "REDIS_URL", value = "redis://${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}:6379/0" },
        { name = "ENABLEBANKING_APP_ID", value = var.enablebanking_app_id },
        { name = "ENABLEBANKING_PRIVATE_KEY_PATH", value = "/tmp/private.pem" },
      ]
      secrets = [
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:password::"
        },
        # S7-06: added once this task actually needed to decrypt a real
        # Fernet-encrypted value (enable_banking_sessions) or make a real
        # Enable Banking API call to verify a real sync — DB_PASSWORD alone
        # was enough for the S7-03 migration/dump work this task
        # definition was originally built for, neither of these was.
        {
          name      = "SETTINGS_SECRET"
          valueFrom = data.aws_secretsmanager_secret.settings_secret.arn
        },
        {
          name      = "EB_PRIVATE_KEY_CONTENT"
          valueFrom = data.aws_secretsmanager_secret.eb_private_key.arn
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migration-runner"
        }
      }
    }
  ])
}
