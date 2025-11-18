# IAM Roles and Policies for CompanyCam Photo Detection

# ==============================================================================
# Photo Upload Service IAM Role
# ==============================================================================

resource "aws_iam_role" "photo_upload_service" {
  name = "${var.project_name}-photo-upload-service-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "${var.project_name}-photo-upload-service-role-${var.environment}"
    Service = "Photo Upload Service"
  }
}

# S3 Access Policy for Photo Upload Service
resource "aws_iam_role_policy" "photo_upload_s3" {
  name = "${var.project_name}-photo-upload-s3-policy-${var.environment}"
  role = aws_iam_role.photo_upload_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:PutObjectAcl",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.photos.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.photos.arn
      }
    ]
  })
}

# CloudWatch Logs Policy for Photo Upload Service
resource "aws_iam_role_policy" "photo_upload_cloudwatch" {
  name = "${var.project_name}-photo-upload-cloudwatch-policy-${var.environment}"
  role = aws_iam_role.photo_upload_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.photo_upload.arn}:*"
      }
    ]
  })
}

# X-Ray Tracing Policy for Photo Upload Service
resource "aws_iam_role_policy" "photo_upload_xray" {
  name = "${var.project_name}-photo-upload-xray-policy-${var.environment}"
  role = aws_iam_role.photo_upload_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# ==============================================================================
# Detection Service IAM Role
# ==============================================================================

resource "aws_iam_role" "detection_service" {
  name = "${var.project_name}-detection-service-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "${var.project_name}-detection-service-role-${var.environment}"
    Service = "Detection Service"
  }
}

# S3 Read Access Policy for Detection Service
resource "aws_iam_role_policy" "detection_s3" {
  name = "${var.project_name}-detection-s3-policy-${var.environment}"
  role = aws_iam_role.detection_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.photos.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.photos.arn
      }
    ]
  })
}

# CloudWatch Logs Policy for Detection Service
resource "aws_iam_role_policy" "detection_cloudwatch" {
  name = "${var.project_name}-detection-cloudwatch-policy-${var.environment}"
  role = aws_iam_role.detection_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.detection.arn}:*"
      }
    ]
  })
}

# X-Ray Tracing Policy for Detection Service
resource "aws_iam_role_policy" "detection_xray" {
  name = "${var.project_name}-detection-xray-policy-${var.environment}"
  role = aws_iam_role.detection_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# SageMaker Inference Access (for ML model invocation)
resource "aws_iam_role_policy" "detection_sagemaker" {
  name = "${var.project_name}-detection-sagemaker-policy-${var.environment}"
  role = aws_iam_role.detection_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:InvokeEndpoint"
        ]
        Resource = "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:endpoint/*"
      }
    ]
  })
}

# ==============================================================================
# Metadata Service IAM Role
# ==============================================================================

resource "aws_iam_role" "metadata_service" {
  name = "${var.project_name}-metadata-service-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "${var.project_name}-metadata-service-role-${var.environment}"
    Service = "Metadata Service"
  }
}

# CloudWatch Logs Policy for Metadata Service
resource "aws_iam_role_policy" "metadata_cloudwatch" {
  name = "${var.project_name}-metadata-cloudwatch-policy-${var.environment}"
  role = aws_iam_role.metadata_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.metadata.arn}:*"
      }
    ]
  })
}

# X-Ray Tracing Policy for Metadata Service
resource "aws_iam_role_policy" "metadata_xray" {
  name = "${var.project_name}-metadata-xray-policy-${var.environment}"
  role = aws_iam_role.metadata_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# ==============================================================================
# API Gateway CloudWatch Logging Role
# ==============================================================================

resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-api-gateway-cloudwatch-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-api-gateway-cloudwatch-role-${var.environment}"
  }
}

resource "aws_iam_role_policy" "api_gateway_cloudwatch" {
  name = "${var.project_name}-api-gateway-cloudwatch-policy-${var.environment}"
  role = aws_iam_role.api_gateway_cloudwatch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:FilterLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# ==============================================================================
# ECS Task Execution Role (for pulling container images and writing logs)
# ==============================================================================

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-execution-role-${var.environment}"
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for accessing Secrets Manager (for sensitive configuration)
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${var.project_name}-ecs-task-execution-secrets-policy-${var.environment}"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:key/*"
      }
    ]
  })
}

# ==============================================================================
# Cross-Account Access Role (for SageMaker in separate account - optional)
# ==============================================================================

# Uncomment if using SageMaker in a separate AWS account
# resource "aws_iam_role" "cross_account_sagemaker" {
#   name = "${var.project_name}-cross-account-sagemaker-role-${var.environment}"
#
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           AWS = "arn:aws:iam::${var.sagemaker_account_id}:root"
#         }
#       }
#     ]
#   })
#
#   tags = {
#     Name = "${var.project_name}-cross-account-sagemaker-role-${var.environment}"
#   }
# }
