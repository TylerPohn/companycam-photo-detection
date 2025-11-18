"""Tests for user feedback service"""

import pytest
from uuid import uuid4
from src.services.user_feedback_service import UserFeedbackService


class TestUserFeedbackService:
    """Test suite for UserFeedbackService"""

    @pytest.fixture
    def feedback_service(self, test_db):
        """Create UserFeedbackService instance"""
        return UserFeedbackService(test_db)

    @pytest.fixture
    def sample_detection(self, test_db, sample_user, sample_project):
        """Create sample detection for testing"""
        from src.models.photo import Photo, PhotoStatus
        from src.models.detection import Detection

        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/bucket/test.jpg",
            s3_key="test.jpg",
            status=PhotoStatus.UPLOADED,
        )
        test_db.add(photo)
        test_db.commit()

        detection = Detection(
            photo_id=photo.id,
            detection_type="damage",
            model_version="v1.0.0",
            results={"has_damage": True},
            confidence=0.9,
        )
        test_db.add(detection)
        test_db.commit()
        test_db.refresh(detection)
        return detection

    def test_submit_confirmed_feedback(self, feedback_service, sample_detection, sample_user):
        """Test submitting confirmed feedback"""
        feedback = feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
            comments="Looks accurate",
        )

        assert feedback.detection_id == sample_detection.id
        assert feedback.user_id == sample_user.id
        assert feedback.feedback_type == "confirmed"
        assert feedback.comments == "Looks accurate"

    def test_submit_rejected_feedback(self, feedback_service, sample_detection, sample_user):
        """Test submitting rejected feedback"""
        feedback = feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="rejected",
            comments="Incorrect detection",
        )

        assert feedback.feedback_type == "rejected"

    def test_submit_corrected_feedback(self, feedback_service, sample_detection, sample_user):
        """Test submitting corrected feedback with corrections"""
        corrections = {
            "severity": "moderate",  # Corrected severity
            "damage_types": ["roof_damage"],
        }

        feedback = feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="corrected",
            corrections=corrections,
            comments="Updated severity",
        )

        assert feedback.feedback_type == "corrected"
        assert feedback.corrections == corrections

    def test_submit_corrected_without_corrections_raises_error(
        self, feedback_service, sample_detection, sample_user
    ):
        """Test that corrected feedback without corrections raises error"""
        with pytest.raises(ValueError, match="Corrections required"):
            feedback_service.submit_feedback(
                detection_id=sample_detection.id,
                user_id=sample_user.id,
                feedback_type="corrected",
                # Missing corrections
            )

    def test_submit_feedback_invalid_type_raises_error(
        self, feedback_service, sample_detection, sample_user
    ):
        """Test that invalid feedback type raises error"""
        with pytest.raises(ValueError, match="Invalid feedback_type"):
            feedback_service.submit_feedback(
                detection_id=sample_detection.id,
                user_id=sample_user.id,
                feedback_type="invalid_type",
            )

    def test_submit_feedback_nonexistent_detection_raises_error(
        self, feedback_service, sample_user
    ):
        """Test that feedback on nonexistent detection raises error"""
        fake_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            feedback_service.submit_feedback(
                detection_id=fake_id,
                user_id=sample_user.id,
                feedback_type="confirmed",
            )

    def test_get_feedback_by_detection(
        self, feedback_service, sample_detection, sample_user
    ):
        """Test retrieving feedback for a detection"""
        feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
        )

        feedback_list = feedback_service.get_feedback_by_detection(sample_detection.id)

        assert len(feedback_list) >= 1
        assert feedback_list[0].detection_id == sample_detection.id

    def test_get_feedback_by_user(self, feedback_service, sample_detection, sample_user):
        """Test retrieving feedback by user"""
        feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
        )

        feedback_list = feedback_service.get_feedback_by_user(sample_user.id)

        assert len(feedback_list) >= 1
        assert feedback_list[0].user_id == sample_user.id

    def test_get_feedback_stats(self, feedback_service, sample_detection, sample_user):
        """Test calculating feedback statistics"""
        # Submit multiple feedback entries
        feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
        )

        stats = feedback_service.get_feedback_stats(model_version="v1.0.0")

        assert stats.model_version == "v1.0.0"
        assert stats.total_feedback >= 1
        assert stats.confirmed >= 1
        assert stats.accuracy_rate >= 0.0

    def test_update_feedback(self, feedback_service, sample_detection, sample_user):
        """Test updating existing feedback"""
        feedback = feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
            comments="Initial comment",
        )

        updated = feedback_service.update_feedback(
            feedback_id=feedback.id,
            comments="Updated comment",
        )

        assert updated.comments == "Updated comment"

    def test_delete_feedback(self, feedback_service, sample_detection, sample_user):
        """Test deleting feedback"""
        feedback = feedback_service.submit_feedback(
            detection_id=sample_detection.id,
            user_id=sample_user.id,
            feedback_type="confirmed",
        )

        result = feedback_service.delete_feedback(feedback.id)

        assert result is True

        # Verify it's deleted
        feedback_list = feedback_service.get_feedback_by_detection(sample_detection.id)
        feedback_ids = [f.id for f in feedback_list]
        assert feedback.id not in feedback_ids
