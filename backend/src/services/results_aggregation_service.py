"""Results aggregation service for combining detection results from multiple AI engines"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from src.schemas.detection_result_schema import (
    AggregatedDetectionResultSchema,
    TagSchema,
    UserConfirmationSchema,
    DetectionSummarySchema,
    DetectionMetadataSchema,
)


class ResultsAggregationService:
    """
    Service for aggregating detection results from multiple AI engines
    (damage, material, volume) into a unified response format.
    """

    @staticmethod
    def aggregate_results(
        photo_id: UUID,
        detection_id: UUID,
        damage_result: Optional[Dict[str, Any]] = None,
        material_result: Optional[Dict[str, Any]] = None,
        volume_result: Optional[Dict[str, Any]] = None,
        user_id: UUID = None,
        project_id: UUID = None,
        processing_region: str = "us-east-1",
    ) -> AggregatedDetectionResultSchema:
        """
        Aggregate detection results from multiple engines into unified format.

        Args:
            photo_id: UUID of the photo
            detection_id: UUID of the detection
            damage_result: Damage detection results
            material_result: Material detection results
            volume_result: Volume estimation results
            user_id: User ID who uploaded the photo
            project_id: Project ID
            processing_region: AWS region where processing occurred

        Returns:
            AggregatedDetectionResultSchema with unified detection results
        """
        # Calculate total processing time
        processing_time_ms = 0
        if damage_result:
            processing_time_ms += damage_result.get("processing_time_ms", 0)
        if material_result:
            processing_time_ms += material_result.get("processing_time_ms", 0)
        if volume_result:
            processing_time_ms += volume_result.get("processing_time_ms", 0)

        # Extract model versions
        model_versions = {}
        if damage_result:
            model_versions["damage"] = damage_result.get("model_version", "unknown")
        if material_result:
            model_versions["material"] = material_result.get("model_version", "unknown")
        if volume_result:
            model_versions["volume"] = volume_result.get("model_version", "unknown")

        # Combine detection results
        detections = {}
        if damage_result:
            detections["damage"] = damage_result.get("results", {})
        if material_result:
            detections["material"] = material_result.get("results", {})
        if volume_result:
            detections["volume"] = volume_result.get("results", {})

        # Generate aggregate tags from all engines
        aggregate_tags = ResultsAggregationService._generate_aggregate_tags(
            damage_result, material_result, volume_result
        )

        # Create summary
        summary = ResultsAggregationService._create_summary(
            damage_result, material_result, volume_result
        )

        # Create user confirmation (default to pending)
        user_confirmation = UserConfirmationSchema(
            status="pending",
            confirmed_by=None,
            confirmed_at=None,
            corrections=None,
        )

        # Create metadata
        metadata = DetectionMetadataSchema(
            project_id=project_id,
            user_id=user_id,
            processing_region=processing_region,
            api_version="v1",
        )

        # Build aggregated result
        return AggregatedDetectionResultSchema(
            photo_id=photo_id,
            detection_id=detection_id,
            detected_at=datetime.utcnow(),
            processing_time_ms=processing_time_ms,
            model_versions=model_versions,
            detections=detections,
            aggregate_tags=aggregate_tags,
            summary=summary,
            user_confirmation=user_confirmation,
            metadata=metadata,
        )

    @staticmethod
    def _generate_aggregate_tags(
        damage_result: Optional[Dict[str, Any]],
        material_result: Optional[Dict[str, Any]],
        volume_result: Optional[Dict[str, Any]],
    ) -> List[TagSchema]:
        """
        Generate aggregate tags from all detection engines.

        Args:
            damage_result: Damage detection results
            material_result: Material detection results
            volume_result: Volume estimation results

        Returns:
            List of TagSchema objects with aggregated tags
        """
        tags = []

        # Process damage detection tags
        if damage_result and damage_result.get("results"):
            results = damage_result["results"]
            confidence = damage_result.get("confidence", 0.0)

            # Add damage-specific tags
            if results.get("has_damage"):
                severity = results.get("severity", "unknown")
                tags.append(
                    TagSchema(
                        tag=f"damage_{severity}",
                        source="ai",
                        confidence=confidence,
                        engines=["damage"],
                    )
                )

                # Add specific damage type tags
                damage_types = results.get("damage_types", [])
                for damage_type in damage_types:
                    tags.append(
                        TagSchema(
                            tag=damage_type,
                            source="ai",
                            confidence=confidence,
                            engines=["damage"],
                        )
                    )

                # Add insurance claim tag if severe
                if severity in ["severe", "critical"]:
                    tags.append(
                        TagSchema(
                            tag="insurance_claim",
                            source="ai",
                            confidence=confidence,
                            engines=["damage"],
                        )
                    )

        # Process material detection tags
        if material_result and material_result.get("results"):
            results = material_result["results"]
            confidence = material_result.get("confidence", 0.0)

            materials = results.get("materials", [])
            if materials:
                tags.append(
                    TagSchema(
                        tag="delivery_confirmation",
                        source="ai",
                        confidence=confidence,
                        engines=["material"],
                    )
                )

                # Add material type tags
                for material in materials:
                    material_type = material.get("material_type", "unknown")
                    tags.append(
                        TagSchema(
                            tag=f"material_{material_type}",
                            source="ai",
                            confidence=material.get("confidence", confidence),
                            engines=["material"],
                        )
                    )

                    # Add brand tags if available
                    brand = material.get("brand")
                    if brand:
                        tags.append(
                            TagSchema(
                                tag=f"brand_{brand}",
                                source="ai",
                                confidence=material.get("confidence", confidence),
                                engines=["material"],
                            )
                        )

            # Add quantity alert if variance detected
            if results.get("has_variance"):
                tags.append(
                    TagSchema(
                        tag="quantity_alert",
                        source="ai",
                        confidence=confidence,
                        engines=["material"],
                    )
                )

        # Process volume estimation tags
        if volume_result and volume_result.get("results"):
            results = volume_result["results"]
            confidence = volume_result.get("confidence", 0.0)

            if results.get("volume_cubic_feet"):
                tags.append(
                    TagSchema(
                        tag="volume_estimated",
                        source="ai",
                        confidence=confidence,
                        engines=["volume"],
                    )
                )

                # Add material type tag if available
                material_type = results.get("material_type")
                if material_type:
                    tags.append(
                        TagSchema(
                            tag=f"volume_{material_type}",
                            source="ai",
                            confidence=confidence,
                            engines=["volume"],
                        )
                    )

                # Add low confidence tag if needed
                if confidence < 0.7:
                    tags.append(
                        TagSchema(
                            tag="requires_confirmation",
                            source="ai",
                            confidence=confidence,
                            engines=["volume"],
                        )
                    )

        # Add cross-detection tags
        if len([r for r in [damage_result, material_result, volume_result] if r]) > 1:
            tags.append(
                TagSchema(
                    tag="multi_detection",
                    source="ai",
                    confidence=1.0,
                    engines=["aggregation"],
                )
            )

        # Add high confidence tag if all detections are high confidence
        all_high_confidence = True
        for result in [damage_result, material_result, volume_result]:
            if result and result.get("confidence", 0.0) < 0.85:
                all_high_confidence = False
                break

        if all_high_confidence and tags:
            tags.append(
                TagSchema(
                    tag="high_confidence",
                    source="ai",
                    confidence=1.0,
                    engines=["aggregation"],
                )
            )

        return tags

    @staticmethod
    def _create_summary(
        damage_result: Optional[Dict[str, Any]],
        material_result: Optional[Dict[str, Any]],
        volume_result: Optional[Dict[str, Any]],
    ) -> DetectionSummarySchema:
        """
        Create high-level summary of all detections.

        Args:
            damage_result: Damage detection results
            material_result: Material detection results
            volume_result: Volume estimation results

        Returns:
            DetectionSummarySchema with summary information
        """
        has_damage = False
        damage_severity = None

        if damage_result and damage_result.get("results"):
            results = damage_result["results"]
            has_damage = results.get("has_damage", False)
            damage_severity = results.get("severity") if has_damage else None

        materials_detected = 0
        if material_result and material_result.get("results"):
            materials = material_result["results"].get("materials", [])
            materials_detected = len(materials)

        volume_estimated = False
        if volume_result and volume_result.get("results"):
            volume_estimated = volume_result["results"].get("volume_cubic_feet") is not None

        return DetectionSummarySchema(
            has_damage=has_damage,
            damage_severity=damage_severity,
            materials_detected=materials_detected,
            volume_estimated=volume_estimated,
        )

    @staticmethod
    def validate_detection_result(
        detection_type: str, result: Dict[str, Any]
    ) -> bool:
        """
        Validate a detection result against its expected schema.

        Args:
            detection_type: Type of detection (damage, material, volume)
            result: Detection result to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["results", "confidence"]

        # Check required fields
        for field in required_fields:
            if field not in result:
                return False

        # Validate confidence range
        confidence = result.get("confidence")
        if confidence is not None and (confidence < 0.0 or confidence > 1.0):
            return False

        # Type-specific validation
        if detection_type == "damage":
            return "has_damage" in result.get("results", {})
        elif detection_type == "material":
            return "materials" in result.get("results", {})
        elif detection_type == "volume":
            return "volume_cubic_feet" in result.get("results", {})

        return True
