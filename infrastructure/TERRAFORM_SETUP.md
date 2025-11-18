# Terraform Setup Guide for CompanyCam Photo Detection

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Deploying Infrastructure](#deploying-infrastructure)
5. [Environment Management](#environment-management)
6. [Resource Architecture](#resource-architecture)
7. [Troubleshooting](#troubleshooting)
8. [Disaster Recovery](#disaster-recovery)
9. [Cost Optimization](#cost-optimization)
10. [Security Best Practices](#security-best-practices)

---

## Overview

This Terraform configuration provisions the complete AWS infrastructure for the CompanyCam Photo Detection system, including:

- **VPC and Networking**: VPC, subnets, NAT gateways, security groups
- **S3 Storage**: Photo storage bucket with versioning, encryption, lifecycle policies
- **API Gateway**: HTTP API Gateway with JWT authentication and rate limiting
- **ElastiCache Redis**: Distributed caching layer
- **CloudWatch**: Logging, monitoring, and alerting
- **IAM**: Service roles and policies

---

## Prerequisites

### Required Tools

1. **Terraform** >= 1.5.0
   ```bash
   # macOS
   brew install terraform

   # Linux
   wget https://releases.hashicorp.com/terraform/1.5.0/terraform_1.5.0_linux_amd64.zip
   unzip terraform_1.5.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **AWS CLI** >= 2.0
   ```bash
   # macOS
   brew install awscli

   # Linux
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   ```

3. **jq** (for JSON parsing)
   ```bash
   # macOS
   brew install jq

   # Linux
   sudo apt-get install jq
   ```

### AWS Account Requirements

- AWS account with appropriate permissions
- IAM user/role with admin access or specific permissions:
  - VPC, EC2, S3, API Gateway, ElastiCache, CloudWatch, IAM, Lambda

### AWS Credentials Configuration

```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

---

## Initial Setup

### 1. Create Terraform State Backend

Before initializing Terraform, create the S3 backend for state management:

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://companycam-terraform-state --region us-east-1

# Enable versioning on state bucket
aws s3api put-bucket-versioning \
  --bucket companycam-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket companycam-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket companycam-terraform-state \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 2. Initialize Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform (downloads providers, sets up backend)
terraform init

# Validate configuration
terraform validate
```

### 3. Create Environment-Specific Variables File

```bash
# Copy example file
cp terraform.tfvars.example dev.tfvars

# Edit with environment-specific values
vim dev.tfvars
```

**Example `dev.tfvars`:**
```hcl
environment              = "dev"
aws_region               = "us-east-1"
vpc_cidr                 = "10.0.0.0/16"
redis_node_type          = "cache.t3.micro"
redis_num_cache_nodes    = 1
cloudwatch_retention_days = 30
```

---

## Deploying Infrastructure

### Development Environment

```bash
cd infrastructure/terraform

# Preview changes
terraform plan -var-file=dev.tfvars -out=tfplan

# Apply changes
terraform apply tfplan

# Or combine plan and apply
terraform apply -var-file=dev.tfvars
```

### Staging Environment

```bash
# Create staging variables
cp dev.tfvars staging.tfvars
# Edit staging.tfvars with staging-specific values

# Deploy staging
terraform workspace new staging  # Create workspace
terraform workspace select staging
terraform apply -var-file=staging.tfvars
```

### Production Environment

```bash
# Create production variables
cp dev.tfvars prod.tfvars
# Edit prod.tfvars with production values:
# - Larger Redis instance (cache.r6g.xlarge)
# - Multiple Redis nodes (3+)
# - Longer log retention (90 days)
# - Enable encryption at rest and in transit

terraform workspace new prod
terraform workspace select prod
terraform apply -var-file=prod.tfvars
```

### Important Lambda Setup

Before applying Terraform, build the Lambda authorizer package:

```bash
cd lambda
npm install jsonwebtoken
zip -r jwt-authorizer.zip jwt-authorizer.js node_modules/
cd ..
```

---

## Environment Management

### Viewing Current Infrastructure

```bash
# Show current state
terraform show

# List all resources
terraform state list

# Get specific resource details
terraform state show aws_s3_bucket.photos

# View outputs
terraform output
terraform output s3_bucket_name
```

### Updating Infrastructure

```bash
# Make changes to .tf files
vim vpc.tf

# Preview changes
terraform plan -var-file=dev.tfvars

# Apply changes
terraform apply -var-file=dev.tfvars
```

### Destroying Infrastructure

```bash
# Destroy specific resource
terraform destroy -target=aws_elasticache_cluster.redis -var-file=dev.tfvars

# Destroy entire environment (DANGEROUS!)
terraform destroy -var-file=dev.tfvars
```

---

## Resource Architecture

### VPC Layout

```
VPC: 10.0.0.0/16
├── Public Subnets (2)
│   ├── 10.0.1.0/24 (us-east-1a) - ALB, NAT Gateway
│   └── 10.0.2.0/24 (us-east-1b) - ALB, NAT Gateway
└── Private Subnets (4)
    ├── 10.0.10.0/24 (us-east-1a) - Backend Services
    ├── 10.0.11.0/24 (us-east-1b) - Backend Services
    ├── 10.0.12.0/24 (us-east-1a) - RDS, Redis
    └── 10.0.13.0/24 (us-east-1b) - RDS, Redis
```

### Security Group Rules

| Security Group | Inbound | Outbound |
|----------------|---------|----------|
| ALB | HTTP (80), HTTPS (443) from 0.0.0.0/0 | All |
| Backend Services | All from ALB SG, Inter-service | All |
| RDS | PostgreSQL (5432) from Backend SG | All |
| Redis | Redis (6379) from Backend SG | All |

### S3 Bucket Structure

```
companycam-photos-{env}/
├── photos/           # Original uploaded photos
├── temp/             # Temporary processing files (deleted after 30 days)
├── depth-maps/       # Generated depth maps (deleted after 30 days)
└── thumbnails/       # Generated thumbnails
```

---

## Troubleshooting

### Common Issues

#### 1. Terraform State Lock

**Problem**: `Error acquiring the state lock`

**Solution**:
```bash
# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>

# Check DynamoDB for locks
aws dynamodb scan --table-name terraform-state-lock
```

#### 2. Lambda Authorizer Errors

**Problem**: Lambda function fails to deploy

**Solution**:
```bash
# Ensure Lambda package exists
ls -lh lambda/jwt-authorizer.zip

# If missing, rebuild:
cd lambda
npm install jsonwebtoken
zip -r jwt-authorizer.zip jwt-authorizer.js node_modules/
cd ..

# Apply with ignore changes
terraform apply -var-file=dev.tfvars
```

#### 3. API Gateway 403 Errors

**Problem**: All API requests return 403 Forbidden

**Checklist**:
- Verify JWT token is valid
- Check Lambda authorizer CloudWatch logs
- Ensure authorizer is attached to routes
- Verify CORS configuration

```bash
# Check Lambda logs
aws logs tail /aws/lambda/companycam-photo-detection-jwt-authorizer-dev --follow
```

#### 4. Redis Connection Timeouts

**Problem**: Backend services cannot connect to Redis

**Checklist**:
- Verify security group allows traffic on port 6379
- Ensure services are in same VPC
- Check Redis cluster status

```bash
# Get Redis endpoint
terraform output redis_endpoint

# Test connectivity from EC2 in same VPC
redis-cli -h <redis-endpoint> -p 6379 ping
```

#### 5. S3 Upload Failures

**Problem**: Pre-signed URLs fail to upload

**Checklist**:
- Verify CORS configuration
- Check IAM role permissions
- Ensure bucket encryption settings don't conflict

```bash
# Check bucket CORS
aws s3api get-bucket-cors --bucket companycam-photos-dev

# Test pre-signed URL generation
aws s3 presign s3://companycam-photos-dev/test.jpg --expires-in 3600
```

---

## Disaster Recovery

### Backup Procedures

#### 1. Terraform State Backup

```bash
# State is automatically versioned in S3
# To manually backup:
terraform state pull > terraform-state-backup-$(date +%Y%m%d).json
```

#### 2. S3 Bucket Backup

```bash
# Enable cross-region replication (CRR)
# Add to s3.tf:

resource "aws_s3_bucket_replication_configuration" "photos_replication" {
  # Configuration for disaster recovery bucket
}
```

#### 3. Redis Backup

```bash
# Manual snapshot
aws elasticache create-snapshot \
  --cache-cluster-id companycam-photo-detection-redis-dev \
  --snapshot-name manual-backup-$(date +%Y%m%d)

# Restore from snapshot
aws elasticache create-cache-cluster \
  --cache-cluster-id companycam-redis-restored \
  --snapshot-name manual-backup-20250117
```

### Recovery Procedures

#### Complete Infrastructure Recovery

```bash
# 1. Ensure state backend is accessible
aws s3 ls s3://companycam-terraform-state/

# 2. Initialize Terraform
terraform init

# 3. Import existing resources (if state is lost)
terraform import aws_vpc.main vpc-xxxxx

# 4. Recreate infrastructure
terraform apply -var-file=prod.tfvars
```

---

## Cost Optimization

### Estimated Monthly Costs (Development)

| Resource | Cost |
|----------|------|
| VPC (NAT Gateways) | ~$65/month |
| S3 Storage (100GB) | ~$2.30/month |
| S3 Requests | ~$0.50/month |
| API Gateway (1M requests) | ~$3.50/month |
| ElastiCache (t3.micro) | ~$12/month |
| CloudWatch Logs (10GB) | ~$5/month |
| **Total** | **~$88/month** |

### Cost Reduction Tips

1. **Use Single NAT Gateway for Dev**: Reduce from 2 to 1
2. **Enable S3 Intelligent Tiering**: Automatic cost optimization
3. **Reduce CloudWatch Retention**: 7 days for dev instead of 30
4. **Use Spot Instances**: For non-critical workloads
5. **Schedule Resources**: Shut down dev/staging during off-hours

```bash
# Example: Reduce NAT gateways for dev
# In dev.tfvars:
enable_nat_gateway = false  # Use single NAT or none for dev
```

---

## Security Best Practices

### 1. Secrets Management

Never commit secrets to version control. Use AWS Secrets Manager:

```bash
# Store JWT secret
aws secretsmanager create-secret \
  --name companycam-photo-detection/jwt-secret \
  --secret-string '{"secret":"your-secret-here"}'

# Update Lambda to use Secrets Manager
# See lambda/jwt-authorizer.js for implementation
```

### 2. Encryption

- S3: AES-256 encryption enabled by default
- Redis: Enable at-rest and in-transit encryption for production
- RDS: Enable encryption at rest
- CloudWatch Logs: Encrypt with KMS

### 3. Network Security

- All backend services in private subnets
- No public IPs on backend services
- Security groups follow principle of least privilege
- VPC Flow Logs enabled for auditing

### 4. IAM Best Practices

- Use service-specific roles
- Follow least privilege principle
- Enable MFA for human users
- Rotate access keys regularly
- Use IAM roles for EC2/ECS, not access keys

### 5. Monitoring and Alerting

```bash
# Set up SNS topic for alerts
aws sns create-topic --name companycam-alerts
aws sns subscribe --topic-arn <topic-arn> --protocol email --notification-endpoint devops@companycam.com

# Update CloudWatch alarms to use SNS
# See cloudwatch.tf for alarm configurations
```

---

## Manual Verification Steps

After deploying infrastructure, verify each component:

### 1. VPC and Networking

```bash
# Check VPC
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=companycam-photo-detection-vpc-dev"

# Check subnets
aws ec2 describe-subnets --filters "Name=vpc-id,Values=<vpc-id>"

# Check NAT gateways
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=<vpc-id>"
```

### 2. S3 Bucket

```bash
# Test pre-signed URL generation (requires AWS SDK in your backend service)
# Example with AWS CLI:
aws s3 presign s3://companycam-photos-dev/test.jpg --expires-in 3600

# Upload test file
echo "test" > test.txt
aws s3 cp test.txt s3://companycam-photos-dev/photos/test.txt

# Verify CORS
curl -H "Origin: https://app.companycam.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://companycam-photos-dev.s3.amazonaws.com
```

### 3. API Gateway

```bash
# Get API Gateway URL
terraform output api_gateway_stage_invoke_url

# Test health endpoint (no auth required)
curl https://<api-id>.execute-api.us-east-1.amazonaws.com/v1/health

# Test authenticated endpoint (requires valid JWT)
curl -H "Authorization: Bearer <jwt-token>" \
     https://<api-id>.execute-api.us-east-1.amazonaws.com/v1/photos/upload
```

### 4. Redis

```bash
# Get Redis endpoint
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)

# Test from EC2 instance in same VPC
redis-cli -h $REDIS_ENDPOINT -p 6379 ping
# Expected: PONG

# Set and get test value
redis-cli -h $REDIS_ENDPOINT -p 6379 SET test "hello"
redis-cli -h $REDIS_ENDPOINT -p 6379 GET test
# Expected: "hello"
```

### 5. CloudWatch Logs

```bash
# Check log groups
aws logs describe-log-groups --log-group-name-prefix /aws/apigateway/companycam

# Tail API Gateway logs
aws logs tail /aws/apigateway/companycam-api-dev --follow
```

---

## Next Steps

1. **Deploy Backend Services**: Use ECS/Kubernetes to deploy microservices
2. **Configure Auth Service**: Set up JWT issuer (Auth0, Cognito, custom)
3. **Set Up CI/CD**: Automate Terraform deployments with GitHub Actions
4. **Configure Monitoring**: Set up dashboards and alerts in CloudWatch
5. **Load Testing**: Test API Gateway and backend services under load

---

## Support and Resources

- **Terraform AWS Provider Docs**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **AWS Best Practices**: https://aws.amazon.com/architecture/well-architected/
- **Project Repository**: https://github.com/companycam/photo-detection

For issues or questions, contact the DevOps team.
