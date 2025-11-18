"""Tests for detection storage service"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from src.services.detection_storage_service import DetectionStorageService
from src.models.detection import Detection


class TestDetectionStorageService:
    """Test suite for DetectionStorageService"""

    @pytest.fixture
    def storage_service(self, test_db):
        """Create DetectionStorageService instance"""
        return DetectionStorageService(test_db)

    @pytest.fixture
    def sample_photo(self, test_db, sample_user, sample_project):
        """Create sample photo for testing"""
        from src.models.photo import Photo, PhotoStatus

        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/bucket/test.jpg",
            s3_key="test.jpg",
            status=PhotoStatus.UPLOADED,
        )
        test_db.add(photo)
        test_db.commit()
        test_db.refresh(photo)
        return photo

    def test_store_detection_result(self, storage_service, sample_photo):
        """Test storing a detection result"""
        results = {
            "has_damage": True,
            "severity": "moderate",
            "damage_types": ["roof_damage"],
        }

        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="damage-v1.2.0",
            results=results,
            confidence=0.92,
            processing_time_ms=500,
        )

        assert detection.id is not None
        assert detection.photo_id == sample_photo.id
        assert detection.detection_type == "damage"
        assert detection.model_version == "damage-v1.2.0"
        assert detection.results == results
        assert detection.confidence == 0.92
        assert detection.processing_time_ms == 500
        assert detection.user_confirmed is False

    def test_store_detection_creates_history(self, storage_service, sample_photo):
        """Test that storing detection creates history entry"""
        results = {"has_damage": True}

        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="damage-v1.0.0",
            results=results,
            confidence=0.9,
            processing_time_ms=400,
            create_history=True,
        )

        # Retrieve history
        history = storage_service.get_detection_history(detection.id)

        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].detection_id == detection.id
        assert history[0].change_reason == "Initial detection"

    def test_update_detection_result(self, storage_service, sample_photo, sample_user):
        """Test updating an existing detection result"""
        # Create initial detection
        initial_results = {"has_damage": True, "severity": "moderate"}

        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="damage-v1.0.0",
            results=initial_results,
            confidence=0.85,
            processing_time_ms=400,
        )

        # Update detection
        updated_results = {"has_damage": True, "severity": "severe"}

        updated = storage_service.update_detection_result(
            detection_id=detection.id,
            results=updated_results,
            confidence=0.92,
            user_id=sample_user.id,
            change_reason="User correction",
        )

        assert updated.id == detection.id
        assert updated.results == updated_results
        assert updated.confidence == 0.92

        # Check history was created
        history = storage_service.get_detection_history(detection.id)
        assert len(history) > 0

    def test_get_detection_by_id(self, storage_service, sample_photo):
        """Test retrieving detection by ID"""
        results = {"has_damage": False}

        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="damage-v1.0.0",
            results=results,
            confidence=0.95,
            processing_time_ms=300,
        )

        retrieved = storage_service.get_detection_by_id(detection.id)

        assert retrieved is not None
        assert retrieved.id == detection.id
        assert retrieved.results == results

    def test_get_detections_by_photo(self, storage_service, sample_photo):
        """Test retrieving all detections for a photo"""
        # Create multiple detections
        for detection_type in ["damage", "material", "volume"]:
            storage_service.store_detection_result(
                photo_id=sample_photo.id,
                detection_type=detection_type,
                model_version=f"{detection_type}-v1.0.0",
                results={"test": True},
                confidence=0.9,
                processing_time_ms=400,
            )

        detections = storage_service.get_detections_by_photo(sample_photo.id)

        assert len(detections) == 3

        # Test filtering by type
        damage_detections = storage_service.get_detections_by_photo(
            sample_photo.id, detection_type="damage"
        )

        assert len(damage_detections) == 1
        assert damage_detections[0].detection_type == "damage"

    def test_search_detections_by_confidence(self, storage_service, sample_photo):
        """Test searching detections by minimum confidence"""
        # Create detections with different confidences
        storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1",
            results={"test": True},
            confidence=0.95,
            processing_time_ms=400,
        )

        storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="material",
            model_version="v1",
            results={"test": True},
            confidence=0.75,
            processing_time_ms=400,
        )

        # Search with min confidence
        results, total = storage_service.search_detections(min_confidence=0.9)

        assert total >= 1
        for detection in results:
            assert detection.confidence >= 0.9

    def test_search_detections_by_date_range(self, storage_service, sample_photo):
        """Test searching detections by date range"""
        now = datetime.utcnow()

        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1",
            results={"test": True},
            confidence=0.9,
            processing_time_ms=400,
        )

        # Search within date range
        results, total = storage_service.search_detections(
            start_date=now - timedelta(minutes=5),
            end_date=now + timedelta(minutes=5),
        )

        assert total >= 1

    def test_search_detections_pagination(self, storage_service, sample_photo):
        """Test pagination in search results"""
        # Create multiple detections
        for i in range(10):
            storage_service.store_detection_result(
                photo_id=sample_photo.id,
                detection_type="damage",
                model_version="v1",
                results={"index": i},
                confidence=0.9,
                processing_time_ms=400,
            )

        # Get first page
        page1, total = storage_service.search_detections(
            photo_ids=[sample_photo.id],
            page=1,
            page_size=5,
        )

        assert len(page1) == 5
        assert total >= 10

        # Get second page
        page2, _ = storage_service.search_detections(
            photo_ids=[sample_photo.id],
            page=2,
            page_size=5,
        )

        assert len(page2) >= 5
        # Results should be different
        assert page1[0].id != page2[0].id

    def test_store_tags(self, storage_service, sample_photo):
        """Test storing tags for a photo"""
        tags_data = [
            {"tag": "roof_damage", "source": "ai", "confidence": 0.92},
            {"tag": "insurance_claim", "source": "ai", "confidence": 0.88},
        ]

        tags = storage_service.store_tags(sample_photo.id, tags_data)

        assert len(tags) == 2
        assert tags[0].photo_id == sample_photo.id
        assert tags[0].tag == "roof_damage"
        assert tags[0].source == "ai"

    def test_get_tags_by_photo(self, storage_service, sample_photo):
        """Test retrieving tags for a photo"""
        tags_data = [
            {"tag": "damage_severe", "source": "ai", "confidence": 0.9},
        ]

        storage_service.store_tags(sample_photo.id, tags_data)

        tags = storage_service.get_tags_by_photo(sample_photo.id)

        assert len(tags) >= 1
        assert tags[0].photo_id == sample_photo.id

    def test_get_detection_version(self, storage_service, sample_photo, sample_user):
        """Test retrieving specific version of detection"""
        # Create detection with history
        detection = storage_service.store_detection_result(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1",
            results={"version": 1},
            confidence=0.85,
            processing_time_ms=400,
            create_history=True,
        )

        # Update to create version 2
        storage_service.update_detection_result(
            detection_id=detection.id,
            results={"version": 2},
            confidence=0.90,
            user_id=sample_user.id,
            change_reason="Update",
        )

        # Retrieve version 1
        version1 = storage_service.get_detection_version(detection.id, 1)

        assert version1 is not None
        assert version1.version == 1
        assert version1.results == {"version": 1}
