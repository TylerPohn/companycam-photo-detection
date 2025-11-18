"""Damage Detection Service - Business logic for damage detection engine"""

import logging
import asyncio
import httpx
from typing import Optional, List, Dict
from PIL import Image
import io

from src.ai_models.model_loader import model_loader
from src.ai_models.damage_detection import DamageDetectionConfig
from src.schemas.damage_detection import (
    DamageDetectionResponse,
    BatchDamageDetectionRequest,
    BatchDamageDetectionResponse,
)
from src.services.s3_service import S3Service
from src.config import settings

logger = logging.getLogger(__name__)


class DamageDetectionService:
    """
    Service for damage detection operations.
    Handles photo retrieval, inference, and result storage.
    """

    def __init__(
        self,
        s3_service: Optional[S3Service] = None,
        config: Optional[DamageDetectionConfig] = None,
    ):
        self.s3_service = s3_service or S3Service()
        self.config = config or DamageDetectionConfig()
        self.pipeline = None
        logger.info("Initialized DamageDetectionService")

    def _get_pipeline(self):
        """Get or create damage detection pipeline"""
        if self.pipeline is None:
            self.pipeline = model_loader.get_damage_detection_pipeline(self.config)
        return self.pipeline

    async def download_image_from_url(self, photo_url: str) -> Image.Image:
        """
        Download image from S3 URL or HTTP URL.

        Args:
            photo_url: S3 URL or HTTP URL to photo

        Returns:
            PIL Image

        Raises:
            Exception if download fails
        """
        try:
            # Check if S3 URL
            if photo_url.startswith("s3://"):
                # Extract bucket and key from S3 URL
                # s3://bucket/key/path
                parts = photo_url[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""

                logger.debug(f"Downloading from S3: {bucket}/{key}")
                image_bytes = await self.s3_service.download_file_bytes(bucket, key)
                image = Image.open(io.BytesIO(image_bytes))

            elif photo_url.startswith("http://") or photo_url.startswith("https://"):
                # Download from HTTP URL
                logger.debug(f"Downloading from HTTP: {photo_url}")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(photo_url)
                    response.raise_for_status()
                    image = Image.open(io.BytesIO(response.content))

            else:
                raise ValueError(f"Unsupported URL scheme: {photo_url}")

            logger.debug(f"Downloaded image: {image.size} {image.mode}")
            return image

        except Exception as e:
            logger.error(f"Failed to download image from {photo_url}: {e}")
            raise

    async def detect_damage(
        self,
        photo_url: str,
        photo_id: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        include_segmentation: bool = True,
    ) -> DamageDetectionResponse:
        """
        Detect damage in a photo.

        Args:
            photo_url: S3 URL or HTTP URL to photo
            photo_id: Optional photo ID for tracking
            confidence_threshold: Optional confidence threshold override
            include_segmentation: Whether to generate segmentation masks

        Returns:
            DamageDetectionResponse with detection results
        """
        logger.info(f"Processing damage detection for photo: {photo_url}")

        try:
            # Download image
            image = await self.download_image_from_url(photo_url)

            # Update config if threshold provided
            if confidence_threshold is not None:
                self.config.detector.confidence_threshold = confidence_threshold

            # Update segmentation flag
            self.config.enable_segmentation = include_segmentation

            # Get pipeline
            pipeline = self._get_pipeline()

            # Run detection in thread pool (CPU/GPU intensive)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                pipeline.process_image,
                image,
                self.s3_service if include_segmentation else None,
                photo_id,
            )

            logger.info(
                f"Damage detection completed for {photo_url}: "
                f"{len(response.detections)} detections in {response.processing_time_ms}ms"
            )

            return response

        except Exception as e:
            logger.error(f"Damage detection failed for {photo_url}: {e}")
            raise

    async def detect_damage_batch(
        self, request: BatchDamageDetectionRequest
    ) -> BatchDamageDetectionResponse:
        """
        Detect damage in multiple photos.

        Args:
            request: BatchDamageDetectionRequest with photo URLs and settings

        Returns:
            BatchDamageDetectionResponse with results for all photos
        """
        logger.info(f"Processing batch damage detection for {len(request.photo_urls)} photos")

        import time

        start_time = time.time()

        results = {}
        errors = {}
        successful_count = 0
        failed_count = 0

        # Process photos concurrently (with limit)
        semaphore = asyncio.Semaphore(5)  # Limit concurrent processing

        async def process_one(photo_url: str, idx: int):
            async with semaphore:
                try:
                    response = await self.detect_damage(
                        photo_url=photo_url,
                        photo_id=f"batch_{idx}",
                        confidence_threshold=request.confidence_threshold,
                        include_segmentation=request.include_segmentation,
                    )
                    return photo_url, response, None
                except Exception as e:
                    logger.error(f"Failed to process {photo_url}: {e}")
                    return photo_url, None, str(e)

        # Create tasks for all photos
        tasks = [
            process_one(url, idx) for idx, url in enumerate(request.photo_urls)
        ]

        # Execute all tasks
        task_results = await asyncio.gather(*tasks)

        # Collect results
        for photo_url, response, error in task_results:
            if error:
                errors[photo_url] = error
                failed_count += 1
            else:
                results[photo_url] = response
                successful_count += 1

        total_processing_time_ms = int((time.time() - start_time) * 1000)

        batch_response = BatchDamageDetectionResponse(
            results=results,
            total_processing_time_ms=total_processing_time_ms,
            successful_count=successful_count,
            failed_count=failed_count,
            errors=errors,
        )

        logger.info(
            f"Batch processing completed: {successful_count} successful, "
            f"{failed_count} failed in {total_processing_time_ms}ms"
        )

        return batch_response

    async def get_health_status(self) -> Dict:
        """
        Get health status of damage detection service.

        Returns:
            Health status dictionary
        """
        try:
            pipeline = self._get_pipeline()
            stats = pipeline.get_stats()

            return {
                "status": "healthy",
                "pipeline_loaded": stats.get("pipeline_loaded", False),
                "model_version": stats.get("model_version", "unknown"),
                "detector_loaded": stats.get("detector_stats", {}).get(
                    "model_loaded", False
                ),
                "segmenter_loaded": stats.get("segmenter_stats", {}).get(
                    "model_loaded", False
                ),
                "severity_classifier_loaded": stats.get(
                    "severity_classifier_stats", {}
                ).get("model_loaded", False),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def get_model_stats(self) -> Dict:
        """Get model statistics"""
        pipeline = self._get_pipeline()
        return pipeline.get_stats()
