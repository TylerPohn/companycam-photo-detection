"""Volume Estimation Service"""

import logging
import time
from typing import Optional, Dict
import json
import hashlib
import httpx
import numpy as np
from PIL import Image
import io

from ..ai_models.volume_estimation import VolumeEstimationPipeline, VolumeEstimationConfig
from ..schemas.volume_estimation_schema import (
    VolumeEstimationResponse,
    VolumeEstimationRequest,
    VolumeEstimationError
)
from ..services.s3_service import S3Service

logger = logging.getLogger(__name__)


class VolumeEstimationService:
    """
    Service layer for volume estimation.
    Handles caching, S3 operations, and business logic.
    """

    def __init__(
        self,
        config: Optional[VolumeEstimationConfig] = None,
        redis_client=None,
        s3_service: Optional[S3Service] = None
    ):
        """
        Initialize volume estimation service.

        Args:
            config: VolumeEstimationConfig instance
            redis_client: Redis client for caching (optional)
            s3_service: S3Service instance (optional)
        """
        self.config = config or VolumeEstimationConfig()
        self.redis_client = redis_client
        self.s3_service = s3_service or S3Service()
        self.pipeline = VolumeEstimationPipeline(config)
        self._service_ready = False

        logger.info("VolumeEstimationService initialized")

    async def initialize(self):
        """Initialize service and load models"""
        if self._service_ready:
            logger.debug("Service already initialized")
            return

        logger.info("Initializing VolumeEstimationService...")

        # Load models
        self.pipeline.load_models()

        self._service_ready = True
        logger.info("VolumeEstimationService ready")

    async def estimate_volume(
        self, request: VolumeEstimationRequest
    ) -> VolumeEstimationResponse:
        """
        Estimate volume for a photo.

        Args:
            request: VolumeEstimationRequest

        Returns:
            VolumeEstimationResponse

        Raises:
            Exception if estimation fails
        """
        if not self._service_ready:
            await self.initialize()

        start_time = time.time()

        try:
            # Check cache first
            if self.config.enable_caching and self.redis_client:
                cached_result = await self._get_from_cache(request.photo_id)
                if cached_result:
                    logger.info(f"Cache hit for photo_id={request.photo_id}")
                    return VolumeEstimationResponse(**cached_result)

            # Download image from S3
            logger.debug(f"Downloading image from {request.photo_url}")
            image_data = await self._download_image(request.photo_url)

            # Convert to numpy array
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image.convert("RGB"))

            # Run volume estimation
            logger.info(f"Running volume estimation for photo_id={request.photo_id}")
            result = self.pipeline.estimate_volume(
                image_array,
                save_depth_map=request.save_depth_map
            )

            # Convert to response schema
            response = VolumeEstimationResponse(**result)

            # Cache result
            if self.config.enable_caching and self.redis_client:
                await self._save_to_cache(request.photo_id, response.model_dump())

            processing_time = (time.time() - start_time) * 1000
            logger.info(
                f"Volume estimation complete for photo_id={request.photo_id}: "
                f"{response.estimated_volume} {response.unit} "
                f"(confidence={response.confidence:.2f}, time={processing_time:.0f}ms)"
            )

            return response

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"Volume estimation failed for photo_id={request.photo_id}: {e}")

            # Return error response
            error = VolumeEstimationError(
                error=str(e),
                error_code="ESTIMATION_FAILED",
                photo_id=request.photo_id,
                processing_time_ms=processing_time
            )
            raise Exception(error.model_dump_json())

    async def _download_image(self, photo_url: str) -> bytes:
        """
        Download image from URL or S3.

        Args:
            photo_url: URL or S3 path to image

        Returns:
            Image data as bytes
        """
        try:
            if photo_url.startswith("s3://"):
                # Parse S3 URL
                parts = photo_url.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""

                # Download from S3
                image_data = await self.s3_service.download_file(bucket, key)
                return image_data

            elif photo_url.startswith("http://") or photo_url.startswith("https://"):
                # Download from HTTP URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(photo_url, timeout=30.0)
                    response.raise_for_status()
                    return response.content

            else:
                raise ValueError(f"Unsupported photo URL format: {photo_url}")

        except Exception as e:
            logger.error(f"Failed to download image from {photo_url}: {e}")
            raise

    async def _get_from_cache(self, photo_id: str) -> Optional[Dict]:
        """
        Get cached result from Redis.

        Args:
            photo_id: Photo ID

        Returns:
            Cached result dict or None
        """
        try:
            cache_key = self._get_cache_key(photo_id)

            if hasattr(self.redis_client, 'get'):
                # Sync Redis client
                cached = self.redis_client.get(cache_key)
            else:
                # Async Redis client
                cached = await self.redis_client.get(cache_key)

            if cached:
                return json.loads(cached)

        except Exception as e:
            logger.warning(f"Cache get failed for photo_id={photo_id}: {e}")

        return None

    async def _save_to_cache(self, photo_id: str, result: Dict):
        """
        Save result to Redis cache.

        Args:
            photo_id: Photo ID
            result: Estimation result dict
        """
        try:
            cache_key = self._get_cache_key(photo_id)
            cached_data = json.dumps(result)

            if hasattr(self.redis_client, 'setex'):
                # Sync Redis client
                self.redis_client.setex(
                    cache_key,
                    self.config.cache_ttl_seconds,
                    cached_data
                )
            else:
                # Async Redis client
                await self.redis_client.setex(
                    cache_key,
                    self.config.cache_ttl_seconds,
                    cached_data
                )

            logger.debug(f"Cached result for photo_id={photo_id}")

        except Exception as e:
            logger.warning(f"Cache save failed for photo_id={photo_id}: {e}")

    def _get_cache_key(self, photo_id: str) -> str:
        """
        Generate cache key for photo.

        Args:
            photo_id: Photo ID

        Returns:
            Cache key
        """
        # Include model version in cache key
        key_base = f"volume_estimation:{self.config.model_version}:{photo_id}"
        return key_base

    async def get_health(self) -> Dict:
        """
        Get service health status.

        Returns:
            Health status dict
        """
        return {
            "status": "healthy" if self._service_ready else "initializing",
            "service": "volume_estimation",
            "model_version": self.config.model_version,
            "models_loaded": self.pipeline._models_loaded,
            "device": self.pipeline.device,
            "stats": self.pipeline.get_stats() if self._service_ready else {}
        }

    async def get_stats(self) -> Dict:
        """
        Get service statistics.

        Returns:
            Stats dict
        """
        stats = {
            "service": "volume_estimation",
            "model_version": self.config.model_version,
            "ready": self._service_ready
        }

        if self._service_ready:
            stats.update(self.pipeline.get_stats())

        return stats
