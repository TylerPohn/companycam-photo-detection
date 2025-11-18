"""Tests for results aggregation service"""

import pytest
from uuid import uuid4
from datetime import datetime
from src.services.results_aggregation_service import ResultsAggregationService
from src.schemas.detection_result_schema import AggregatedDetectionResultSchema


class TestResultsAggregationService:
    """Test suite for ResultsAggregationService"""

    def test_aggregate_damage_only(self):
        """Test aggregation with only damage detection results"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        damage_result = {
            "model_version": "damage-v1.2.0",
            "processing_time_ms": 500,
            "confidence": 0.92,
            "results": {
                "has_damage": True,
                "severity": "moderate",
                "damage_types": ["roof_damage", "hail_impact"],
                "affected_area": {"percentage": 25.5},
            },
        }

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            damage_result=damage_result,
            user_id=user_id,
            project_id=project_id,
        )

        assert aggregated.photo_id == photo_id
        assert aggregated.detection_id == detection_id
        assert aggregated.processing_time_ms == 500
        assert "damage" in aggregated.model_versions
        assert aggregated.summary.has_damage is True
        assert aggregated.summary.damage_severity == "moderate"
        assert len(aggregated.aggregate_tags) > 0

    def test_aggregate_material_only(self):
        """Test aggregation with only material detection results"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        material_result = {
            "model_version": "material-v1.1.0",
            "processing_time_ms": 400,
            "confidence": 0.87,
            "results": {
                "materials": [
                    {
                        "material_type": "shingles",
                        "brand": "GAF",
                        "quantity": 25,
                        "confidence": 0.9,
                    },
                    {
                        "material_type": "plywood",
                        "quantity": 10,
                        "confidence": 0.85,
                    },
                ],
                "has_variance": False,
            },
        }

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            material_result=material_result,
            user_id=user_id,
            project_id=project_id,
        )

        assert aggregated.summary.materials_detected == 2
        assert "material" in aggregated.model_versions
        # Should have delivery_confirmation tag
        tag_names = [tag.tag for tag in aggregated.aggregate_tags]
        assert "delivery_confirmation" in tag_names

    def test_aggregate_volume_only(self):
        """Test aggregation with only volume estimation results"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        volume_result = {
            "model_version": "volume-v1.0.0",
            "processing_time_ms": 350,
            "confidence": 0.78,
            "results": {
                "volume_cubic_feet": 120.5,
                "material_type": "gravel",
                "dimensions": {"length": 10, "width": 8, "height": 1.5},
            },
        }

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            volume_result=volume_result,
            user_id=user_id,
            project_id=project_id,
        )

        assert aggregated.summary.volume_estimated is True
        assert "volume" in aggregated.model_versions
        tag_names = [tag.tag for tag in aggregated.aggregate_tags]
        assert "volume_estimated" in tag_names

    def test_aggregate_all_detection_types(self):
        """Test aggregation with all detection types combined"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        damage_result = {
            "model_version": "damage-v1.2.0",
            "processing_time_ms": 500,
            "confidence": 0.92,
            "results": {
                "has_damage": True,
                "severity": "severe",
                "damage_types": ["roof_damage"],
            },
        }

        material_result = {
            "model_version": "material-v1.1.0",
            "processing_time_ms": 400,
            "confidence": 0.87,
            "results": {
                "materials": [{"material_type": "shingles", "quantity": 20}],
                "has_variance": False,
            },
        }

        volume_result = {
            "model_version": "volume-v1.0.0",
            "processing_time_ms": 350,
            "confidence": 0.78,
            "results": {"volume_cubic_feet": 100.0},
        }

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            damage_result=damage_result,
            material_result=material_result,
            volume_result=volume_result,
            user_id=user_id,
            project_id=project_id,
        )

        # Total processing time should be sum of all
        assert aggregated.processing_time_ms == 1250
        assert len(aggregated.model_versions) == 3
        assert aggregated.summary.has_damage is True
        assert aggregated.summary.materials_detected == 1
        assert aggregated.summary.volume_estimated is True

        # Should have multi_detection tag
        tag_names = [tag.tag for tag in aggregated.aggregate_tags]
        assert "multi_detection" in tag_names

    def test_validate_detection_result_valid(self):
        """Test validation of valid detection results"""
        damage_result = {
            "results": {"has_damage": True},
            "confidence": 0.9,
        }

        assert ResultsAggregationService.validate_detection_result("damage", damage_result)

    def test_validate_detection_result_invalid(self):
        """Test validation of invalid detection results"""
        # Missing required field
        invalid_result = {
            "results": {"has_damage": True},
            # Missing confidence
        }

        assert not ResultsAggregationService.validate_detection_result(
            "damage", invalid_result
        )

        # Invalid confidence range
        invalid_confidence = {
            "results": {"has_damage": True},
            "confidence": 1.5,  # Out of range
        }

        assert not ResultsAggregationService.validate_detection_result(
            "damage", invalid_confidence
        )

    def test_generate_aggregate_tags_damage_severity(self):
        """Test tag generation for different damage severity levels"""
        damage_result_severe = {
            "confidence": 0.95,
            "results": {
                "has_damage": True,
                "severity": "severe",
                "damage_types": ["roof_damage"],
            },
        }

        tags = ResultsAggregationService._generate_aggregate_tags(
            damage_result_severe, None, None
        )

        tag_names = [tag.tag for tag in tags]
        assert "damage_severe" in tag_names
        assert "insurance_claim" in tag_names  # Should add insurance claim for severe

    def test_user_confirmation_default_pending(self):
        """Test that user confirmation defaults to pending"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            user_id=user_id,
            project_id=project_id,
        )

        assert aggregated.user_confirmation.status == "pending"
        assert aggregated.user_confirmation.confirmed_by is None
        assert aggregated.user_confirmation.confirmed_at is None

    def test_metadata_populated(self):
        """Test that metadata is properly populated"""
        photo_id = uuid4()
        detection_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        aggregated = ResultsAggregationService.aggregate_results(
            photo_id=photo_id,
            detection_id=detection_id,
            user_id=user_id,
            project_id=project_id,
            processing_region="us-west-2",
        )

        assert aggregated.metadata.project_id == project_id
        assert aggregated.metadata.user_id == user_id
        assert aggregated.metadata.processing_region == "us-west-2"
        assert aggregated.metadata.api_version == "v1"
