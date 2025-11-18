"""Message queue service for photo detection pipeline"""

import logging
import json
from typing import Dict, List, Optional
from uuid import UUID
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from pydantic import ValidationError

from src.config import settings
from src.schemas.processing_job import PhotoDetectionMessage

logger = logging.getLogger(__name__)


class QueueServiceError(Exception):
    """Base exception for queue service errors"""
    pass


class QueueService:
    """Service for publishing and managing messages in SQS queues with priority levels"""

    # Priority queue mapping
    PRIORITY_HIGH = "high"
    PRIORITY_NORMAL = "normal"
    PRIORITY_LOW = "low"

    def __init__(self):
        """Initialize SQS client with retry configuration"""
        retry_config = Config(
            retries={
                "max_attempts": 3,
                "mode": "standard",
            },
            connect_timeout=5,
            read_timeout=10,
        )

        client_kwargs = {
            "region_name": settings.aws_region,
            "config": retry_config,
        }

        # Add credentials if provided
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        # Use custom endpoint for local development
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        try:
            self.sqs_client = boto3.client("sqs", **client_kwargs)
            self._queue_urls: Dict[str, Optional[str]] = {
                self.PRIORITY_HIGH: None,
                self.PRIORITY_NORMAL: None,
                self.PRIORITY_LOW: None,
            }
            self._dlq_urls: Dict[str, Optional[str]] = {
                self.PRIORITY_HIGH: None,
                self.PRIORITY_NORMAL: None,
                self.PRIORITY_LOW: None,
            }
            logger.info("SQS client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {e}")
            # Don't raise error - queue service is optional for development
            self.sqs_client = None

    def _get_queue_name_for_priority(self, priority: str) -> str:
        """Get queue name for given priority level"""
        queue_names = {
            self.PRIORITY_HIGH: settings.sqs_high_priority_queue_name,
            self.PRIORITY_NORMAL: settings.sqs_normal_priority_queue_name,
            self.PRIORITY_LOW: settings.sqs_low_priority_queue_name,
        }
        return queue_names.get(priority, settings.sqs_normal_priority_queue_name)

    def _get_dlq_name_for_priority(self, priority: str) -> str:
        """Get DLQ name for given priority level"""
        dlq_names = {
            self.PRIORITY_HIGH: settings.sqs_high_priority_dlq_name,
            self.PRIORITY_NORMAL: settings.sqs_normal_priority_dlq_name,
            self.PRIORITY_LOW: settings.sqs_low_priority_dlq_name,
        }
        return dlq_names.get(priority, settings.sqs_normal_priority_dlq_name)

    def _get_queue_url(self, priority: str = PRIORITY_NORMAL) -> Optional[str]:
        """
        Get or retrieve queue URL for given priority.

        Args:
            priority: Priority level (high, normal, low)

        Returns:
            Queue URL or None if queue service is unavailable
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return None

        # Return cached URL if available
        if self._queue_urls.get(priority):
            return self._queue_urls[priority]

        # Try to get queue URL by name
        queue_name = self._get_queue_name_for_priority(priority)
        try:
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            self._queue_urls[priority] = response["QueueUrl"]
            logger.info(f"Found queue URL for {priority} priority: {self._queue_urls[priority]}")
            return self._queue_urls[priority]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AWS.SimpleQueueService.NonExistentQueue":
                logger.warning(f"Queue {queue_name} does not exist")
            else:
                logger.error(f"Error getting queue URL: {error_code} - {e}")
            return None

    def _get_dlq_url(self, priority: str = PRIORITY_NORMAL) -> Optional[str]:
        """
        Get or retrieve DLQ URL for given priority.

        Args:
            priority: Priority level (high, normal, low)

        Returns:
            DLQ URL or None if queue service is unavailable
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return None

        # Return cached URL if available
        if self._dlq_urls.get(priority):
            return self._dlq_urls[priority]

        # Try to get DLQ URL by name
        dlq_name = self._get_dlq_name_for_priority(priority)
        try:
            response = self.sqs_client.get_queue_url(QueueName=dlq_name)
            self._dlq_urls[priority] = response["QueueUrl"]
            logger.info(f"Found DLQ URL for {priority} priority: {self._dlq_urls[priority]}")
            return self._dlq_urls[priority]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AWS.SimpleQueueService.NonExistentQueue":
                logger.warning(f"DLQ {dlq_name} does not exist")
            else:
                logger.error(f"Error getting DLQ URL: {error_code} - {e}")
            return None

    def validate_message(self, message_data: dict) -> Optional[PhotoDetectionMessage]:
        """
        Validate message against PhotoDetectionMessage schema.

        Args:
            message_data: Raw message data dictionary

        Returns:
            Validated PhotoDetectionMessage or None if invalid
        """
        try:
            return PhotoDetectionMessage(**message_data)
        except ValidationError as e:
            logger.error(f"Message validation failed: {e}")
            return None

    def publish_photo_detection_message(
        self,
        photo_id: str,
        user_id: str,
        project_id: str,
        s3_url: str,
        s3_key: str,
        detection_types: Optional[List[str]] = None,
        priority: str = "normal",
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Publish photo detection message to priority queue.

        Args:
            photo_id: UUID of the photo
            user_id: UUID of the user
            project_id: UUID of the project
            s3_url: S3 URL of the photo
            s3_key: S3 key path
            detection_types: List of detection types to run
            priority: Message priority (high, normal, low)
            metadata: Additional metadata

        Returns:
            Message ID if published successfully, None otherwise
        """
        if detection_types is None:
            detection_types = ["damage", "material"]

        if metadata is None:
            metadata = {}

        # Build message following PhotoDetectionMessage schema
        message_data = {
            "message_id": "",  # Will be set by SQS
            "photo_id": photo_id,
            "user_id": user_id,
            "project_id": project_id,
            "s3_url": s3_url,
            "s3_key": s3_key,
            "detection_types": detection_types,
            "priority": priority,
            "metadata": metadata,
        }

        queue_url = self._get_queue_url(priority)
        if not queue_url:
            logger.error(
                f"Queue not available for priority {priority}, cannot publish message for photo {photo_id}. "
                "Message will need to be processed manually."
            )
            return None

        try:
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_data),
                MessageAttributes={
                    "PhotoId": {"StringValue": str(photo_id), "DataType": "String"},
                    "UserId": {"StringValue": str(user_id), "DataType": "String"},
                    "ProjectId": {"StringValue": str(project_id), "DataType": "String"},
                    "Priority": {"StringValue": priority, "DataType": "String"},
                },
            )

            message_id = response.get("MessageId")
            logger.info(
                f"Published detection message for photo {photo_id} to {priority} queue. "
                f"MessageId: {message_id}"
            )
            return message_id

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"Failed to publish message for photo {photo_id}: {error_code} - {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error publishing message for photo {photo_id}: {e}")
            return None

    def receive_messages(
        self,
        priority: str = PRIORITY_NORMAL,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: int = 300,
    ) -> List[Dict]:
        """
        Receive messages from priority queue using long polling.

        Args:
            priority: Priority level to consume from
            max_messages: Maximum number of messages to receive (1-10)
            wait_time_seconds: Long polling wait time
            visibility_timeout: Message visibility timeout in seconds

        Returns:
            List of message dictionaries
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return []

        queue_url = self._get_queue_url(priority)
        if not queue_url:
            logger.error(f"Queue not available for priority {priority}")
            return []

        try:
            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                VisibilityTimeout=visibility_timeout,
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            logger.info(f"Received {len(messages)} messages from {priority} queue")
            return messages

        except ClientError as e:
            logger.error(f"Failed to receive messages: {e}")
            return []

    def delete_message(self, receipt_handle: str, priority: str = PRIORITY_NORMAL) -> bool:
        """
        Delete message from queue after successful processing.

        Args:
            receipt_handle: Message receipt handle from receive_message
            priority: Priority level of the queue

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return False

        queue_url = self._get_queue_url(priority)
        if not queue_url:
            logger.error(f"Queue not available for priority {priority}")
            return False

        try:
            self.sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.debug(f"Deleted message from {priority} queue")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    def get_queue_metrics(self, priority: str = PRIORITY_NORMAL) -> Dict[str, int]:
        """
        Get queue metrics for monitoring.

        Args:
            priority: Priority level

        Returns:
            Dictionary with queue metrics
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return {}

        queue_url = self._get_queue_url(priority)
        if not queue_url:
            logger.error(f"Queue not available for priority {priority}")
            return {}

        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                    "ApproximateNumberOfMessagesDelayed",
                ]
            )

            attributes = response.get("Attributes", {})
            return {
                "messages_available": int(attributes.get("ApproximateNumberOfMessages", 0)),
                "messages_in_flight": int(attributes.get("ApproximateNumberOfMessagesNotVisible", 0)),
                "messages_delayed": int(attributes.get("ApproximateNumberOfMessagesDelayed", 0)),
            }

        except ClientError as e:
            logger.error(f"Failed to get queue metrics: {e}")
            return {}

    def get_dlq_messages(self, priority: str = PRIORITY_NORMAL, max_messages: int = 10) -> List[Dict]:
        """
        Retrieve messages from Dead Letter Queue for analysis.

        Args:
            priority: Priority level
            max_messages: Maximum number of messages to retrieve

        Returns:
            List of DLQ messages
        """
        if not self.sqs_client:
            logger.warning("SQS client not available")
            return []

        dlq_url = self._get_dlq_url(priority)
        if not dlq_url:
            logger.error(f"DLQ not available for priority {priority}")
            return []

        try:
            response = self.sqs_client.receive_message(
                QueueUrl=dlq_url,
                MaxNumberOfMessages=min(max_messages, 10),
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            logger.info(f"Retrieved {len(messages)} messages from {priority} DLQ")
            return messages

        except ClientError as e:
            logger.error(f"Failed to retrieve DLQ messages: {e}")
            return []

    def publish_batch_detection_messages(
        self, messages: List[Dict]
    ) -> Dict[str, int]:
        """
        Publish multiple detection messages in batch.

        Args:
            messages: List of message dictionaries with photo_id, s3_url, priority, etc.

        Returns:
            Dictionary with success and failure counts
        """
        if not messages:
            return {"success": 0, "failed": 0}

        # Group messages by priority
        priority_groups = {
            self.PRIORITY_HIGH: [],
            self.PRIORITY_NORMAL: [],
            self.PRIORITY_LOW: [],
        }

        for msg in messages:
            priority = msg.get("priority", self.PRIORITY_NORMAL)
            priority_groups[priority].append(msg)

        total_success = 0
        total_failed = 0

        # Process each priority group
        for priority, priority_messages in priority_groups.items():
            if not priority_messages:
                continue

            queue_url = self._get_queue_url(priority)
            if not queue_url:
                logger.error(f"Queue not available for priority {priority}")
                total_failed += len(priority_messages)
                continue

            # SQS batch limit is 10 messages
            batch_size = 10
            for i in range(0, len(priority_messages), batch_size):
                batch = priority_messages[i : i + batch_size]
                entries = []

                for idx, msg in enumerate(batch):
                    entries.append(
                        {
                            "Id": str(idx),
                            "MessageBody": json.dumps(
                                {
                                    "photo_id": msg.get("photo_id"),
                                    "user_id": msg.get("user_id"),
                                    "project_id": msg.get("project_id"),
                                    "s3_url": msg.get("s3_url"),
                                    "s3_key": msg.get("s3_key"),
                                    "detection_types": msg.get("detection_types", ["damage", "material"]),
                                    "priority": priority,
                                    "metadata": msg.get("metadata", {}),
                                }
                            ),
                            "MessageAttributes": {
                                "PhotoId": {
                                    "StringValue": str(msg.get("photo_id")),
                                    "DataType": "String",
                                },
                                "Priority": {
                                    "StringValue": priority,
                                    "DataType": "String",
                                },
                            },
                        }
                    )

                try:
                    response = self.sqs_client.send_message_batch(
                        QueueUrl=queue_url, Entries=entries
                    )

                    successful = len(response.get("Successful", []))
                    failed = len(response.get("Failed", []))

                    total_success += successful
                    total_failed += failed

                    logger.info(
                        f"Batch published to {priority} queue: {successful} success, {failed} failed"
                    )

                except ClientError as e:
                    logger.error(f"Failed to publish batch to {priority} queue: {e}")
                    total_failed += len(batch)

        return {"success": total_success, "failed": total_failed}
