output "state_bucket" {
  description = "Name of the S3 bucket holding Terraform state for infra/"
  value       = aws_s3_bucket.tf_state.id
}

output "lock_table" {
  description = "Name of the DynamoDB table used for Terraform state locking"
  value       = aws_dynamodb_table.tf_lock.name
}
