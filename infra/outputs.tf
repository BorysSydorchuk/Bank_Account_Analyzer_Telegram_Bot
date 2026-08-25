output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "nat_gateway_id" {
  value = aws_nat_gateway.single.id
}

output "ecr_web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}

output "ecr_worker_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "deploy_iam_user_arn" {
  value = aws_iam_user.deploy.arn
}

output "budget_arn" {
  value = aws_budgets_budget.monthly_cost.arn
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "rds_arn" {
  value = aws_db_instance.main.arn
}

output "rds_master_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "redis_dns_name" {
  value = "${aws_service_discovery_service.redis.name}.${aws_service_discovery_private_dns_namespace.internal.name}"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "migration_runner_task_definition_arn" {
  value = aws_ecs_task_definition.migration_runner.arn
}

output "app_security_group_id" {
  value = aws_security_group.app.id
}
