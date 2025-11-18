"""Tests for Volume Estimation Service"""

import pytest
import numpy as np
from PIL import Image
import io
from unittest.mock import Mock, AsyncMock, patch
from src.services.volume_estimation_service import VolumeEstimationService
from src.schemas.volume_estimation_schema import VolumeEstimationRequest, VolumeEstimationResponse
from src.ai_models.volume_estimation.config import VolumeEstimationConfig


@pytest.fixture
def service_config():
    """Create service config"""
    return VolumeEstimationConfig(enable_caching=False)


@pytest.fixture
def mock_s3_service():
    """Create mock S3 service"""
    s3 = Mock()
    # Create sample image bytes
    image = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()

    s3.download_file = AsyncMock(return_value=image_bytes)
    return s3


@pytest.fixture
def service(service_config, mock_s3_service):
    """Create volume estimation service"""
    return VolumeEstimationService(
        config=service_config,
        redis_client=None,
        s3_service=mock_s3_service
    )


@pytest.fixture
def sample_request():
    """Create sample estimation request"""
    return VolumeEstimationRequest(
        photo_id="photo_123",
        photo_url="s3://test-bucket/photos/photo_123.jpg",
        save_depth_map=True,
        unit="cubic_yards"
    )


@pytest.mark.asyncio
async def test_service_initialization(service):
    """Test service initialization"""
    assert service.config is not None
    assert service.pipeline is not None
    assert service._service_ready is False


@pytest.mark.asyncio
async def test_initialize_service(service):
    """Test service initialization"""
    await service.initialize()

    assert service._service_ready is True
    assert service.pipeline._models_loaded is True


@pytest.mark.asyncio
async def test_estimate_volume(service, sample_request):
    """Test volume estimation"""
    await service.initialize()

    response = await service.estimate_volume(sample_request)

    assert isinstance(response, VolumeEstimationResponse)
    assert response.estimated_volume >= 0.0
    assert 0.0 <= response.confidence <= 1.0
    assert response.unit == "cubic_yards"
    assert response.processing_time_ms > 0


@pytest.mark.asyncio
async def test_estimate_volume_auto_initialize(service, sample_request):
    """Test that estimation auto-initializes service"""
    assert service._service_ready is False

    response = await service.estimate_volume(sample_request)

    assert service._service_ready is True
    assert isinstance(response, VolumeEstimationResponse)


@pytest.mark.asyncio
async def test_download_image_s3(service):
    """Test downloading image from S3"""
    image_bytes = await service._download_image("s3://test-bucket/photos/test.jpg")

    assert image_bytes is not None
    assert len(image_bytes) > 0
    service.s3_service.download_file.assert_called_once()


@pytest.mark.asyncio
async def test_download_image_http(service):
    """Test downloading image from HTTP URL"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = Mock()

        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        image_bytes = await service._download_image("https://example.com/photo.jpg")

        assert image_bytes == b"fake_image_data"


@pytest.mark.asyncio
async def test_download_image_invalid_url(service):
    """Test downloading image with invalid URL"""
    with pytest.raises(ValueError, match="Unsupported photo URL format"):
        await service._download_image("invalid://url")


@pytest.mark.asyncio
async def test_get_health(service):
    """Test health check"""
    # Before initialization
    health = await service.get_health()
    assert health["status"] == "initializing"
    assert health["service"] == "volume_estimation"

    # After initialization
    await service.initialize()
    health = await service.get_health()
    assert health["status"] == "healthy"
    assert health["models_loaded"] is True


@pytest.mark.asyncio
async def test_get_stats(service):
    """Test getting service statistics"""
    await service.initialize()

    stats = await service.get_stats()

    assert stats["service"] == "volume_estimation"
    assert stats["ready"] is True
    assert "inference_count" in stats


@pytest.mark.asyncio
async def test_caching():
    """Test result caching"""
    # Create service with caching enabled
    config = VolumeEstimationConfig(enable_caching=True)
    mock_redis = Mock()
    mock_redis.get = Mock(return_value=None)
    mock_redis.setex = Mock()

    mock_s3 = Mock()
    image = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    mock_s3.download_file = AsyncMock(return_value=buffer.getvalue())

    service = VolumeEstimationService(
        config=config,
        redis_client=mock_redis,
        s3_service=mock_s3
    )

    await service.initialize()

    request = VolumeEstimationRequest(
        photo_id="cached_photo",
        photo_url="s3://test-bucket/photos/cached.jpg"
    )

    response = await service.estimate_volume(request)

    # Should have tried to save to cache
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_key_generation(service):
    """Test cache key generation"""
    cache_key = service._get_cache_key("photo_123")

    assert "volume_estimation" in cache_key
    assert "photo_123" in cache_key
    assert service.config.model_version in cache_key


@pytest.mark.asyncio
async def test_estimate_volume_error_handling(service):
    """Test error handling in volume estimation"""
    # Create invalid request with bad URL
    service.s3_service.download_file = AsyncMock(side_effect=Exception("Download failed"))

    request = VolumeEstimationRequest(
        photo_id="error_photo",
        photo_url="s3://test-bucket/photos/error.jpg"
    )

    with pytest.raises(Exception):
        await service.estimate_volume(request)
