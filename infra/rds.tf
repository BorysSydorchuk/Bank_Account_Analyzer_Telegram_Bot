resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = aws_subnet.private[*].id
}

# S7-03: db.t4g.micro Single-AZ, matching S7-01's sizing assumption and
# cost estimate exactly. Password is AWS-managed (manage_master_user_
# password), not a Terraform variable or a value anyone types — RDS
# creates and rotates its own Secrets Manager secret, and this project
# never holds the master password anywhere itself. Deletion protection
# and a final snapshot on destroy are both on: this instance holds real
# migrated financial data as of this ticket, not throwaway test data.
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "kbc_analyzer"
  username = "kbc"

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-db-final"

  # 1, not the usual 7 — this account is on AWS Free Tier, which caps
  # backup retention below what a non-free-tier account allows (found
  # empirically: 7 was rejected with FreeTierRestrictionError).
  backup_retention_period = 1
}
