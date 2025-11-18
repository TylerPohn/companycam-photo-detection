"""Unit tests for Message Schema Validation"""

import pytest
from datetime import datetime
from uuid import uuid4

from pydantic import ValidationError
from src.schemas.processing_job import PhotoDetectionMessage


class TestPhotoDetectionMessage:
    """Test photo detection message schema validation"""

    def test_valid_message_all_fields(self):
        """Test validation with all required and optional fields"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://companycam-photos.s3.amazonaws.com/project/2025/11/17/photo.jpg",
            "s3_key": "project_id/2025/11/17/photo.jpg",
            "detection_types": ["damage", "material"],
            "priority": "normal",
            "metadata": {
                "file_size": 2097152,
                "dimensions": {"width": 4000, "height": 3000},
                "timestamp": "2025-11-17T10:30:00Z"
            },
        }

        message = PhotoDetectionMessage(**message_data)

        assert message.message_id == message_data["message_id"]
        assert str(message.photo_id) == message_data["photo_id"]
        assert str(message.user_id) == message_data["user_id"]
        assert str(message.project_id) == message_data["project_id"]
        assert message.s3_url == message_data["s3_url"]
        assert message.s3_key == message_data["s3_key"]
        assert message.detection_types == message_data["detection_types"]
        assert message.priority == message_data["priority"]
        assert message.metadata == message_data["metadata"]

    def test_valid_message_minimal_fields(self):
        """Test validation with only required fields"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
        }

        message = PhotoDetectionMessage(**message_data)

        assert message.message_id == message_data["message_id"]
        # Default values
        assert message.detection_types == ["damage", "material"]
        assert message.priority == "normal"
        assert message.metadata == {}

    def test_missing_required_field_photo_id(self):
        """Test validation fails when photo_id is missing"""
        message_data = {
            "message_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
        }

        with pytest.raises(ValidationError) as exc_info:
            PhotoDetectionMessage(**message_data)

        assert "photo_id" in str(exc_info.value)

    def test_missing_required_field_s3_url(self):
        """Test validation fails when s3_url is missing"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_key": "photos/photo.jpg",
        }

        with pytest.raises(ValidationError) as exc_info:
            PhotoDetectionMessage(**message_data)

        assert "s3_url" in str(exc_info.value)

    def test_invalid_uuid_format(self):
        """Test validation fails with invalid UUID format"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": "not-a-valid-uuid",
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
        }

        with pytest.raises(ValidationError) as exc_info:
            PhotoDetectionMessage(**message_data)

        # Should fail UUID validation
        assert "photo_id" in str(exc_info.value)

    def test_custom_detection_types(self):
        """Test validation with custom detection types"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
            "detection_types": ["damage"],
        }

        message = PhotoDetectionMessage(**message_data)

        assert message.detection_types == ["damage"]

    def test_custom_priority(self):
        """Test validation with custom priority"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
            "priority": "high",
        }

        message = PhotoDetectionMessage(**message_data)

        assert message.priority == "high"

    def test_custom_metadata(self):
        """Test validation with custom metadata"""
        custom_metadata = {
            "file_size": 1024000,
            "dimensions": {"width": 3000, "height": 2000},
            "camera": "iPhone 14",
            "location": {"lat": 40.7128, "lon": -74.0060},
        }

        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
            "metadata": custom_metadata,
        }

        message = PhotoDetectionMessage(**message_data)

        assert message.metadata == custom_metadata

    def test_message_serialization(self):
        """Test message can be serialized to dict"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
        }

        message = PhotoDetectionMessage(**message_data)
        serialized = message.model_dump()

        assert isinstance(serialized, dict)
        assert "photo_id" in serialized
        assert "s3_url" in serialized

    def test_message_json_serialization(self):
        """Test message can be serialized to JSON"""
        message_data = {
            "message_id": str(uuid4()),
            "photo_id": str(uuid4()),
            "user_id": str(uuid4()),
            "project_id": str(uuid4()),
            "s3_url": "https://example.com/photo.jpg",
            "s3_key": "photos/photo.jpg",
        }

        message = PhotoDetectionMessage(**message_data)
        json_str = message.model_dump_json()

        assert isinstance(json_str, str)
        assert "photo_id" in json_str
