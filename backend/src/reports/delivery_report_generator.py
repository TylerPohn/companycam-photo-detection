"""Delivery verification report generator"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from src.models.detection import Detection
from src.models.photo import Photo
from src.models.project import Project


class DeliveryReportGenerator:
    """
    Generator for delivery verification reports based on material detections.
    Produces reports with material counts, photos, and variance alerts.
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db

    def generate_report(
        self,
        project_id: UUID,
        expected_materials: Optional[Dict[str, int]] = None,
        include_photos: bool = True,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Generate delivery verification report for a project.

        Args:
            project_id: UUID of the project
            expected_materials: Expected material counts for variance detection
            include_photos: Whether to include photo URLs
            format: Output format (json or pdf)

        Returns:
            Report dictionary
        """
        # Get project information
        project = self.db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get all material detections for the project
        material_detections = (
            self.db.query(Detection, Photo)
            .join(Photo, Detection.photo_id == Photo.id)
            .filter(Photo.project_id == project_id)
            .filter(Detection.detection_type == "material")
            .order_by(Detection.created_at)
            .all()
        )

        # Generate report sections
        report = {
            "report_type": "delivery_verification",
            "generated_at": datetime.utcnow().isoformat(),
            "project": self._format_project_info(project),
            "summary": self._generate_summary(material_detections, expected_materials),
            "material_items": self._format_material_items(material_detections, include_photos),
            "variance_alerts": self._generate_variance_alerts(
                material_detections, expected_materials
            ),
        }

        return report

    def generate_batch_report(
        self,
        project_ids: List[UUID],
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Generate batch delivery verification report for multiple projects.

        Args:
            project_ids: List of project UUIDs
            format: Output format

        Returns:
            Batch report dictionary
        """
        reports = []

        for project_id in project_ids:
            try:
                report = self.generate_report(project_id, format=format)
                reports.append(report)
            except Exception as e:
                reports.append({
                    "project_id": str(project_id),
                    "error": str(e),
                })

        return {
            "report_type": "delivery_verification_batch",
            "generated_at": datetime.utcnow().isoformat(),
            "total_projects": len(project_ids),
            "reports": reports,
        }

    def _format_project_info(self, project: Project) -> Dict[str, Any]:
        """Format project information for report"""
        return {
            "id": str(project.id),
            "name": project.name,
            "address": getattr(project, "address", None),
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }

    def _generate_summary(
        self,
        material_detections: List[tuple[Detection, Photo]],
        expected_materials: Optional[Dict[str, int]],
    ) -> Dict[str, Any]:
        """Generate summary statistics for the report"""
        if not material_detections:
            return {
                "total_photos": 0,
                "total_materials_detected": 0,
                "material_breakdown": {},
                "has_variance": False,
            }

        # Aggregate material counts
        material_counts = {}
        brand_counts = {}

        for detection, photo in material_detections:
            results = detection.results
            materials = results.get("materials", [])

            for material in materials:
                material_type = material.get("material_type", "unknown")
                quantity = material.get("quantity", 1)

                material_counts[material_type] = (
                    material_counts.get(material_type, 0) + quantity
                )

                # Track brands
                brand = material.get("brand")
                if brand:
                    brand_counts[brand] = brand_counts.get(brand, 0) + quantity

        # Check for variance
        has_variance = False
        if expected_materials:
            for material_type, expected_count in expected_materials.items():
                actual_count = material_counts.get(material_type, 0)
                if actual_count != expected_count:
                    has_variance = True
                    break

        return {
            "total_photos": len(material_detections),
            "total_materials_detected": sum(material_counts.values()),
            "material_breakdown": material_counts,
            "brand_breakdown": brand_counts,
            "has_variance": has_variance,
        }

    def _format_material_items(
        self,
        material_detections: List[tuple[Detection, Photo]],
        include_photos: bool,
    ) -> List[Dict[str, Any]]:
        """Format individual material items for report"""
        items = []

        for detection, photo in material_detections:
            results = detection.results

            item = {
                "detection_id": str(detection.id),
                "photo_id": str(photo.id),
                "detected_at": detection.created_at.isoformat(),
                "confidence": detection.confidence,
                "materials": results.get("materials", []),
                "total_quantity": sum(
                    m.get("quantity", 1) for m in results.get("materials", [])
                ),
                "user_confirmed": detection.user_confirmed,
            }

            if include_photos:
                item["photo_url"] = photo.s3_url

            items.append(item)

        return items

    def _generate_variance_alerts(
        self,
        material_detections: List[tuple[Detection, Photo]],
        expected_materials: Optional[Dict[str, int]],
    ) -> List[Dict[str, Any]]:
        """Generate variance alerts by comparing expected vs actual counts"""
        if not expected_materials:
            return []

        # Calculate actual counts
        material_counts = {}

        for detection, photo in material_detections:
            results = detection.results
            materials = results.get("materials", [])

            for material in materials:
                material_type = material.get("material_type", "unknown")
                quantity = material.get("quantity", 1)

                material_counts[material_type] = (
                    material_counts.get(material_type, 0) + quantity
                )

        # Generate variance alerts
        alerts = []

        for material_type, expected_count in expected_materials.items():
            actual_count = material_counts.get(material_type, 0)

            if actual_count != expected_count:
                variance = actual_count - expected_count
                variance_pct = (variance / expected_count * 100) if expected_count > 0 else 0

                alert = {
                    "material_type": material_type,
                    "expected": expected_count,
                    "actual": actual_count,
                    "variance": variance,
                    "variance_percentage": round(variance_pct, 2),
                    "severity": self._determine_variance_severity(variance_pct),
                }

                alerts.append(alert)

        # Check for unexpected materials
        for material_type in material_counts.keys():
            if material_type not in expected_materials:
                alerts.append({
                    "material_type": material_type,
                    "expected": 0,
                    "actual": material_counts[material_type],
                    "variance": material_counts[material_type],
                    "variance_percentage": None,
                    "severity": "warning",
                    "note": "Unexpected material detected",
                })

        return alerts

    @staticmethod
    def _determine_variance_severity(variance_pct: float) -> str:
        """Determine severity level based on variance percentage"""
        abs_variance = abs(variance_pct)

        if abs_variance > 20:
            return "critical"
        elif abs_variance > 10:
            return "warning"
        else:
            return "info"
