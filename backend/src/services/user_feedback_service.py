"""User feedback service for managing detection confirmations and corrections"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models.user_feedback import UserFeedback
from src.models.detection import Detection
from src.schemas.feedback_schema import FeedbackStatsSchema


class UserFeedbackService:
    """
    Service for managing user feedback on detection results.
    Tracks confirmations, rejections, and corrections for model improvement.
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db

    def submit_feedback(
        self,
        detection_id: UUID,
        user_id: UUID,
        feedback_type: str,
        corrections: Optional[Dict[str, Any]] = None,
        comments: Optional[str] = None,
    ) -> UserFeedback:
        """
        Submit user feedback on a detection result.

        Args:
            detection_id: UUID of the detection
            user_id: UUID of the user providing feedback
            feedback_type: Type of feedback (confirmed, rejected, corrected)
            corrections: Corrected values if feedback_type is 'corrected'
            comments: Optional user comments

        Returns:
            Created UserFeedback object

        Raises:
            ValueError: If detection not found or invalid feedback_type
        """
        # Validate detection exists
        detection = self.db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise ValueError(f"Detection {detection_id} not found")

        # Validate feedback type
        valid_types = ["confirmed", "rejected", "corrected"]
        if feedback_type not in valid_types:
            raise ValueError(f"Invalid feedback_type. Must be one of: {valid_types}")

        # Validate corrections for corrected feedback
        if feedback_type == "corrected" and not corrections:
            raise ValueError("Corrections required when feedback_type is 'corrected'")

        try:
            # Create feedback entry
            feedback = UserFeedback(
                detection_id=detection_id,
                user_id=user_id,
                feedback_type=feedback_type,
                corrections=corrections,
                comments=comments,
            )

            self.db.add(feedback)

            # Update detection user_confirmed flag
            if feedback_type == "confirmed":
                detection.user_confirmed = True
            elif feedback_type in ["rejected", "corrected"]:
                detection.user_confirmed = False

            # Store feedback summary in detection
            detection.user_feedback = {
                "type": feedback_type,
                "user_id": str(user_id),
                "corrections": corrections,
                "comments": comments,
            }

            self.db.commit()
            self.db.refresh(feedback)

            return feedback

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to submit feedback: {str(e)}")

    def get_feedback_by_detection(
        self, detection_id: UUID
    ) -> List[UserFeedback]:
        """
        Get all feedback for a detection.

        Args:
            detection_id: UUID of the detection

        Returns:
            List of UserFeedback objects
        """
        return (
            self.db.query(UserFeedback)
            .filter(UserFeedback.detection_id == detection_id)
            .order_by(UserFeedback.created_at)
            .all()
        )

    def get_feedback_by_user(
        self, user_id: UUID, limit: int = 100
    ) -> List[UserFeedback]:
        """
        Get feedback submitted by a user.

        Args:
            user_id: UUID of the user
            limit: Maximum number of feedback entries to return

        Returns:
            List of UserFeedback objects
        """
        return (
            self.db.query(UserFeedback)
            .filter(UserFeedback.user_id == user_id)
            .order_by(UserFeedback.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_feedback_stats(
        self, model_version: Optional[str] = None
    ) -> FeedbackStatsSchema:
        """
        Calculate feedback statistics for a model version.

        Args:
            model_version: Optional model version to filter by

        Returns:
            FeedbackStatsSchema with statistics
        """
        # Query to join feedback with detections
        query = self.db.query(
            Detection.model_version,
            func.count(UserFeedback.id).label("total_feedback"),
            func.sum(
                func.case((UserFeedback.feedback_type == "confirmed", 1), else_=0)
            ).label("confirmed"),
            func.sum(
                func.case((UserFeedback.feedback_type == "rejected", 1), else_=0)
            ).label("rejected"),
            func.sum(
                func.case((UserFeedback.feedback_type == "corrected", 1), else_=0)
            ).label("corrected"),
        ).join(
            UserFeedback, UserFeedback.detection_id == Detection.id
        )

        if model_version:
            query = query.filter(Detection.model_version == model_version)
            query = query.group_by(Detection.model_version)
            result = query.first()
        else:
            # Get overall stats
            query = query.group_by(Detection.model_version)
            results = query.all()

            # Aggregate across all versions
            if not results:
                return FeedbackStatsSchema(
                    model_version="all",
                    total_feedback=0,
                    confirmed=0,
                    rejected=0,
                    corrected=0,
                    accuracy_rate=0.0,
                )

            total_feedback = sum(r.total_feedback for r in results)
            confirmed = sum(r.confirmed for r in results)
            rejected = sum(r.rejected for r in results)
            corrected = sum(r.corrected for r in results)

            accuracy_rate = confirmed / total_feedback if total_feedback > 0 else 0.0

            return FeedbackStatsSchema(
                model_version="all",
                total_feedback=total_feedback,
                confirmed=confirmed,
                rejected=rejected,
                corrected=corrected,
                accuracy_rate=round(accuracy_rate, 4),
            )

        if not result:
            return FeedbackStatsSchema(
                model_version=model_version or "unknown",
                total_feedback=0,
                confirmed=0,
                rejected=0,
                corrected=0,
                accuracy_rate=0.0,
            )

        accuracy_rate = (
            result.confirmed / result.total_feedback
            if result.total_feedback > 0
            else 0.0
        )

        return FeedbackStatsSchema(
            model_version=result.model_version or "unknown",
            total_feedback=result.total_feedback,
            confirmed=result.confirmed,
            rejected=result.rejected,
            corrected=result.corrected,
            accuracy_rate=round(accuracy_rate, 4),
        )

    def update_feedback(
        self,
        feedback_id: UUID,
        corrections: Optional[Dict[str, Any]] = None,
        comments: Optional[str] = None,
    ) -> UserFeedback:
        """
        Update existing feedback.

        Args:
            feedback_id: UUID of the feedback
            corrections: Updated corrections
            comments: Updated comments

        Returns:
            Updated UserFeedback object

        Raises:
            ValueError: If feedback not found
        """
        feedback = self.db.query(UserFeedback).filter(UserFeedback.id == feedback_id).first()

        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        try:
            if corrections is not None:
                feedback.corrections = corrections

            if comments is not None:
                feedback.comments = comments

            self.db.commit()
            self.db.refresh(feedback)

            return feedback

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update feedback: {str(e)}")

    def delete_feedback(self, feedback_id: UUID) -> bool:
        """
        Delete feedback entry.

        Args:
            feedback_id: UUID of the feedback

        Returns:
            True if deleted, False if not found
        """
        feedback = self.db.query(UserFeedback).filter(UserFeedback.id == feedback_id).first()

        if not feedback:
            return False

        try:
            self.db.delete(feedback)
            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete feedback: {str(e)}")
