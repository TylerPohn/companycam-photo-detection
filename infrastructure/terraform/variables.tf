# Terraform Variables for CompanyCam Photo Detection Infrastructure

# ==============================================================================
# Environment Configuration
# ==============================================================================

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "companycam-photo-detection"
}

# ==============================================================================
# VPC Configuration
# ==============================================================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnet distribution"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnet internet access"
  type        = bool
  default     = true
}

# ==============================================================================
# S3 Configuration
# ==============================================================================

variable "s3_bucket_prefix" {
  description = "Prefix for S3 bucket name"
  type        = string
  default     = "companycam-photos"
}

variable "s3_lifecycle_glacier_days" {
  description = "Days before transitioning objects to Glacier"
  type        = number
  default     = 90
}

variable "s3_lifecycle_temp_expiration_days" {
  description = "Days before expiring temporary files"
  type        = number
  default     = 30
}

variable "s3_versioning_enabled" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "allowed_cors_origins" {
  description = "Allowed CORS origins for S3 bucket"
  type        = list(string)
  default = [
    "https://app.companycam.com",
    "https://mobile.companycam.com",
    "http://localhost:3000"
  ]
}

# ==============================================================================
# API Gateway Configuration
# ==============================================================================

variable "api_gateway_name" {
  description = "Name for API Gateway"
  type        = string
  default     = "companycam-api"
}

variable "api_gateway_stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "v1"
}

variable "api_rate_limit_general" {
  description = "General rate limit (requests per second per user)"
  type        = number
  default     = 100
}

variable "api_rate_limit_detection" {
  description = "Detection endpoint rate limit (requests per second per user)"
  type        = number
  default     = 10
}

variable "api_throttle_burst_limit" {
  description = "API Gateway burst limit"
  type        = number
  default     = 200
}

variable "api_throttle_rate_limit" {
  description = "API Gateway rate limit"
  type        = number
  default     = 100
}

# ==============================================================================
# Redis (ElastiCache) Configuration
# ==============================================================================

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro" # Override in prod with cache.r6g.xlarge
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes in cluster"
  type        = number
  default     = 1 # Override in prod with 3
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_parameter_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "redis_port" {
  description = "Redis port"
  type        = number
  default     = 6379
}

# ==============================================================================
# CloudWatch Configuration
# ==============================================================================

variable "cloudwatch_retention_days" {
  description = "CloudWatch log retention days"
  type        = number
  default     = 30 # Override in prod with 90
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring (1-minute granularity)"
  type        = bool
  default     = true
}

# ==============================================================================
# Tags
# ==============================================================================

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
