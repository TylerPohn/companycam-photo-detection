"""FastAPI routes for Damage Detection Engine"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.damage_detection_service import DamageDetectionService
from src.schemas.damage_detection import (
    DamageDetectionResponse,
    BatchDamageDetectionRequest,
    BatchDamageDetectionResponse,
)
from src.schemas.orchestrator import EngineResult, DetectionType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/damage", tags=["Damage Detection"])

# Initialize service
damage_service = DamageDetectionService()


class DamageDetectionRequest(BaseModel):
    """Request schema for single damage detection"""

    photo_url: str = Field(..., description="S3 URL or HTTP URL to photo")
    photo_id: str = Field(..., description="Photo ID for tracking")
    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    include_segmentation: bool = Field(
        default=True, description="Whether to generate segmentation masks"
    )


@router.post("/detect", response_model=EngineResult, status_code=status.HTTP_200_OK)
async def detect_damage(request: DamageDetectionRequest) -> EngineResult:
    """
    Detect roof damage in a photo.

    This endpoint runs the full damage detection pipeline:
    - YOLOv8 object detection for damage identification
    - U-Net semantic segmentation for damage area visualization
    - ResNet50 severity classification for damage assessment

    Returns results in the EngineResult format for AI Orchestrator integration.
    """
    try:
        logger.info(f"Processing damage detection request for photo: {request.photo_id}")

        # Run damage detection
        import time

        start_time = time.time()

        response = await damage_service.detect_damage(
            photo_url=request.photo_url,
            photo_id=request.photo_id,
            confidence_threshold=request.confidence_threshold,
            include_segmentation=request.include_segmentation,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Convert to EngineResult format for orchestrator
        engine_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version=response.model_version,
            confidence=response.confidence,
            results=response.model_dump(),
            processing_time_ms=processing_time_ms,
            error=None,
        )

        logger.info(
            f"Damage detection completed for {request.photo_id}: "
            f"{len(response.detections)} detections in {processing_time_ms}ms"
        )

        return engine_result

    except Exception as e:
        logger.error(f"Damage detection failed for {request.photo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Damage detection failed: {str(e)}",
        )


@router.post(
    "/detect/batch",
    response_model=BatchDamageDetectionResponse,
    status_code=status.HTTP_200_OK,
)
async def detect_damage_batch(
    request: BatchDamageDetectionRequest,
) -> BatchDamageDetectionResponse:
    """
    Detect damage in multiple photos (batch processing).

    Processes multiple photos concurrently for efficiency.
    Returns individual results for each photo along with batch statistics.
    """
    try:
        logger.info(
            f"Processing batch damage detection for {len(request.photo_urls)} photos"
        )

        response = await damage_service.detect_damage_batch(request)

        logger.info(
            f"Batch damage detection completed: {response.successful_count} successful, "
            f"{response.failed_count} failed in {response.total_processing_time_ms}ms"
        )

        return response

    except Exception as e:
        logger.error(f"Batch damage detection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch damage detection failed: {str(e)}",
        )


@router.get("/health", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for damage detection service.

    Returns status of all loaded models and service health.
    """
    try:
        health_status = await damage_service.get_health_status()
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}",
        )


@router.get("/stats", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_stats() -> Dict[str, Any]:
    """
    Get statistics for damage detection models.

    Returns inference counts, model versions, and performance metrics.
    """
    try:
        stats = damage_service.get_model_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )
