# Infrastructure

Infrastructure as Code (IaC) for AWS deployment and Kubernetes orchestration.

## Structure

- `terraform/` - Terraform configurations for AWS resources
  - VPC and networking
  - EKS cluster setup
  - RDS (PostgreSQL) and ElastiCache (Redis)
  - S3 buckets
  - IAM roles and policies

- `k8s/` - Kubernetes manifests
  - Service deployments
  - ConfigMaps and Secrets
  - Ingress rules
  - Horizontal Pod Autoscalers

## Deployment

See root README.md for deployment instructions.

## Environments

- Development (local Docker Compose)
- Staging (AWS EKS)
- Production (AWS EKS with blue/green deployment)
