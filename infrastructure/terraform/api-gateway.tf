# API Gateway Configuration for CompanyCam Photo Detection

# ==============================================================================
# HTTP API Gateway (API Gateway v2)
# ==============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.api_gateway_name}-${var.environment}"
  protocol_type = "HTTP"
  description   = "API Gateway for CompanyCam Photo Detection System"

  cors_configuration {
    allow_origins = var.allowed_cors_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = [
      "Authorization",
      "Content-Type",
      "X-Amz-Date",
      "X-Api-Key",
      "X-Amz-Security-Token",
      "X-Requested-With"
    ]
    expose_headers = [
      "X-Request-Id",
      "X-Rate-Limit-Limit",
      "X-Rate-Limit-Remaining"
    ]
    max_age = 300
  }

  tags = {
    Name = "${var.api_gateway_name}-${var.environment}"
  }
}

# ==============================================================================
# API Gateway Stage
# ==============================================================================

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.api_gateway_stage_name
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
      integrationErrorMessage = "$context.integrationErrorMessage"
    })
  }

  default_route_settings {
    throttle_burst_limit = var.api_throttle_burst_limit
    throttle_rate_limit  = var.api_throttle_rate_limit
    detailed_metrics_enabled = var.enable_detailed_monitoring
  }

  tags = {
    Name = "${var.api_gateway_name}-${var.api_gateway_stage_name}-${var.environment}"
  }

  depends_on = [aws_cloudwatch_log_group.api_gateway]
}

# ==============================================================================
# JWT Authorizer for API Gateway
# ==============================================================================

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.project_name}-jwt-authorizer-${var.environment}"

  jwt_configuration {
    # This should be configured with your actual JWT issuer and audience
    # For now, using placeholders - replace with actual values from Auth0, Cognito, etc.
    audience = ["companycam-api"]
    issuer   = "https://auth.companycam.com"
  }
}

# ==============================================================================
# Lambda Authorizer (Alternative to JWT for custom authentication logic)
# ==============================================================================

# Create Lambda function for JWT validation
resource "aws_lambda_function" "jwt_authorizer" {
  filename      = "${path.module}/lambda/jwt-authorizer.zip"
  function_name = "${var.project_name}-jwt-authorizer-${var.environment}"
  role          = aws_iam_role.lambda_authorizer.arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"
  timeout       = 10

  environment {
    variables = {
      JWT_SECRET = "REPLACE_WITH_SECRET_MANAGER_REFERENCE"
      AUDIENCE   = "companycam-api"
      ISSUER     = "https://auth.companycam.com"
    }
  }

  tags = {
    Name = "${var.project_name}-jwt-authorizer-${var.environment}"
  }

  # This will fail initially because the Lambda zip doesn't exist yet
  # Uncomment lifecycle to prevent errors during initial terraform apply
  lifecycle {
    ignore_changes = [filename]
  }
}

# Lambda authorizer integration with API Gateway
resource "aws_apigatewayv2_authorizer" "lambda" {
  api_id                            = aws_apigatewayv2_api.main.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = aws_lambda_function.jwt_authorizer.invoke_arn
  identity_sources                  = ["$request.header.Authorization"]
  name                              = "${var.project_name}-lambda-authorizer-${var.environment}"
  authorizer_payload_format_version = "2.0"
  enable_simple_responses           = true
  authorizer_result_ttl_in_seconds  = 300
}

# ==============================================================================
# Example API Routes (placeholders for backend integrations)
# ==============================================================================

# Health check route (no authentication)
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

resource "aws_apigatewayv2_integration" "health" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "HTTP_PROXY"
  integration_uri  = "http://example.com/health" # Replace with actual backend URL

  integration_method = "GET"
  payload_format_version = "1.0"
}

# Photo upload route (requires authentication)
resource "aws_apigatewayv2_route" "upload_photo" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /v1/photos/upload"
  target    = "integrations/${aws_apigatewayv2_integration.upload_photo.id}"

  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.lambda.id
}

resource "aws_apigatewayv2_integration" "upload_photo" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "HTTP_PROXY"
  integration_uri  = "http://example.com/upload" # Replace with actual backend URL

  integration_method = "POST"
  payload_format_version = "1.0"
}

# Detection route (requires authentication, lower rate limit)
resource "aws_apigatewayv2_route" "detect" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /v1/detect"
  target    = "integrations/${aws_apigatewayv2_integration.detect.id}"

  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.lambda.id
}

resource "aws_apigatewayv2_integration" "detect" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "HTTP_PROXY"
  integration_uri  = "http://example.com/detect" # Replace with actual backend URL

  integration_method = "POST"
  payload_format_version = "1.0"
}

# ==============================================================================
# VPC Link for Private Integration (if backend services are in VPC)
# ==============================================================================

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${var.project_name}-vpc-link-${var.environment}"
  security_group_ids = [aws_security_group.backend_services.id]
  subnet_ids         = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-vpc-link-${var.environment}"
  }
}

# ==============================================================================
# IAM Role for Lambda Authorizer
# ==============================================================================

resource "aws_iam_role" "lambda_authorizer" {
  name = "${var.project_name}-lambda-authorizer-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-authorizer-role-${var.environment}"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_authorizer_basic" {
  role       = aws_iam_role.lambda_authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow API Gateway to invoke Lambda authorizer
resource "aws_lambda_permission" "api_gateway_invoke_authorizer" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.jwt_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# ==============================================================================
# API Gateway Account Settings (for CloudWatch logging)
# ==============================================================================

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}
