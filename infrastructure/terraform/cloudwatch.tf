# CloudWatch Logging and Monitoring Configuration for CompanyCam Photo Detection

# ==============================================================================
# CloudWatch Log Groups
# ==============================================================================

# API Gateway Log Group
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.api_gateway_name}-${var.environment}"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name        = "${var.project_name}-api-gateway-logs-${var.environment}"
    Service     = "API Gateway"
    Description = "Logs for API Gateway requests and responses"
  }
}

# Photo Upload Service Log Group
resource "aws_cloudwatch_log_group" "photo_upload" {
  name              = "/aws/ecs/${var.project_name}-photo-upload-service-${var.environment}"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name        = "${var.project_name}-photo-upload-logs-${var.environment}"
    Service     = "Photo Upload Service"
    Description = "Logs for photo upload microservice"
  }
}

# Detection Service Log Group
resource "aws_cloudwatch_log_group" "detection" {
  name              = "/aws/ecs/${var.project_name}-detection-service-${var.environment}"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name        = "${var.project_name}-detection-logs-${var.environment}"
    Service     = "Detection Service"
    Description = "Logs for object detection microservice"
  }
}

# Metadata Service Log Group
resource "aws_cloudwatch_log_group" "metadata" {
  name              = "/aws/ecs/${var.project_name}-metadata-service-${var.environment}"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name        = "${var.project_name}-metadata-logs-${var.environment}"
    Service     = "Metadata Service"
    Description = "Logs for metadata management microservice"
  }
}

# Lambda Authorizer Log Group
resource "aws_cloudwatch_log_group" "lambda_authorizer" {
  name              = "/aws/lambda/${var.project_name}-jwt-authorizer-${var.environment}"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name        = "${var.project_name}-lambda-authorizer-logs-${var.environment}"
    Service     = "Lambda Authorizer"
    Description = "Logs for JWT authorization Lambda function"
  }
}

# ==============================================================================
# CloudWatch Metric Filters
# ==============================================================================

# API Gateway Error Rate Filter
resource "aws_cloudwatch_log_metric_filter" "api_gateway_errors" {
  name           = "${var.project_name}-api-gateway-errors-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.api_gateway.name
  pattern        = "[..., status_code=5*, ...]"

  metric_transformation {
    name      = "APIGatewayServerErrors"
    namespace = "CompanyCam/PhotoDetection"
    value     = "1"
    unit      = "Count"
  }
}

# API Gateway 4xx Client Errors Filter
resource "aws_cloudwatch_log_metric_filter" "api_gateway_4xx" {
  name           = "${var.project_name}-api-gateway-4xx-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.api_gateway.name
  pattern        = "[..., status_code=4*, ...]"

  metric_transformation {
    name      = "APIGatewayClientErrors"
    namespace = "CompanyCam/PhotoDetection"
    value     = "1"
    unit      = "Count"
  }
}

# Photo Upload Service Error Filter
resource "aws_cloudwatch_log_metric_filter" "photo_upload_errors" {
  name           = "${var.project_name}-photo-upload-errors-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.photo_upload.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "PhotoUploadServiceErrors"
    namespace = "CompanyCam/PhotoDetection"
    value     = "1"
    unit      = "Count"
  }
}

# Detection Service Error Filter
resource "aws_cloudwatch_log_metric_filter" "detection_errors" {
  name           = "${var.project_name}-detection-errors-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.detection.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "DetectionServiceErrors"
    namespace = "CompanyCam/PhotoDetection"
    value     = "1"
    unit      = "Count"
  }
}

# ==============================================================================
# CloudWatch Alarms
# ==============================================================================

# API Gateway 5xx Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${var.project_name}-api-gateway-5xx-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Triggered when API Gateway 5xx errors exceed threshold"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
  }

  tags = {
    Name     = "${var.project_name}-api-gateway-5xx-alarm-${var.environment}"
    Severity = "High"
  }
}

# API Gateway Latency Alarm
resource "aws_cloudwatch_metric_alarm" "api_gateway_latency" {
  alarm_name          = "${var.project_name}-api-gateway-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000" # 5 seconds
  alarm_description   = "Triggered when API Gateway latency exceeds 5 seconds"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
  }

  tags = {
    Name     = "${var.project_name}-api-gateway-latency-alarm-${var.environment}"
    Severity = "Medium"
  }
}

# Lambda Authorizer Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_authorizer_errors" {
  alarm_name          = "${var.project_name}-lambda-authorizer-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Triggered when Lambda authorizer errors exceed threshold"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.jwt_authorizer.function_name
  }

  tags = {
    Name     = "${var.project_name}-lambda-authorizer-errors-alarm-${var.environment}"
    Severity = "High"
  }
}

# ==============================================================================
# CloudWatch Dashboard
# ==============================================================================

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "Total Requests" }],
            [".", "4XXError", { stat = "Sum", label = "4xx Errors" }],
            [".", "5XXError", { stat = "Sum", label = "5xx Errors" }]
          ]
          period = 300
          region = var.aws_region
          title  = "API Gateway Metrics"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Latency", { stat = "Average", label = "Average Latency" }],
            ["...", { stat = "p99", label = "p99 Latency" }]
          ]
          period = 300
          region = var.aws_region
          title  = "API Gateway Latency"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", { stat = "Average" }],
            [".", "DatabaseMemoryUsagePercentage", { stat = "Average" }],
            [".", "NetworkBytesIn", { stat = "Sum" }],
            [".", "NetworkBytesOut", { stat = "Sum" }]
          ]
          period = 300
          region = var.aws_region
          title  = "Redis Cluster Metrics"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '${aws_cloudwatch_log_group.api_gateway.name}' | fields @timestamp, status, httpMethod, routeKey | filter status >= 400 | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent API Errors"
        }
      }
    ]
  })
}

# ==============================================================================
# SNS Topic for Alerts (Optional - for production use)
# ==============================================================================

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts-${var.environment}"

  tags = {
    Name = "${var.project_name}-alerts-${var.environment}"
  }
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.environment == "prod" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "devops@companycam.com" # Replace with actual email
}

# ==============================================================================
# X-Ray Tracing Configuration (for distributed tracing)
# ==============================================================================

# Enable X-Ray tracing for API Gateway
resource "aws_apigatewayv2_stage" "main_xray" {
  # This is handled in api-gateway.tf, but adding X-Ray specific configuration here
  # X-Ray tracing is enabled by default for HTTP APIs
}

# X-Ray sampling rule
resource "aws_xray_sampling_rule" "main" {
  rule_name      = "${var.project_name}-sampling-rule-${var.environment}"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.05 # Sample 5% of requests
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  attributes = {
    Environment = var.environment
  }
}
