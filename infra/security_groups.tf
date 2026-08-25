# S7-03: the "app" security group represents whatever runs the Fargate
# web/worker services and the migration-runner task below — it doesn't
# have a service attached to it yet (that's S7-04's job), but RDS/Redis
# need something concrete to name as their only allowed source now.
resource "aws_security_group" "app" {
  name_prefix = "${var.project_name}-app-"
  description = "Fargate web/worker services and one-off in-VPC tasks (e.g. the S7-03 migration runner)"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "All outbound (RDS, Redis, ECR, Enable Banking, LLM providers, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  description = "RDS Postgres, inbound 5432 from the app SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from the app tier"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-redis-"
  description = "Self-hosted Redis (Fargate), inbound 6379 from the app SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from the app tier"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}
