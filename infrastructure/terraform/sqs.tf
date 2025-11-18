# SQS Queues for Photo Detection Processing
# Implements 3 priority levels (high, normal, low) with Dead Letter Queues

locals {
  queue_priorities = ["high", "normal", "low"]

  # Queue configuration
  message_retention_seconds = 1209600  # 14 days
  visibility_timeout_seconds = 300      # 5 minutes
  max_receive_count = 4                # Move to DLQ after 4 attempts
  receive_wait_time_seconds = 20       # Long polling enabled
}

# Dead Letter Queues - must be created first
resource "aws_sqs_queue" "photo_detection_dlq" {
  for_each = toset(local.queue_priorities)

  name                      = "companycam-photos-${each.key}-priority-dlq-${var.environment}"
  message_retention_seconds = local.message_retention_seconds

  tags = {
    Name        = "CompanyCam Photo Detection DLQ - ${title(each.key)} Priority"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Priority    = each.key
    Type        = "DeadLetterQueue"
  }
}

# Main Priority Queues
resource "aws_sqs_queue" "photo_detection_queue" {
  for_each = toset(local.queue_priorities)

  name                       = "companycam-photos-${each.key}-priority-${var.environment}"
  message_retention_seconds  = local.message_retention_seconds
  visibility_timeout_seconds = local.visibility_timeout_seconds
  receive_wait_time_seconds  = local.receive_wait_time_seconds
  max_message_size          = 262144  # 256 KB

  # Enable content-based deduplication for FIFO-like behavior
  # Note: Standard queues don't support deduplication, but we can add message attributes

  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.photo_detection_dlq[each.key].arn
    maxReceiveCount     = local.max_receive_count
  })

  tags = {
    Name        = "CompanyCam Photo Detection Queue - ${title(each.key)} Priority"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Priority    = each.key
    Type        = "MainQueue"
  }
}

# IAM Policy for Queue Access
resource "aws_iam_policy" "sqs_queue_access" {
  name        = "companycam-sqs-queue-access-${var.environment}"
  description = "Policy for accessing CompanyCam photo detection SQS queues"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
        ]
        Resource = concat(
          [for q in aws_sqs_queue.photo_detection_queue : q.arn],
          [for q in aws_sqs_queue.photo_detection_dlq : q.arn]
        )
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ListQueues",
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "CompanyCam SQS Queue Access Policy"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# CloudWatch Alarms for Queue Monitoring

# Alarm: High queue depth (> 1000 messages)
resource "aws_cloudwatch_metric_alarm" "queue_depth_high" {
  for_each = toset(local.queue_priorities)

  alarm_name          = "companycam-photos-${each.key}-queue-depth-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"  # 5 minutes
  statistic           = "Average"
  threshold           = "1000"
  alarm_description   = "This metric monitors ${each.key} priority queue depth"
  alarm_actions       = []  # Add SNS topic ARN for notifications

  dimensions = {
    QueueName = aws_sqs_queue.photo_detection_queue[each.key].name
  }

  tags = {
    Name        = "Queue Depth High - ${title(each.key)} Priority"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Priority    = each.key
  }
}

# Alarm: Messages in DLQ (> 10 messages)
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  for_each = toset(local.queue_priorities)

  alarm_name          = "companycam-photos-${each.key}-dlq-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "60"  # 1 minute
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors messages in ${each.key} priority DLQ"
  alarm_actions       = []  # Add SNS topic ARN for notifications
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.photo_detection_dlq[each.key].name
  }

  tags = {
    Name        = "DLQ Messages - ${title(each.key)} Priority"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Priority    = each.key
  }
}

# Alarm: Old messages in queue (age > 5 minutes)
resource "aws_cloudwatch_metric_alarm" "message_age_high" {
  for_each = toset(local.queue_priorities)

  alarm_name          = "companycam-photos-${each.key}-message-age-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "300"  # 5 minutes
  statistic           = "Maximum"
  threshold           = "300"  # 5 minutes in seconds
  alarm_description   = "This metric monitors message age in ${each.key} priority queue"
  alarm_actions       = []  # Add SNS topic ARN for notifications

  dimensions = {
    QueueName = aws_sqs_queue.photo_detection_queue[each.key].name
  }

  tags = {
    Name        = "Message Age High - ${title(each.key)} Priority"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Priority    = each.key
  }
}

# Outputs
output "sqs_queue_urls" {
  description = "URLs of the SQS priority queues"
  value = {
    for priority in local.queue_priorities :
    priority => aws_sqs_queue.photo_detection_queue[priority].url
  }
}

output "sqs_queue_arns" {
  description = "ARNs of the SQS priority queues"
  value = {
    for priority in local.queue_priorities :
    priority => aws_sqs_queue.photo_detection_queue[priority].arn
  }
}

output "sqs_dlq_urls" {
  description = "URLs of the SQS Dead Letter Queues"
  value = {
    for priority in local.queue_priorities :
    priority => aws_sqs_queue.photo_detection_dlq[priority].url
  }
}

output "sqs_queue_policy_arn" {
  description = "ARN of the SQS queue access policy"
  value       = aws_iam_policy.sqs_queue_access.arn
}
