"""API routes for detection results retrieval and search"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from src.database import get_db
from src.schemas.detection_result_schema import (
    DetectionResultResponseSchema,
    DetectionListResponseSchema,
    AggregatedDetectionResultSchema,
)
from src.services.detection_storage_service import DetectionStorageService
from src.services.results_cache_service import ResultsCacheService
from src.services.redis_service import RedisService
from src.api.auth_routes import get_current_user

router = APIRouter(prefix="/api/v1/detections", tags=["detections"])


@router.get("/{detection_id}", response_model=DetectionResultResponseSchema)
async def get_detection(
    detection_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get a specific detection result by ID.
    Results are cached in Redis for fast retrieval.
    """
    # Try cache first
    redis_service = RedisService()
    cache_service = ResultsCacheService(redis_service)

    cached_result = cache_service.get_cached_detection_result(detection_id)
    if cached_result:
        return cached_result

    # Fetch from database
    storage_service = DetectionStorageService(db)
    detection = storage_service.get_detection_by_id(detection_id)

    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    # Convert to response schema
    response = DetectionResultResponseSchema.model_validate(detection)

    # Cache the result
    cache_service.cache_detection_result(
        detection_id, response.model_dump(mode="json")
    )

    return response


@router.get("/photos/{photo_id}", response_model=DetectionListResponseSchema)
async def get_detections_by_photo(
    photo_id: UUID,
    detection_type: Optional[str] = Query(None, description="Filter by detection type"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all detection results for a photo.
    Optionally filter by detection type (damage, material, volume).
    """
    storage_service = DetectionStorageService(db)
    detections = storage_service.get_detections_by_photo(photo_id, detection_type)

    # Convert to response schemas
    detection_responses = [
        DetectionResultResponseSchema.model_validate(d) for d in detections
    ]

    return DetectionListResponseSchema(
        detections=detection_responses,
        total=len(detection_responses),
        page=1,
        page_size=len(detection_responses),
    )


@router.post("/search", response_model=DetectionListResponseSchema)
async def search_detections(
    photo_ids: Optional[List[UUID]] = None,
    detection_types: Optional[List[str]] = None,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    user_confirmed: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Search detection results with multiple filters.
    Supports pagination and various search criteria.
    """
    storage_service = DetectionStorageService(db)

    detections, total = storage_service.search_detections(
        photo_ids=photo_ids,
        detection_types=detection_types,
        min_confidence=min_confidence,
        user_confirmed=user_confirmed,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )

    # Convert to response schemas
    detection_responses = [
        DetectionResultResponseSchema.model_validate(d) for d in detections
    ]

    return DetectionListResponseSchema(
        detections=detection_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{detection_id}/history")
async def get_detection_history(
    detection_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get version history for a detection result.
    Shows all changes and who made them.
    """
    storage_service = DetectionStorageService(db)
    history = storage_service.get_detection_history(detection_id)

    if not history:
        raise HTTPException(status_code=404, detail="Detection history not found")

    return {
        "detection_id": str(detection_id),
        "total_versions": len(history),
        "history": [
            {
                "version": h.version,
                "detection_type": h.detection_type,
                "model_version": h.model_version,
                "results": h.results,
                "confidence": h.confidence,
                "change_reason": h.change_reason,
                "changed_by": str(h.changed_by) if h.changed_by else None,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
    }


@router.get("/{detection_id}/version/{version}")
async def get_detection_version(
    detection_id: UUID,
    version: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get a specific version of a detection result.
    """
    storage_service = DetectionStorageService(db)
    history_entry = storage_service.get_detection_version(detection_id, version)

    if not history_entry:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for detection {detection_id}",
        )

    return {
        "version": history_entry.version,
        "detection_id": str(detection_id),
        "detection_type": history_entry.detection_type,
        "model_version": history_entry.model_version,
        "results": history_entry.results,
        "confidence": history_entry.confidence,
        "change_reason": history_entry.change_reason,
        "changed_by": str(history_entry.changed_by) if history_entry.changed_by else None,
        "created_at": history_entry.created_at.isoformat(),
    }
