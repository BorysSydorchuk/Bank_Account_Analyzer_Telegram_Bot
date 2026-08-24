terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend config supplied at `terraform init` time via -backend-config,
  # pointing at the bucket/table created by infra/bootstrap. Kept empty
  # here so this file doesn't hardcode a bucket name tied to one AWS
  # account.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
      Sprint    = "S7"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}
