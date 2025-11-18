"""Insurance claim report generator"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from src.models.detection import Detection
from src.models.photo import Photo
from src.models.project import Project


class InsuranceReportGenerator:
    """
    Generator for insurance claim reports based on damage detections.
    Produces structured reports with photos, damage severity, and cost estimates.
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db

    def generate_report(
        self,
        project_id: UUID,
        include_photos: bool = True,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Generate insurance claim report for a project.

        Args:
            project_id: UUID of the project
            include_photos: Whether to include photo URLs
            format: Output format (json or pdf)

        Returns:
            Report dictionary
        """
        # Get project information
        project = self.db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get all damage detections for the project
        damage_detections = (
            self.db.query(Detection, Photo)
            .join(Photo, Detection.photo_id == Photo.id)
            .filter(Photo.project_id == project_id)
            .filter(Detection.detection_type == "damage")
            .filter(Detection.results["has_damage"].astext.cast(bool) == True)
            .order_by(Detection.created_at)
            .all()
        )

        # Generate report sections
        report = {
            "report_type": "insurance_claim",
            "generated_at": datetime.utcnow().isoformat(),
            "project": self._format_project_info(project),
            "summary": self._generate_summary(damage_detections),
            "damage_items": self._format_damage_items(damage_detections, include_photos),
            "recommendations": self._generate_recommendations(damage_detections),
        }

        return report

    def generate_batch_report(
        self,
        project_ids: List[UUID],
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Generate batch insurance claim report for multiple projects.

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
            "report_type": "insurance_claim_batch",
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
        self, damage_detections: List[tuple[Detection, Photo]]
    ) -> Dict[str, Any]:
        """Generate summary statistics for the report"""
        if not damage_detections:
            return {
                "total_photos_with_damage": 0,
                "total_damage_items": 0,
                "severity_breakdown": {},
                "damage_types": [],
            }

        severity_counts = {}
        damage_types = set()

        for detection, photo in damage_detections:
            results = detection.results

            # Count severity levels
            severity = results.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Collect damage types
            for damage_type in results.get("damage_types", []):
                damage_types.add(damage_type)

        return {
            "total_photos_with_damage": len(damage_detections),
            "total_damage_items": len(damage_detections),
            "severity_breakdown": severity_counts,
            "damage_types": list(damage_types),
        }

    def _format_damage_items(
        self,
        damage_detections: List[tuple[Detection, Photo]],
        include_photos: bool,
    ) -> List[Dict[str, Any]]:
        """Format individual damage items for report"""
        items = []

        for detection, photo in damage_detections:
            results = detection.results

            item = {
                "detection_id": str(detection.id),
                "photo_id": str(photo.id),
                "detected_at": detection.created_at.isoformat(),
                "severity": results.get("severity", "unknown"),
                "confidence": detection.confidence,
                "damage_types": results.get("damage_types", []),
                "affected_area": results.get("affected_area", {}),
                "bounding_boxes": results.get("bounding_boxes", []),
                "user_confirmed": detection.user_confirmed,
            }

            if include_photos:
                item["photo_url"] = photo.s3_url

            # Add estimated cost if available
            if "estimated_cost" in results:
                item["estimated_cost"] = results["estimated_cost"]

            items.append(item)

        return items

    def _generate_recommendations(
        self, damage_detections: List[tuple[Detection, Photo]]
    ) -> List[str]:
        """Generate recommendations based on damage detections"""
        recommendations = []

        if not damage_detections:
            return ["No damage detected. No immediate action required."]

        # Count severity levels
        severe_count = 0
        critical_count = 0

        for detection, photo in damage_detections:
            severity = detection.results.get("severity", "unknown")
            if severity == "severe":
                severe_count += 1
            elif severity == "critical":
                critical_count += 1

        # Generate recommendations based on severity
        if critical_count > 0:
            recommendations.append(
                f"URGENT: {critical_count} critical damage item(s) detected. "
                "Immediate professional inspection and emergency repairs recommended."
            )

        if severe_count > 0:
            recommendations.append(
                f"{severe_count} severe damage item(s) detected. "
                "Professional assessment and repair scheduling recommended within 48 hours."
            )

        # Check for roof damage
        has_roof_damage = False
        for detection, photo in damage_detections:
            damage_types = detection.results.get("damage_types", [])
            if any("roof" in str(dt).lower() for dt in damage_types):
                has_roof_damage = True
                break

        if has_roof_damage:
            recommendations.append(
                "Roof damage detected. Consider temporary weatherproofing "
                "to prevent further water damage."
            )

        # General recommendation
        recommendations.append(
            "Document all damage with photos and descriptions. "
            "Contact insurance adjuster with this report."
        )

        return recommendations
