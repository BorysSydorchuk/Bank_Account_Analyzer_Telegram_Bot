# Private DNS so Redis is reachable at a stable name from anywhere in the
# VPC (redis.kbc-analyzer.internal), the same pattern local dev already
# uses (redis://redis:6379 via Docker's own DNS) — not a raw task IP,
# which changes on every task replacement.
resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "${var.project_name}.internal"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "redis" {
  name = "redis"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
}

# S7-01's "self-hosted container" Redis decision, placed as its own
# Fargate service in the ECS cluster S7-03 creates — not co-located in
# the same task as web/worker, so a web/worker deploy/restart can never
# take Redis down with it, and vice versa. All four Redis-dependent
# features (session, sync_lock, rate_limit-if-ever-migrated, job_store)
# are explicitly transient/restart-tolerant by design (see their own
# docstrings), so no persistent volume is attached — same as local dev's
# redis:7-alpine container, which also runs with no volume.
resource "aws_ecs_task_definition" "redis" {
  family                   = "${var.project_name}-redis"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "redis"
      image     = "redis:7-alpine"
      essential = true
      portMappings = [{
        containerPort = 6379
        protocol      = "tcp"
      }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "redis"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "redis" {
  name            = "${var.project_name}-redis"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.redis.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  enable_execute_command = true

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.redis.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.redis.arn
  }
}
