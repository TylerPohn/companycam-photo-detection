"""Unit tests for S3 service"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.services.s3_service import (
    S3Service,
    S3ConnectionError,
    InvalidFileTypeError,
    FileTooLargeError,
)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client"""
    with patch("boto3.client") as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def s3_service(mock_s3_client):
    """S3 service instance with mocked client"""
    with patch("src.services.s3_service.settings") as mock_settings:
        mock_settings.aws_region = "us-east-1"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.aws_access_key_id = None
        mock_settings.aws_secret_access_key = None
        mock_settings.aws_endpoint_url = None
        service = S3Service()
        yield service


class TestS3ServiceValidation:
    """Test file validation"""

    def test_validate_file_success(self, s3_service):
        """Test successful file validation"""
        # Should not raise exception
        s3_service.validate_file(1024 * 100, "image/jpeg")
        s3_service.validate_file(1024 * 100, "image/png")

    def test_validate_file_too_large(self, s3_service):
        """Test file size exceeds maximum"""
        with pytest.raises(FileTooLargeError, match="exceeds maximum"):
            s3_service.validate_file(51 * 1024 * 1024, "image/jpeg")

    def test_validate_file_too_small(self, s3_service):
        """Test file size below minimum"""
        with pytest.raises(FileTooLargeError, match="below minimum"):
            s3_service.validate_file(500, "image/jpeg")

    def test_validate_file_invalid_mime_type(self, s3_service):
        """Test invalid MIME type"""
        with pytest.raises(InvalidFileTypeError, match="not allowed"):
            s3_service.validate_file(1024 * 100, "image/gif")

        with pytest.raises(InvalidFileTypeError, match="not allowed"):
            s3_service.validate_file(1024 * 100, "application/pdf")


class TestS3KeyGeneration:
    """Test S3 key generation"""

    def test_generate_s3_key(self, s3_service):
        """Test S3 key generation follows correct format"""
        project_id = "550e8400-e29b-41d4-a716-446655440000"
        photo_id = "660e8400-e29b-41d4-a716-446655440001"

        key = s3_service.generate_s3_key(project_id, photo_id, "jpg")

        # Should contain project ID
        assert project_id in key
        # Should contain photo ID
        assert photo_id in key
        # Should end with .jpg
        assert key.endswith(".jpg")
        # Should have date components
        parts = key.split("/")
        assert len(parts) == 5  # project_id/year/month/day/photo_id.ext


class TestPresignedUrlGeneration:
    """Test pre-signed URL generation"""

    def test_generate_presigned_upload_url_success(self, s3_service, mock_s3_client):
        """Test successful pre-signed URL generation"""
        mock_s3_client.generate_presigned_url.return_value = "https://s3.aws.com/test-url"

        result = s3_service.generate_presigned_upload_url(
            s3_key="test/key.jpg",
            mime_type="image/jpeg",
            file_size=1024 * 100,
        )

        assert "upload_url" in result
        assert "s3_url" in result
        assert "s3_key" in result
        assert "expires_in_seconds" in result
        assert "headers" in result
        assert result["expires_in_seconds"] == 900
        assert result["s3_key"] == "test/key.jpg"

        # Verify S3 client was called correctly
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        assert call_args[0][0] == "put_object"
        assert call_args[1]["Params"]["ContentType"] == "image/jpeg"

    def test_generate_presigned_url_s3_error(self, s3_service, mock_s3_client):
        """Test pre-signed URL generation with S3 error"""
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "generate_presigned_url",
        )

        with pytest.raises(S3ConnectionError, match="Failed to generate pre-signed URL"):
            s3_service.generate_presigned_upload_url(
                s3_key="test/key.jpg",
                mime_type="image/jpeg",
                file_size=1024 * 100,
            )

    def test_generate_presigned_url_custom_expiration(self, s3_service, mock_s3_client):
        """Test pre-signed URL with custom expiration"""
        mock_s3_client.generate_presigned_url.return_value = "https://s3.aws.com/test-url"

        result = s3_service.generate_presigned_upload_url(
            s3_key="test/key.jpg",
            mime_type="image/jpeg",
            file_size=1024 * 100,
            expiration=1800,  # 30 minutes
        )

        assert result["expires_in_seconds"] == 1800


class TestS3ObjectOperations:
    """Test S3 object operations"""

    def test_check_object_exists_true(self, s3_service, mock_s3_client):
        """Test object exists check returns True"""
        mock_s3_client.head_object.return_value = {"ContentLength": 1024}

        exists = s3_service.check_object_exists("test/key.jpg")

        assert exists is True
        mock_s3_client.head_object.assert_called_once()

    def test_check_object_exists_false(self, s3_service, mock_s3_client):
        """Test object exists check returns False"""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "head_object",
        )

        exists = s3_service.check_object_exists("test/key.jpg")

        assert exists is False

    def test_get_object_metadata_success(self, s3_service, mock_s3_client):
        """Test get object metadata"""
        mock_s3_client.head_object.return_value = {
            "ContentType": "image/jpeg",
            "ContentLength": 1024,
            "LastModified": "2025-11-17",
            "ETag": "abc123",
        }

        metadata = s3_service.get_object_metadata("test/key.jpg")

        assert metadata is not None
        assert metadata["content_type"] == "image/jpeg"
        assert metadata["content_length"] == 1024

    def test_get_object_metadata_not_found(self, s3_service, mock_s3_client):
        """Test get object metadata for non-existent object"""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "head_object",
        )

        metadata = s3_service.get_object_metadata("test/key.jpg")

        assert metadata is None

    def test_delete_object_success(self, s3_service, mock_s3_client):
        """Test delete object"""
        mock_s3_client.delete_object.return_value = {}

        result = s3_service.delete_object("test/key.jpg")

        assert result is True
        mock_s3_client.delete_object.assert_called_once()

    def test_delete_object_error(self, s3_service, mock_s3_client):
        """Test delete object with error"""
        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "delete_object",
        )

        with pytest.raises(S3ConnectionError):
            s3_service.delete_object("test/key.jpg")
