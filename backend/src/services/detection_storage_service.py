"""Detection storage service for database operations on detection results"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from src.models.detection import Detection
from src.models.detection_history import DetectionHistory
from src.models.tag import Tag
from src.models.user_feedback import UserFeedback
from src.schemas.detection_result_schema import DetectionResultResponseSchema


class DetectionStorageService:
    """
    Service for storing and retrieving detection results from PostgreSQL database.
    Handles transactions, versioning, and relationships.
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db

    def store_detection_result(
        self,
        photo_id: UUID,
        detection_type: str,
        model_version: str,
        results: Dict[str, Any],
        confidence: float,
        processing_time_ms: int,
        create_history: bool = True,
    ) -> Detection:
        """
        Store detection result in database with transaction handling.

        Args:
            photo_id: UUID of the photo
            detection_type: Type of detection (damage, material, volume)
            model_version: Model version used
            results: Detection results as dict
            confidence: Overall confidence score
            processing_time_ms: Processing time in milliseconds
            create_history: Whether to create history entry

        Returns:
            Detection object
        """
        try:
            # Create detection record
            detection = Detection(
                photo_id=photo_id,
                detection_type=detection_type,
                model_version=model_version,
                results=results,
                confidence=confidence,
                processing_time_ms=processing_time_ms,
                user_confirmed=False,
                user_feedback=None,
            )

            self.db.add(detection)
            self.db.flush()  # Flush to get the detection ID

            # Create initial history entry if requested
            if create_history:
                self._create_history_entry(
                    detection_id=detection.id,
                    version=1,
                    detection_type=detection_type,
                    model_version=model_version,
                    results=results,
                    confidence=confidence,
                    change_reason="Initial detection",
                    changed_by=None,
                )

            self.db.commit()
            self.db.refresh(detection)

            return detection

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to store detection result: {str(e)}")

    def update_detection_result(
        self,
        detection_id: UUID,
        results: Dict[str, Any],
        confidence: float,
        user_id: Optional[UUID] = None,
        change_reason: str = "Updated detection",
    ) -> Detection:
        """
        Update existing detection result and create history entry.

        Args:
            detection_id: UUID of the detection
            results: Updated detection results
            confidence: Updated confidence score
            user_id: User who made the update
            change_reason: Reason for the change

        Returns:
            Updated Detection object
        """
        try:
            detection = self.db.query(Detection).filter(Detection.id == detection_id).first()

            if not detection:
                raise ValueError(f"Detection {detection_id} not found")

            # Get current version number
            latest_history = (
                self.db.query(DetectionHistory)
                .filter(DetectionHistory.detection_id == detection_id)
                .order_by(desc(DetectionHistory.version))
                .first()
            )

            next_version = (latest_history.version + 1) if latest_history else 1

            # Create history entry for current state before updating
            self._create_history_entry(
                detection_id=detection_id,
                version=next_version,
                detection_type=detection.detection_type,
                model_version=detection.model_version,
                results=results,
                confidence=confidence,
                change_reason=change_reason,
                changed_by=user_id,
            )

            # Update detection
            detection.results = results
            detection.confidence = confidence

            self.db.commit()
            self.db.refresh(detection)

            return detection

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update detection result: {str(e)}")

    def get_detection_by_id(self, detection_id: UUID) -> Optional[Detection]:
        """
        Retrieve detection by ID.

        Args:
            detection_id: UUID of the detection

        Returns:
            Detection object or None if not found
        """
        return self.db.query(Detection).filter(Detection.id == detection_id).first()

    def get_detections_by_photo(
        self, photo_id: UUID, detection_type: Optional[str] = None
    ) -> List[Detection]:
        """
        Get all detections for a photo, optionally filtered by type.

        Args:
            photo_id: UUID of the photo
            detection_type: Optional detection type filter

        Returns:
            List of Detection objects
        """
        query = self.db.query(Detection).filter(Detection.photo_id == photo_id)

        if detection_type:
            query = query.filter(Detection.detection_type == detection_type)

        return query.order_by(Detection.created_at).all()

    def search_detections(
        self,
        photo_ids: Optional[List[UUID]] = None,
        detection_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        user_confirmed: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Detection], int]:
        """
        Search detections with multiple filters.

        Args:
            photo_ids: List of photo IDs to filter by
            detection_types: List of detection types to filter by
            min_confidence: Minimum confidence threshold
            user_confirmed: Filter by user confirmation status
            start_date: Start of date range
            end_date: End of date range
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (list of Detection objects, total count)
        """
        query = self.db.query(Detection)

        # Apply filters
        if photo_ids:
            query = query.filter(Detection.photo_id.in_(photo_ids))

        if detection_types:
            query = query.filter(Detection.detection_type.in_(detection_types))

        if min_confidence is not None:
            query = query.filter(Detection.confidence >= min_confidence)

        if user_confirmed is not None:
            query = query.filter(Detection.user_confirmed == user_confirmed)

        if start_date:
            query = query.filter(Detection.created_at >= start_date)

        if end_date:
            query = query.filter(Detection.created_at <= end_date)

        # Get total count
        total_count = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        results = query.order_by(desc(Detection.created_at)).offset(offset).limit(page_size).all()

        return results, total_count

    def store_tags(self, photo_id: UUID, tags: List[Dict[str, Any]]) -> List[Tag]:
        """
        Store tags for a photo.

        Args:
            photo_id: UUID of the photo
            tags: List of tag dictionaries with 'tag', 'source', 'confidence'

        Returns:
            List of created Tag objects
        """
        try:
            tag_objects = []

            for tag_data in tags:
                tag = Tag(
                    photo_id=photo_id,
                    tag=tag_data["tag"],
                    source=tag_data.get("source", "ai"),
                    confidence=tag_data.get("confidence"),
                )
                self.db.add(tag)
                tag_objects.append(tag)

            self.db.commit()

            for tag in tag_objects:
                self.db.refresh(tag)

            return tag_objects

        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to store tags: {str(e)}")

    def get_tags_by_photo(self, photo_id: UUID) -> List[Tag]:
        """
        Get all tags for a photo.

        Args:
            photo_id: UUID of the photo

        Returns:
            List of Tag objects
        """
        return self.db.query(Tag).filter(Tag.photo_id == photo_id).all()

    def _create_history_entry(
        self,
        detection_id: UUID,
        version: int,
        detection_type: str,
        model_version: str,
        results: Dict[str, Any],
        confidence: float,
        change_reason: str,
        changed_by: Optional[UUID],
    ) -> DetectionHistory:
        """
        Create a history entry for detection versioning.

        Args:
            detection_id: UUID of the detection
            version: Version number
            detection_type: Type of detection
            model_version: Model version
            results: Detection results
            confidence: Confidence score
            change_reason: Reason for the change
            changed_by: User who made the change

        Returns:
            DetectionHistory object
        """
        history = DetectionHistory(
            detection_id=detection_id,
            version=version,
            detection_type=detection_type,
            model_version=model_version,
            results=results,
            confidence=confidence,
            change_reason=change_reason,
            changed_by=changed_by,
        )

        self.db.add(history)
        return history

    def get_detection_history(
        self, detection_id: UUID
    ) -> List[DetectionHistory]:
        """
        Get version history for a detection.

        Args:
            detection_id: UUID of the detection

        Returns:
            List of DetectionHistory objects ordered by version
        """
        return (
            self.db.query(DetectionHistory)
            .filter(DetectionHistory.detection_id == detection_id)
            .order_by(DetectionHistory.version)
            .all()
        )

    def get_detection_version(
        self, detection_id: UUID, version: int
    ) -> Optional[DetectionHistory]:
        """
        Get a specific version of a detection.

        Args:
            detection_id: UUID of the detection
            version: Version number

        Returns:
            DetectionHistory object or None if not found
        """
        return (
            self.db.query(DetectionHistory)
            .filter(
                and_(
                    DetectionHistory.detection_id == detection_id,
                    DetectionHistory.version == version,
                )
            )
            .first()
        )
