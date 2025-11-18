# Terraform Outputs for CompanyCam Photo Detection Infrastructure

# ==============================================================================
# VPC Outputs
# ==============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "nat_gateway_ips" {
  description = "Elastic IPs of NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

# ==============================================================================
# Security Group Outputs
# ==============================================================================

output "alb_security_group_id" {
  description = "Security Group ID for Application Load Balancer"
  value       = aws_security_group.alb.id
}

output "backend_security_group_id" {
  description = "Security Group ID for backend services"
  value       = aws_security_group.backend_services.id
}

output "redis_security_group_id" {
  description = "Security Group ID for Redis cluster"
  value       = aws_security_group.redis.id
}

output "rds_security_group_id" {
  description = "Security Group ID for RDS database"
  value       = aws_security_group.rds.id
}

# ==============================================================================
# S3 Outputs
# ==============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 photo storage bucket"
  value       = aws_s3_bucket.photos.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 photo storage bucket"
  value       = aws_s3_bucket.photos.arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = aws_s3_bucket.photos.bucket_domain_name
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.photos.bucket_regional_domain_name
}

# ==============================================================================
# API Gateway Outputs
# ==============================================================================

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_apigatewayv2_api.main.id
}

output "api_gateway_endpoint" {
  description = "Endpoint URL of the API Gateway"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_gateway_stage_invoke_url" {
  description = "Invoke URL for the API Gateway stage"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

output "api_gateway_execution_arn" {
  description = "Execution ARN of the API Gateway (for Lambda permissions)"
  value       = aws_apigatewayv2_api.main.execution_arn
}

# ==============================================================================
# Redis (ElastiCache) Outputs
# ==============================================================================

output "redis_endpoint" {
  description = "Primary endpoint for Redis cluster"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_port" {
  description = "Port for Redis cluster"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].port
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
  sensitive   = true
}

# ==============================================================================
# CloudWatch Outputs
# ==============================================================================

output "cloudwatch_log_group_api_gateway" {
  description = "CloudWatch log group name for API Gateway"
  value       = aws_cloudwatch_log_group.api_gateway.name
}

output "cloudwatch_log_group_photo_upload" {
  description = "CloudWatch log group name for Photo Upload Service"
  value       = aws_cloudwatch_log_group.photo_upload.name
}

output "cloudwatch_log_group_detection" {
  description = "CloudWatch log group name for Detection Service"
  value       = aws_cloudwatch_log_group.detection.name
}

output "cloudwatch_log_group_metadata" {
  description = "CloudWatch log group name for Metadata Service"
  value       = aws_cloudwatch_log_group.metadata.name
}

# ==============================================================================
# IAM Outputs
# ==============================================================================

output "photo_upload_service_role_arn" {
  description = "ARN of Photo Upload Service IAM role"
  value       = aws_iam_role.photo_upload_service.arn
}

output "detection_service_role_arn" {
  description = "ARN of Detection Service IAM role"
  value       = aws_iam_role.detection_service.arn
}

output "metadata_service_role_arn" {
  description = "ARN of Metadata Service IAM role"
  value       = aws_iam_role.metadata_service.arn
}

output "api_gateway_cloudwatch_role_arn" {
  description = "ARN of API Gateway CloudWatch logging role"
  value       = aws_iam_role.api_gateway_cloudwatch.arn
}

# ==============================================================================
# Account Information
# ==============================================================================

output "aws_account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}

# ==============================================================================
# Environment Information
# ==============================================================================

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}
