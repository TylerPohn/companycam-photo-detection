"""Unit tests for Queue service"""

import pytest
import json
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.services.queue_service import QueueService


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client"""
    with patch("boto3.client") as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def queue_service(mock_sqs_client):
    """Queue service instance with mocked client"""
    with patch("src.services.queue_service.settings") as mock_settings:
        mock_settings.aws_region = "us-east-1"
        mock_settings.aws_access_key_id = None
        mock_settings.aws_secret_access_key = None
        mock_settings.aws_endpoint_url = None
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456/test-queue"
        mock_settings.sqs_detection_queue_name = "test-queue"
        service = QueueService()
        yield service


class TestQueueService:
    """Test queue service operations"""

    def test_publish_photo_detection_message_success(self, queue_service, mock_sqs_client):
        """Test successful message publishing"""
        mock_sqs_client.send_message.return_value = {"MessageId": "msg-123"}

        result = queue_service.publish_photo_detection_message(
            photo_id="550e8400-e29b-41d4-a716-446655440000",
            s3_url="s3://bucket/photo.jpg",
        )

        assert result is True
        mock_sqs_client.send_message.assert_called_once()

        # Verify message body
        call_args = mock_sqs_client.send_message.call_args
        message_body = json.loads(call_args[1]["MessageBody"])
        assert message_body["photo_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert message_body["s3_url"] == "s3://bucket/photo.jpg"
        assert message_body["detection_types"] == ["damage", "material"]
        assert message_body["priority"] == "normal"

    def test_publish_photo_detection_message_with_custom_types(self, queue_service, mock_sqs_client):
        """Test message publishing with custom detection types"""
        mock_sqs_client.send_message.return_value = {"MessageId": "msg-123"}

        result = queue_service.publish_photo_detection_message(
            photo_id="550e8400-e29b-41d4-a716-446655440000",
            s3_url="s3://bucket/photo.jpg",
            detection_types=["damage"],
            priority="high",
        )

        assert result is True

        # Verify message body
        call_args = mock_sqs_client.send_message.call_args
        message_body = json.loads(call_args[1]["MessageBody"])
        assert message_body["detection_types"] == ["damage"]
        assert message_body["priority"] == "high"

    def test_publish_photo_detection_message_error(self, queue_service, mock_sqs_client):
        """Test message publishing with SQS error"""
        mock_sqs_client.send_message.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "send_message",
        )

        result = queue_service.publish_photo_detection_message(
            photo_id="550e8400-e29b-41d4-a716-446655440000",
            s3_url="s3://bucket/photo.jpg",
        )

        # Should return False on error but not raise exception
        assert result is False

    def test_publish_batch_detection_messages_success(self, queue_service, mock_sqs_client):
        """Test batch message publishing"""
        mock_sqs_client.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}, {"Id": "1"}],
            "Failed": [],
        }

        messages = [
            {"photo_id": "id-1", "s3_url": "s3://bucket/photo1.jpg"},
            {"photo_id": "id-2", "s3_url": "s3://bucket/photo2.jpg"},
        ]

        result = queue_service.publish_batch_detection_messages(messages)

        assert result["success"] == 2
        assert result["failed"] == 0

    def test_publish_batch_detection_messages_partial_failure(self, queue_service, mock_sqs_client):
        """Test batch publishing with partial failure"""
        mock_sqs_client.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}],
            "Failed": [{"Id": "1", "Code": "Error", "Message": "Failed"}],
        }

        messages = [
            {"photo_id": "id-1", "s3_url": "s3://bucket/photo1.jpg"},
            {"photo_id": "id-2", "s3_url": "s3://bucket/photo2.jpg"},
        ]

        result = queue_service.publish_batch_detection_messages(messages)

        assert result["success"] == 1
        assert result["failed"] == 1

    def test_publish_batch_empty_messages(self, queue_service, mock_sqs_client):
        """Test batch publishing with empty message list"""
        result = queue_service.publish_batch_detection_messages([])

        assert result["success"] == 0
        assert result["failed"] == 0
        mock_sqs_client.send_message_batch.assert_not_called()


class TestQueueServiceUnavailable:
    """Test queue service when SQS is unavailable"""

    def test_publish_when_no_queue_url(self):
        """Test publishing when queue URL is not configured"""
        with patch("boto3.client") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            with patch("src.services.queue_service.settings") as mock_settings:
                mock_settings.aws_region = "us-east-1"
                mock_settings.sqs_queue_url = None  # No queue URL
                mock_settings.sqs_detection_queue_name = "test-queue"

                # Simulate queue doesn't exist
                mock_instance.get_queue_url.side_effect = ClientError(
                    {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue"}},
                    "get_queue_url",
                )

                service = QueueService()
                result = service.publish_photo_detection_message(
                    photo_id="test-id",
                    s3_url="s3://bucket/photo.jpg",
                )

                # Should return False gracefully
                assert result is False
