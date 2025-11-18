"""API routes for user feedback on detection results"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from src.database import get_db
from src.schemas.feedback_schema import (
    FeedbackCreateSchema,
    FeedbackResponseSchema,
    FeedbackStatsSchema,
)
from src.services.user_feedback_service import UserFeedbackService
from src.services.results_cache_service import ResultsCacheService
from src.services.redis_service import RedisService
from src.api.auth_routes import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("/", response_model=FeedbackResponseSchema)
async def submit_feedback(
    feedback: FeedbackCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit user feedback on a detection result.
    Can be confirmed, rejected, or corrected.
    Invalidates cached results when feedback is submitted.
    """
    feedback_service = UserFeedbackService(db)

    try:
        feedback_obj = feedback_service.submit_feedback(
            detection_id=feedback.detection_id,
            user_id=current_user.id,
            feedback_type=feedback.feedback_type,
            corrections=feedback.corrections,
            comments=feedback.comments,
        )

        # Invalidate cache for this detection
        redis_service = RedisService()
        cache_service = ResultsCacheService(redis_service)
        cache_service.invalidate_detection_cache(feedback.detection_id)

        return FeedbackResponseSchema.model_validate(feedback_obj)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.get("/detection/{detection_id}")
async def get_feedback_by_detection(
    detection_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all feedback for a specific detection.
    """
    feedback_service = UserFeedbackService(db)
    feedback_list = feedback_service.get_feedback_by_detection(detection_id)

    return {
        "detection_id": str(detection_id),
        "total_feedback": len(feedback_list),
        "feedback": [
            FeedbackResponseSchema.model_validate(f) for f in feedback_list
        ],
    }


@router.get("/user/me")
async def get_my_feedback(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get feedback submitted by the current user.
    """
    feedback_service = UserFeedbackService(db)
    feedback_list = feedback_service.get_feedback_by_user(current_user.id, limit)

    return {
        "user_id": str(current_user.id),
        "total_feedback": len(feedback_list),
        "feedback": [
            FeedbackResponseSchema.model_validate(f) for f in feedback_list
        ],
    }


@router.get("/stats", response_model=FeedbackStatsSchema)
async def get_feedback_stats(
    model_version: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get feedback statistics for model performance tracking.
    Optionally filter by model version.
    """
    feedback_service = UserFeedbackService(db)
    stats = feedback_service.get_feedback_stats(model_version)

    return stats


@router.put("/{feedback_id}", response_model=FeedbackResponseSchema)
async def update_feedback(
    feedback_id: UUID,
    corrections: dict = None,
    comments: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update existing feedback.
    """
    feedback_service = UserFeedbackService(db)

    try:
        feedback_obj = feedback_service.update_feedback(
            feedback_id=feedback_id,
            corrections=corrections,
            comments=comments,
        )

        return FeedbackResponseSchema.model_validate(feedback_obj)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update feedback: {str(e)}")


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete feedback entry.
    """
    feedback_service = UserFeedbackService(db)

    success = feedback_service.delete_feedback(feedback_id)

    if not success:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return {"message": "Feedback deleted successfully"}
