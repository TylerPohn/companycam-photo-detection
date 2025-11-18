"""Tests for report generation"""

import pytest
from uuid import uuid4
from src.reports.insurance_report_generator import InsuranceReportGenerator
from src.reports.delivery_report_generator import DeliveryReportGenerator


class TestInsuranceReportGenerator:
    """Test suite for InsuranceReportGenerator"""

    @pytest.fixture
    def report_generator(self, test_db):
        """Create InsuranceReportGenerator instance"""
        return InsuranceReportGenerator(test_db)

    @pytest.fixture
    def sample_project_with_damage(self, test_db, sample_user, sample_project):
        """Create sample project with damage detections"""
        from src.models.photo import Photo, PhotoStatus
        from src.models.detection import Detection

        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/bucket/test.jpg",
            s3_key="test.jpg",
            status=PhotoStatus.COMPLETED,
        )
        test_db.add(photo)
        test_db.commit()

        detection = Detection(
            photo_id=photo.id,
            detection_type="damage",
            model_version="v1.0.0",
            results={
                "has_damage": True,
                "severity": "severe",
                "damage_types": ["roof_damage", "hail_impact"],
                "affected_area": {"percentage": 30.5},
            },
            confidence=0.92,
        )
        test_db.add(detection)
        test_db.commit()

        return sample_project

    def test_generate_insurance_report(self, report_generator, sample_project_with_damage):
        """Test generating insurance claim report"""
        report = report_generator.generate_report(sample_project_with_damage.id)

        assert report["report_type"] == "insurance_claim"
        assert "project" in report
        assert "summary" in report
        assert "damage_items" in report
        assert "recommendations" in report

    def test_insurance_report_summary(self, report_generator, sample_project_with_damage):
        """Test insurance report summary statistics"""
        report = report_generator.generate_report(sample_project_with_damage.id)

        summary = report["summary"]
        assert summary["total_photos_with_damage"] >= 1
        assert "severity_breakdown" in summary
        assert "severe" in summary["severity_breakdown"]

    def test_insurance_report_recommendations(
        self, report_generator, sample_project_with_damage
    ):
        """Test insurance report recommendations"""
        report = report_generator.generate_report(sample_project_with_damage.id)

        recommendations = report["recommendations"]
        assert len(recommendations) > 0
        # Should have recommendation for severe damage
        assert any("severe" in str(r).lower() for r in recommendations)


class TestDeliveryReportGenerator:
    """Test suite for DeliveryReportGenerator"""

    @pytest.fixture
    def report_generator(self, test_db):
        """Create DeliveryReportGenerator instance"""
        return DeliveryReportGenerator(test_db)

    @pytest.fixture
    def sample_project_with_materials(self, test_db, sample_user, sample_project):
        """Create sample project with material detections"""
        from src.models.photo import Photo, PhotoStatus
        from src.models.detection import Detection

        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/bucket/test.jpg",
            s3_key="test.jpg",
            status=PhotoStatus.COMPLETED,
        )
        test_db.add(photo)
        test_db.commit()

        detection = Detection(
            photo_id=photo.id,
            detection_type="material",
            model_version="v1.0.0",
            results={
                "materials": [
                    {
                        "material_type": "shingles",
                        "brand": "GAF",
                        "quantity": 25,
                        "confidence": 0.9,
                    },
                ],
                "has_variance": False,
            },
            confidence=0.87,
        )
        test_db.add(detection)
        test_db.commit()

        return sample_project

    def test_generate_delivery_report(
        self, report_generator, sample_project_with_materials
    ):
        """Test generating delivery verification report"""
        report = report_generator.generate_report(sample_project_with_materials.id)

        assert report["report_type"] == "delivery_verification"
        assert "project" in report
        assert "summary" in report
        assert "material_items" in report
        assert "variance_alerts" in report

    def test_delivery_report_summary(
        self, report_generator, sample_project_with_materials
    ):
        """Test delivery report summary statistics"""
        report = report_generator.generate_report(sample_project_with_materials.id)

        summary = report["summary"]
        assert summary["total_photos"] >= 1
        assert summary["total_materials_detected"] >= 25
        assert "material_breakdown" in summary

    def test_delivery_report_variance_detection(
        self, report_generator, sample_project_with_materials
    ):
        """Test delivery report variance detection"""
        expected_materials = {
            "shingles": 30,  # Expected 30 but detected 25
        }

        report = report_generator.generate_report(
            sample_project_with_materials.id,
            expected_materials=expected_materials,
        )

        variance_alerts = report["variance_alerts"]
        assert len(variance_alerts) >= 1

        # Find shingles variance
        shingles_variance = next(
            (v for v in variance_alerts if v["material_type"] == "shingles"),
            None,
        )
        assert shingles_variance is not None
        assert shingles_variance["expected"] == 30
        assert shingles_variance["actual"] == 25
        assert shingles_variance["variance"] == -5
