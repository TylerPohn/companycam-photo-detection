# S3 Photo Storage Configuration for CompanyCam Photo Detection

# ==============================================================================
# S3 Bucket for Photo Storage
# ==============================================================================

resource "aws_s3_bucket" "photos" {
  bucket = "${var.s3_bucket_prefix}-${var.environment}"

  tags = {
    Name        = "${var.s3_bucket_prefix}-${var.environment}"
    Description = "Photo storage bucket for CompanyCam photo detection system"
  }
}

# ==============================================================================
# S3 Bucket Versioning
# ==============================================================================

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id

  versioning_configuration {
    status = var.s3_versioning_enabled ? "Enabled" : "Disabled"
  }
}

# ==============================================================================
# S3 Bucket Encryption (AES-256)
# ==============================================================================

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# ==============================================================================
# S3 Bucket Public Access Block (Block all public access)
# ==============================================================================

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket = aws_s3_bucket.photos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ==============================================================================
# S3 Bucket Lifecycle Configuration
# ==============================================================================

resource "aws_s3_bucket_lifecycle_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  # Rule 1: Transition original photos to Glacier after 90 days
  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    filter {
      prefix = "photos/"
    }

    transition {
      days          = var.s3_lifecycle_glacier_days
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = var.s3_lifecycle_glacier_days
      storage_class   = "GLACIER"
    }
  }

  # Rule 2: Delete temporary processing files after 30 days
  rule {
    id     = "expire-temporary-files"
    status = "Enabled"

    filter {
      prefix = "temp/"
    }

    expiration {
      days = var.s3_lifecycle_temp_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.s3_lifecycle_temp_expiration_days
    }
  }

  # Rule 3: Delete depth maps after 30 days
  rule {
    id     = "expire-depth-maps"
    status = "Enabled"

    filter {
      prefix = "depth-maps/"
    }

    expiration {
      days = var.s3_lifecycle_temp_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.s3_lifecycle_temp_expiration_days
    }
  }

  # Rule 4: Clean up incomplete multipart uploads after 7 days
  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ==============================================================================
# S3 Bucket CORS Configuration
# ==============================================================================

resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST", "PUT"]
    allowed_origins = var.allowed_cors_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }

  cors_rule {
    allowed_headers = ["Authorization"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.allowed_cors_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# ==============================================================================
# S3 Bucket Policy (IAM Role-based Access)
# ==============================================================================

resource "aws_s3_bucket_policy" "photos" {
  bucket = aws_s3_bucket.photos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPhotoUploadServiceAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.photo_upload_service.arn
        }
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.photos.arn}/*"
      },
      {
        Sid    = "AllowDetectionServiceReadAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.detection_service.arn
        }
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.photos.arn,
          "${aws_s3_bucket.photos.arn}/*"
        ]
      },
      {
        Sid    = "DenyInsecureTransport"
        Effect = "Deny"
        Principal = {
          AWS = "*"
        }
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.photos.arn,
          "${aws_s3_bucket.photos.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

  depends_on = [
    aws_iam_role.photo_upload_service,
    aws_iam_role.detection_service
  ]
}

# ==============================================================================
# S3 Bucket Intelligent-Tiering Configuration (Optional for cost optimization)
# ==============================================================================

resource "aws_s3_bucket_intelligent_tiering_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# ==============================================================================
# S3 Bucket Logging (for audit trail)
# ==============================================================================

resource "aws_s3_bucket" "logs" {
  bucket = "${var.s3_bucket_prefix}-logs-${var.environment}"

  tags = {
    Name        = "${var.s3_bucket_prefix}-logs-${var.environment}"
    Description = "Access logs for photo storage bucket"
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_logging" "photos" {
  bucket = aws_s3_bucket.photos.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "access-logs/"
}
