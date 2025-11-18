# Terraform Infrastructure for CompanyCam Photo Detection

This directory contains Terraform configurations for provisioning AWS infrastructure.

## Quick Start

```bash
# 1. Initialize Terraform
terraform init

# 2. Create environment variables file
cp terraform.tfvars.example dev.tfvars
# Edit dev.tfvars with your values

# 3. Plan deployment
terraform plan -var-file=dev.tfvars

# 4. Apply infrastructure
terraform apply -var-file=dev.tfvars
```

## File Structure

```
terraform/
├── main.tf              # Provider and backend configuration
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── vpc.tf              # VPC, subnets, security groups
├── s3.tf               # S3 bucket for photo storage
├── api-gateway.tf      # API Gateway configuration
├── redis.tf            # ElastiCache Redis cluster
├── cloudwatch.tf       # CloudWatch logs and monitoring
├── iam.tf              # IAM roles and policies
├── lambda/             # Lambda functions
│   ├── jwt-authorizer.js
│   └── README.md
├── .gitignore          # Git ignore patterns
├── terraform.tfvars.example  # Example variables file
└── README.md           # This file
```

## Configuration Files

### main.tf
- AWS provider configuration
- Terraform backend (S3 + DynamoDB)
- Common data sources

### variables.tf
- All input variables with descriptions and defaults
- Validation rules for environment values

### outputs.tf
- Export important resource IDs and endpoints
- Used by other services and CI/CD pipelines

### vpc.tf
- VPC with public and private subnets
- NAT gateways for private subnet internet access
- Security groups for ALB, backend services, RDS, Redis
- VPC Flow Logs for auditing

### s3.tf
- S3 bucket for photo storage
- Versioning, encryption (AES-256), lifecycle policies
- CORS configuration for client uploads
- Bucket policy for IAM role-based access
- Separate bucket for access logs

### api-gateway.tf
- HTTP API Gateway (API Gateway v2)
- JWT authorizer for authentication
- Lambda authorizer for custom auth logic
- CORS configuration
- Access logging to CloudWatch
- VPC Link for private integrations

### redis.tf
- ElastiCache Redis cluster
- Parameter group with optimized settings
- CloudWatch alarms for CPU, memory, evictions
- Subnet group for private subnet deployment

### cloudwatch.tf
- Log groups for all services
- Metric filters for error tracking
- CloudWatch alarms for critical metrics
- CloudWatch Dashboard
- X-Ray sampling rules

### iam.tf
- Service-specific IAM roles
- Least privilege policies
- Task execution role for ECS
- API Gateway CloudWatch logging role

## Environment Variables

Create a `<environment>.tfvars` file with these required variables:

```hcl
environment = "dev"  # dev, staging, or prod
aws_region  = "us-east-1"

# VPC Configuration
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]

# Redis Configuration
redis_node_type       = "cache.t3.micro"  # Use cache.r6g.xlarge for prod
redis_num_cache_nodes = 1                 # Use 3+ for prod

# CloudWatch
cloudwatch_retention_days = 30  # Use 90 for prod
```

## Important Outputs

After applying Terraform, these outputs are available:

```bash
# VPC
terraform output vpc_id
terraform output public_subnet_ids
terraform output private_subnet_ids

# S3
terraform output s3_bucket_name
terraform output s3_bucket_arn

# API Gateway
terraform output api_gateway_endpoint
terraform output api_gateway_stage_invoke_url

# Redis
terraform output redis_endpoint
terraform output redis_connection_string

# IAM
terraform output photo_upload_service_role_arn
terraform output detection_service_role_arn
terraform output metadata_service_role_arn
```

## State Management

Terraform state is stored in S3 with DynamoDB locking:

- **Bucket**: `companycam-terraform-state`
- **Key**: `photo-detection/terraform.tfstate`
- **Lock Table**: `terraform-state-lock`

**Important**: Never commit `terraform.tfstate` files to version control.

## Workspaces

Use Terraform workspaces for environment isolation:

```bash
# Create workspace
terraform workspace new dev

# List workspaces
terraform workspace list

# Switch workspace
terraform workspace select dev

# Show current workspace
terraform workspace show
```

## Common Commands

```bash
# Format Terraform files
terraform fmt -recursive

# Validate configuration
terraform validate

# Show current state
terraform show

# List resources
terraform state list

# Show specific resource
terraform state show aws_s3_bucket.photos

# Refresh state from AWS
terraform refresh -var-file=dev.tfvars

# Import existing resource
terraform import aws_vpc.main vpc-xxxxx

# Generate dependency graph
terraform graph | dot -Tpng > graph.png
```

## Deployment Workflow

### Development
```bash
terraform workspace select dev
terraform plan -var-file=dev.tfvars -out=tfplan
terraform apply tfplan
```

### Staging
```bash
terraform workspace select staging
terraform plan -var-file=staging.tfvars -out=tfplan
terraform apply tfplan
```

### Production
```bash
terraform workspace select prod
terraform plan -var-file=prod.tfvars -out=tfplan
# Review plan carefully
terraform apply tfplan
```

## Pre-Deployment Checklist

Before deploying to production:

- [ ] Review all variable values in `prod.tfvars`
- [ ] Ensure proper Redis instance size (cache.r6g.xlarge minimum)
- [ ] Set Redis nodes to 3+ for high availability
- [ ] Configure CloudWatch retention to 90 days
- [ ] Enable S3 bucket encryption at rest and in transit
- [ ] Enable Redis encryption at rest and in transit
- [ ] Set up SNS topics for CloudWatch alarms
- [ ] Configure backup and retention policies
- [ ] Review IAM policies for least privilege
- [ ] Build and upload Lambda authorizer package
- [ ] Test in staging environment first

## Lambda Authorizer Setup

Build the Lambda package before deploying:

```bash
cd lambda
npm install jsonwebtoken
zip -r jwt-authorizer.zip jwt-authorizer.js node_modules/
cd ..
terraform apply -var-file=dev.tfvars
```

## Troubleshooting

### Issue: Terraform state lock

```bash
# List locks
aws dynamodb scan --table-name terraform-state-lock

# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
```

### Issue: Lambda deployment fails

```bash
# Rebuild Lambda package
cd lambda && npm install && zip -r jwt-authorizer.zip jwt-authorizer.js node_modules/ && cd ..

# Apply with lifecycle ignore
terraform apply -var-file=dev.tfvars
```

### Issue: Resource already exists

```bash
# Import existing resource
terraform import <resource_type>.<resource_name> <resource_id>

# Example
terraform import aws_s3_bucket.photos companycam-photos-dev
```

## Security Considerations

- All secrets should be stored in AWS Secrets Manager
- Enable MFA for AWS console access
- Use IAM roles instead of access keys
- Enable S3 bucket versioning and encryption
- Enable VPC Flow Logs for auditing
- Use private subnets for backend services
- Block all public S3 access
- Enable CloudTrail for API auditing

## Cost Optimization

- Use `t3.micro` instances for dev/staging
- Reduce CloudWatch log retention in non-prod
- Use single NAT Gateway for dev
- Enable S3 Intelligent Tiering
- Delete unused snapshots and volumes
- Schedule non-prod environments to shut down overnight

## Documentation

See [TERRAFORM_SETUP.md](../TERRAFORM_SETUP.md) for detailed setup instructions, troubleshooting, and disaster recovery procedures.

## Support

For questions or issues:
- Check [TERRAFORM_SETUP.md](../TERRAFORM_SETUP.md) troubleshooting section
- Review Terraform AWS Provider docs
- Contact DevOps team
