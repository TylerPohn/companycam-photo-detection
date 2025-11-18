"""Tests for tags service"""

import pytest
from uuid import uuid4
from src.services.tags_service import TagsService


class TestTagsService:
    """Test suite for TagsService"""

    @pytest.fixture
    def tags_service(self, test_db):
        """Create TagsService instance"""
        return TagsService(test_db)

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

    def test_generate_tags_from_damage_detection(self, tags_service, sample_photo):
        """Test generating tags from damage detection results"""
        damage_result = {
            "confidence": 0.92,
            "results": {
                "has_damage": True,
                "severity": "severe",
                "damage_types": ["roof_damage", "hail_impact"],
            },
        }

        tags = tags_service.generate_tags_from_detections(
            photo_id=sample_photo.id,
            damage_result=damage_result,
        )

        assert len(tags) > 0
        tag_names = [tag.tag for tag in tags]
        assert "damage_severe" in tag_names
        assert "roof_damage" in tag_names
        assert "insurance_claim" in tag_names  # Severe damage should trigger insurance claim

    def test_generate_tags_from_material_detection(self, tags_service, sample_photo):
        """Test generating tags from material detection results"""
        material_result = {
            "confidence": 0.87,
            "results": {
                "materials": [
                    {"material_type": "shingles", "brand": "GAF", "quantity": 20},
                ],
                "has_variance": False,
            },
        }

        tags = tags_service.generate_tags_from_detections(
            photo_id=sample_photo.id,
            material_result=material_result,
        )

        tag_names = [tag.tag for tag in tags]
        assert "delivery_confirmation" in tag_names
        assert "material_shingles" in tag_names
        assert "brand_GAF" in tag_names

    def test_generate_tags_from_volume_estimation(self, tags_service, sample_photo):
        """Test generating tags from volume estimation results"""
        volume_result = {
            "confidence": 0.75,
            "results": {
                "volume_cubic_feet": 120.5,
                "material_type": "gravel",
            },
        }

        tags = tags_service.generate_tags_from_detections(
            photo_id=sample_photo.id,
            volume_result=volume_result,
        )

        tag_names = [tag.tag for tag in tags]
        assert "volume_estimated" in tag_names
        assert "volume_gravel" in tag_names

    def test_add_user_tag(self, tags_service, sample_photo, sample_user):
        """Test adding a user-generated tag"""
        tag = tags_service.add_user_tag(
            photo_id=sample_photo.id,
            tag="custom_tag",
            user_id=sample_user.id,
        )

        assert tag.photo_id == sample_photo.id
        assert tag.tag == "custom_tag"
        assert tag.source == "user"
        assert tag.confidence is None

    def test_get_tags_by_photo(self, tags_service, sample_photo):
        """Test retrieving tags for a photo"""
        tags_service.add_user_tag(
            photo_id=sample_photo.id,
            tag="test_tag1",
        )

        tags_service.add_user_tag(
            photo_id=sample_photo.id,
            tag="test_tag2",
        )

        tags = tags_service.get_tags_by_photo(sample_photo.id)

        assert len(tags) >= 2

    def test_remove_tag(self, tags_service, sample_photo):
        """Test removing a tag"""
        tag = tags_service.add_user_tag(
            photo_id=sample_photo.id,
            tag="to_be_removed",
        )

        result = tags_service.remove_tag(tag.id)

        assert result is True

        # Verify tag is gone
        tags = tags_service.get_tags_by_photo(sample_photo.id)
        tag_ids = [t.id for t in tags]
        assert tag.id not in tag_ids

    def test_search_photos_by_tags(self, tags_service, sample_photo):
        """Test searching photos by tags"""
        tags_service.add_user_tag(
            photo_id=sample_photo.id,
            tag="searchable_tag",
        )

        photo_ids = tags_service.search_photos_by_tags(["searchable_tag"])

        assert sample_photo.id in photo_ids

    def test_cross_detection_tags(self, tags_service, sample_photo):
        """Test cross-detection tag generation"""
        damage_result = {
            "confidence": 0.92,
            "results": {"has_damage": True, "severity": "moderate"},
        }

        material_result = {
            "confidence": 0.87,
            "results": {"materials": [{"material_type": "shingles"}]},
        }

        tags = tags_service.generate_tags_from_detections(
            photo_id=sample_photo.id,
            damage_result=damage_result,
            material_result=material_result,
        )

        tag_names = [tag.tag for tag in tags]
        assert "multi_detection" in tag_names
        assert "potential_claim" in tag_names  # Both damage and material should trigger this
