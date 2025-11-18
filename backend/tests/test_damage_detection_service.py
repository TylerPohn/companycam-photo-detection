"""Tests for damage detection service"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from PIL import Image
import numpy as np
import io

from src.services.damage_detection_service import DamageDetectionService
from src.schemas.damage_detection import (
    DamageDetectionResponse,
    BatchDamageDetectionRequest,
    BatchDamageDetectionResponse,
)


@pytest.fixture
def mock_s3_service():
    """Create mock S3 service"""
    service = Mock()
    service.download_file_bytes = AsyncMock(
        return_value=create_test_image_bytes()
    )
    service.upload_bytes = Mock(
        return_value="https://s3.amazonaws.com/bucket/masks/test.png"
    )
    return service


@pytest.fixture
def service(mock_s3_service):
    """Create damage detection service"""
    return DamageDetectionService(s3_service=mock_s3_service)


def create_test_image_bytes():
    """Create test image bytes"""
    image_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    image = Image.fromarray(image_array, mode="RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer.getvalue()


class TestDamageDetectionService:
    """Test suite for DamageDetectionService"""

    def test_service_initialization(self, service):
        """Test service initializes correctly"""
        assert service.s3_service is not None
        assert service.config is not None
        assert service.pipeline is None  # Lazy loaded

    @pytest.mark.asyncio
    async def test_download_image_from_s3_url(self, service):
        """Test downloading image from S3 URL"""
        s3_url = "s3://test-bucket/path/to/image.jpg"

        image = await service.download_image_from_url(s3_url)

        assert isinstance(image, Image.Image)
        assert service.s3_service.download_file_bytes.called

    @pytest.mark.asyncio
    async def test_download_image_from_http_url(self, service):
        """Test downloading image from HTTP URL"""
        http_url = "https://example.com/image.jpg"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.content = create_test_image_bytes()
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            image = await service.download_image_from_url(http_url)

            assert isinstance(image, Image.Image)

    @pytest.mark.asyncio
    async def test_download_image_invalid_url(self, service):
        """Test downloading with invalid URL scheme"""
        invalid_url = "ftp://example.com/image.jpg"

        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            await service.download_image_from_url(invalid_url)

    @pytest.mark.asyncio
    async def test_detect_damage(self, service):
        """Test damage detection"""
        photo_url = "s3://test-bucket/photo.jpg"
        photo_id = "test_photo_123"

        response = await service.detect_damage(
            photo_url=photo_url,
            photo_id=photo_id,
            confidence_threshold=0.7,
            include_segmentation=True,
        )

        assert isinstance(response, DamageDetectionResponse)
        assert response.processing_time_ms > 0
        assert 0.0 <= response.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_detect_damage_without_segmentation(self, service):
        """Test damage detection without segmentation"""
        photo_url = "s3://test-bucket/photo.jpg"

        response = await service.detect_damage(
            photo_url=photo_url,
            photo_id="test_photo",
            include_segmentation=False,
        )

        # All detections should have None for segmentation_mask
        for detection in response.detections:
            assert detection.segmentation_mask is None

    @pytest.mark.asyncio
    async def test_detect_damage_custom_threshold(self, service):
        """Test damage detection with custom confidence threshold"""
        photo_url = "s3://test-bucket/photo.jpg"

        response = await service.detect_damage(
            photo_url=photo_url,
            photo_id="test_photo",
            confidence_threshold=0.9,
        )

        # All detections should meet high threshold
        for detection in response.detections:
            assert detection.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_detect_damage_batch(self, service):
        """Test batch damage detection"""
        request = BatchDamageDetectionRequest(
            photo_urls=[
                "s3://test-bucket/photo1.jpg",
                "s3://test-bucket/photo2.jpg",
                "s3://test-bucket/photo3.jpg",
            ],
            confidence_threshold=0.7,
            include_segmentation=True,
        )

        response = await service.detect_damage_batch(request)

        assert isinstance(response, BatchDamageDetectionResponse)
        assert response.successful_count + response.failed_count == len(
            request.photo_urls
        )
        assert response.total_processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_detect_damage_batch_partial_failure(self, service):
        """Test batch processing with some failures"""
        # Configure mock to fail on second image
        service.s3_service.download_file_bytes = AsyncMock(
            side_effect=[
                create_test_image_bytes(),  # Success
                Exception("S3 error"),  # Failure
                create_test_image_bytes(),  # Success
            ]
        )

        request = BatchDamageDetectionRequest(
            photo_urls=[
                "s3://test-bucket/photo1.jpg",
                "s3://test-bucket/photo2.jpg",
                "s3://test-bucket/photo3.jpg",
            ],
        )

        response = await service.detect_damage_batch(request)

        # Should have some successes and some failures
        assert response.successful_count > 0
        assert response.failed_count > 0
        assert len(response.errors) == response.failed_count

    @pytest.mark.asyncio
    async def test_get_health_status(self, service):
        """Test health status check"""
        health = await service.get_health_status()

        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy"]

    @pytest.mark.asyncio
    async def test_get_health_status_after_processing(self, service):
        """Test health status after processing"""
        # Process an image first
        await service.detect_damage(
            photo_url="s3://test-bucket/photo.jpg",
            photo_id="test_photo",
        )

        health = await service.get_health_status()

        assert health["status"] == "healthy"
        assert health["pipeline_loaded"] is True
        assert health["detector_loaded"] is True

    def test_get_model_stats(self, service):
        """Test getting model statistics"""
        # Get pipeline loaded
        service._get_pipeline()

        stats = service.get_model_stats()

        assert "pipeline_loaded" in stats
        assert "model_version" in stats
        assert "detector_stats" in stats

    @pytest.mark.asyncio
    async def test_pipeline_lazy_loading(self, service):
        """Test that pipeline is lazy loaded"""
        assert service.pipeline is None

        # First call should load pipeline
        await service.detect_damage(
            photo_url="s3://test-bucket/photo.jpg",
            photo_id="test_photo",
        )

        assert service.pipeline is not None

    @pytest.mark.asyncio
    async def test_download_error_handling(self, service):
        """Test error handling for download failures"""
        service.s3_service.download_file_bytes = AsyncMock(
            side_effect=Exception("Download failed")
        )

        with pytest.raises(Exception, match="Download failed"):
            await service.download_image_from_url("s3://test-bucket/photo.jpg")

    @pytest.mark.asyncio
    async def test_concurrent_batch_processing(self, service):
        """Test that batch processing handles concurrency"""
        # Create a batch with many images
        request = BatchDamageDetectionRequest(
            photo_urls=[f"s3://test-bucket/photo{i}.jpg" for i in range(10)],
            confidence_threshold=0.7,
        )

        response = await service.detect_damage_batch(request)

        # All images should be processed
        assert (
            response.successful_count + response.failed_count
            == len(request.photo_urls)
        )
