"""CloudWatch metrics and monitoring service"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

from src.config import settings

logger = logging.getLogger(__name__)


class CloudWatchService:
    """
    Service for publishing custom CloudWatch metrics and logs.

    Tracks:
    - Messages processed count
    - Processing time
    - Failure rate
    - Queue depth
    - Worker health
    """

    # CloudWatch namespace
    NAMESPACE = "CompanyCam/PhotoDetection"

    # Metric names
    METRIC_MESSAGES_PROCESSED = "MessagesProcessed"
    METRIC_PROCESSING_TIME = "ProcessingTimeMs"
    METRIC_PROCESSING_FAILURES = "ProcessingFailures"
    METRIC_QUEUE_DEPTH = "QueueDepth"
    METRIC_WORKER_HEALTH = "WorkerHealth"
    METRIC_RETRY_COUNT = "RetryCount"

    def __init__(self):
        """Initialize CloudWatch client"""
        try:
            client_kwargs = {"region_name": settings.aws_region}

            # Add credentials if provided
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

            # Use custom endpoint for local development (LocalStack)
            if settings.aws_endpoint_url:
                client_kwargs["endpoint_url"] = settings.aws_endpoint_url

            self.cloudwatch = boto3.client("cloudwatch", **client_kwargs)
            logger.info("CloudWatch client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.cloudwatch = None

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Publish a single metric to CloudWatch.

        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit (Count, Milliseconds, etc.)
            dimensions: Metric dimensions for filtering
            timestamp: Metric timestamp (default: now)

        Returns:
            True if successful, False otherwise
        """
        if not self.cloudwatch:
            logger.warning("CloudWatch client not available, metric not published")
            return False

        if dimensions is None:
            dimensions = []

        if timestamp is None:
            timestamp = datetime.utcnow()

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.NAMESPACE,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Timestamp": timestamp,
                        "Dimensions": dimensions,
                    }
                ],
            )

            logger.debug(f"Published metric {metric_name}={value} {unit}")
            return True

        except ClientError as e:
            logger.error(f"Failed to publish metric {metric_name}: {e}")
            return False

    def record_message_processed(
        self, priority: str, success: bool = True
    ) -> bool:
        """
        Record a message processing event.

        Args:
            priority: Queue priority (high, normal, low)
            success: Whether processing was successful

        Returns:
            True if metric published successfully
        """
        dimensions = [
            {"Name": "Priority", "Value": priority},
            {"Name": "Environment", "Value": settings.environment},
        ]

        # Record processing count
        metric_name = (
            self.METRIC_MESSAGES_PROCESSED
            if success
            else self.METRIC_PROCESSING_FAILURES
        )

        return self.put_metric(
            metric_name=metric_name,
            value=1.0,
            unit="Count",
            dimensions=dimensions,
        )

    def record_processing_time(
        self, priority: str, processing_time_ms: int
    ) -> bool:
        """
        Record message processing time.

        Args:
            priority: Queue priority
            processing_time_ms: Processing time in milliseconds

        Returns:
            True if metric published successfully
        """
        dimensions = [
            {"Name": "Priority", "Value": priority},
            {"Name": "Environment", "Value": settings.environment},
        ]

        return self.put_metric(
            metric_name=self.METRIC_PROCESSING_TIME,
            value=float(processing_time_ms),
            unit="Milliseconds",
            dimensions=dimensions,
        )

    def record_retry_attempt(self, priority: str, retry_count: int) -> bool:
        """
        Record a retry attempt.

        Args:
            priority: Queue priority
            retry_count: Current retry count

        Returns:
            True if metric published successfully
        """
        dimensions = [
            {"Name": "Priority", "Value": priority},
            {"Name": "Environment", "Value": settings.environment},
        ]

        return self.put_metric(
            metric_name=self.METRIC_RETRY_COUNT,
            value=float(retry_count),
            unit="Count",
            dimensions=dimensions,
        )

    def record_queue_depth(self, priority: str, depth: int) -> bool:
        """
        Record current queue depth.

        Args:
            priority: Queue priority
            depth: Number of messages in queue

        Returns:
            True if metric published successfully
        """
        dimensions = [
            {"Name": "Priority", "Value": priority},
            {"Name": "Environment", "Value": settings.environment},
        ]

        return self.put_metric(
            metric_name=self.METRIC_QUEUE_DEPTH,
            value=float(depth),
            unit="Count",
            dimensions=dimensions,
        )

    def record_worker_health(self, priority: str, healthy: bool = True) -> bool:
        """
        Record worker health status.

        Args:
            priority: Queue priority
            healthy: Whether worker is healthy

        Returns:
            True if metric published successfully
        """
        dimensions = [
            {"Name": "Priority", "Value": priority},
            {"Name": "Environment", "Value": settings.environment},
        ]

        return self.put_metric(
            metric_name=self.METRIC_WORKER_HEALTH,
            value=1.0 if healthy else 0.0,
            unit="Count",
            dimensions=dimensions,
        )

    def put_metrics_batch(
        self, metrics: List[Dict]
    ) -> bool:
        """
        Publish multiple metrics in a single call.

        Args:
            metrics: List of metric dictionaries with keys:
                - metric_name: str
                - value: float
                - unit: str (optional, default: "Count")
                - dimensions: List[Dict] (optional)
                - timestamp: datetime (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.cloudwatch:
            logger.warning("CloudWatch client not available")
            return False

        if not metrics:
            return True

        try:
            metric_data = []

            for metric in metrics:
                metric_data.append({
                    "MetricName": metric["metric_name"],
                    "Value": metric["value"],
                    "Unit": metric.get("unit", "Count"),
                    "Timestamp": metric.get("timestamp", datetime.utcnow()),
                    "Dimensions": metric.get("dimensions", []),
                })

            # CloudWatch limits to 20 metrics per call
            batch_size = 20
            for i in range(0, len(metric_data), batch_size):
                batch = metric_data[i : i + batch_size]
                self.cloudwatch.put_metric_data(
                    Namespace=self.NAMESPACE,
                    MetricData=batch,
                )

            logger.info(f"Published {len(metrics)} metrics to CloudWatch")
            return True

        except ClientError as e:
            logger.error(f"Failed to publish metrics batch: {e}")
            return False

    def get_metric_statistics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 300,
        statistics: Optional[List[str]] = None,
        dimensions: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict]:
        """
        Retrieve metric statistics from CloudWatch.

        Args:
            metric_name: Name of the metric
            start_time: Start time for statistics
            end_time: End time for statistics
            period: Period in seconds (default: 300 = 5 minutes)
            statistics: List of statistics (Average, Sum, Maximum, etc.)
            dimensions: Metric dimensions for filtering

        Returns:
            Dictionary with metric statistics or None on error
        """
        if not self.cloudwatch:
            logger.warning("CloudWatch client not available")
            return None

        if statistics is None:
            statistics = ["Average", "Sum", "Maximum"]

        if dimensions is None:
            dimensions = []

        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace=self.NAMESPACE,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics,
            )

            return {
                "metric_name": metric_name,
                "datapoints": response.get("Datapoints", []),
                "label": response.get("Label", ""),
            }

        except ClientError as e:
            logger.error(f"Failed to get metric statistics: {e}")
            return None
