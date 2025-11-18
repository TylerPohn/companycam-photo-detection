# ElastiCache Redis Configuration for CompanyCam Photo Detection

# ==============================================================================
# ElastiCache Subnet Group
# ==============================================================================

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet-group-${var.environment}"
  subnet_ids = aws_subnet.private[*].id

  description = "Subnet group for ElastiCache Redis cluster"

  tags = {
    Name = "${var.project_name}-redis-subnet-group-${var.environment}"
  }
}

# ==============================================================================
# ElastiCache Parameter Group
# ==============================================================================

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.project_name}-redis-params-${var.environment}"
  family = var.redis_parameter_family

  description = "Custom parameter group for Redis with optimized settings"

  # Eviction policy: Remove least recently used keys when memory limit is reached
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  # Enable keyspace notifications for cache events (optional)
  parameter {
    name  = "notify-keyspace-events"
    value = "Ex" # Expired events
  }

  # Connection timeout (in seconds)
  parameter {
    name  = "timeout"
    value = "300"
  }

  # Maximum number of connected clients
  parameter {
    name  = "maxclients"
    value = "65000"
  }

  tags = {
    Name = "${var.project_name}-redis-params-${var.environment}"
  }
}

# ==============================================================================
# ElastiCache Redis Cluster
# ==============================================================================

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis-${var.environment}"
  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_nodes      = var.redis_num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = var.redis_port
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  # Maintenance window (Sunday 3:00-4:00 AM UTC)
  maintenance_window = "sun:03:00-sun:04:00"

  # Snapshot window (Daily 1:00-2:00 AM UTC)
  snapshot_window = "01:00-02:00"

  # Snapshot retention (days)
  snapshot_retention_limit = var.environment == "prod" ? 7 : 1

  # Enable automatic failover for multi-node clusters
  # automatic_failover_enabled = var.redis_num_cache_nodes > 1 ? true : false

  # Apply changes immediately (set to false in production for scheduled maintenance)
  apply_immediately = var.environment != "prod"

  # Enable encryption at rest (for compliance)
  # at_rest_encryption_enabled = true

  # Enable encryption in transit (for security)
  # transit_encryption_enabled = true

  # CloudWatch log delivery configuration
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = {
    Name = "${var.project_name}-redis-${var.environment}"
  }
}

# ==============================================================================
# CloudWatch Log Groups for Redis Logs
# ==============================================================================

resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/aws/elasticache/redis/${var.project_name}-${var.environment}/slow-log"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name = "${var.project_name}-redis-slow-log-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  name              = "/aws/elasticache/redis/${var.project_name}-${var.environment}/engine-log"
  retention_in_days = var.cloudwatch_retention_days

  tags = {
    Name = "${var.project_name}-redis-engine-log-${var.environment}"
  }
}

# ==============================================================================
# CloudWatch Alarms for Redis Monitoring
# ==============================================================================

# CPU Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${var.project_name}-redis-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors Redis CPU utilization"
  alarm_actions       = [] # Add SNS topic ARN for notifications

  dimensions = {
    CacheClusterId = aws_elasticache_cluster.redis.id
  }

  tags = {
    Name = "${var.project_name}-redis-cpu-alarm-${var.environment}"
  }
}

# Memory Usage Alarm
resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${var.project_name}-redis-memory-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors Redis memory usage"
  alarm_actions       = [] # Add SNS topic ARN for notifications

  dimensions = {
    CacheClusterId = aws_elasticache_cluster.redis.id
  }

  tags = {
    Name = "${var.project_name}-redis-memory-alarm-${var.environment}"
  }
}

# Evictions Alarm (indicates memory pressure)
resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${var.project_name}-redis-evictions-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "This metric monitors Redis evictions"
  alarm_actions       = [] # Add SNS topic ARN for notifications

  dimensions = {
    CacheClusterId = aws_elasticache_cluster.redis.id
  }

  tags = {
    Name = "${var.project_name}-redis-evictions-alarm-${var.environment}"
  }
}

# ==============================================================================
# Outputs (moved to outputs.tf but kept here for reference)
# ==============================================================================

# Output values are defined in outputs.tf
