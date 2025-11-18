# CompanyCam Photo Detection - AWS Infrastructure
# Main Terraform Configuration

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # S3 backend for state management with DynamoDB locking
  # To initialize: terraform init -backend-config="bucket=companycam-terraform-state-${env}"
  backend "s3" {
    bucket         = "companycam-terraform-state"
    key            = "photo-detection/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"

    # Prevent accidental state file deletion
    # lifecycle {
    #   prevent_destroy = true
    # }
  }
}

# AWS Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CompanyCam Photo Detection"
      ManagedBy   = "Terraform"
      Environment = var.environment
      Repository  = "companycam-photo-detection"
    }
  }
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for current AWS region
data "aws_region" "current" {}
