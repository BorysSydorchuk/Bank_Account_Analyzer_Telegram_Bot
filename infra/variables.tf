variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Short name used as a prefix for resource naming and tagging"
  type        = string
  default     = "kbc-analyzer"
}

variable "budget_notification_email" {
  description = "Email address that receives AWS Budget threshold alerts"
  type        = string
}

variable "budget_limit_usd" {
  description = "Monthly account cost budget limit, in USD"
  type        = number
  default     = 50
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}
