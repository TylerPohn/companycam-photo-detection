"""Tags service for automatic tag generation and management"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from src.models.tag import Tag


class TagsService:
    """
    Service for generating and managing tags from detection results.
    Implements automatic tag generation and user tag management.
    """

    def __init__(self, db: Session):
        """Initialize with database session"""
        self.db = db

    def generate_tags_from_detections(
        self,
        photo_id: UUID,
        damage_result: Optional[Dict[str, Any]] = None,
        material_result: Optional[Dict[str, Any]] = None,
        volume_result: Optional[Dict[str, Any]] = None,
    ) -> List[Tag]:
        """
        Generate and store tags based on detection results.

        Args:
            photo_id: UUID of the photo
            damage_result: Damage detection results
            material_result: Material detection results
            volume_result: Volume estimation results

        Returns:
            List of created Tag objects
        """
        tags_to_create = []

        # Generate damage tags
        if damage_result:
            tags_to_create.extend(
                self._generate_damage_tags(damage_result)
            )

        # Generate material tags
        if material_result:
            tags_to_create.extend(
                self._generate_material_tags(material_result)
            )

        # Generate volume tags
        if volume_result:
            tags_to_create.extend(
                self._generate_volume_tags(volume_result)
            )

        # Generate cross-detection tags
        tags_to_create.extend(
            self._generate_cross_detection_tags(
                damage_result, material_result, volume_result
            )
        )

        # Create tag objects and store in database
        return self._store_tags(photo_id, tags_to_create)

    def add_user_tag(
        self,
        photo_id: UUID,
        tag: str,
        user_id: Optional[UUID] = None,
    ) -> Tag:
        """
        Add a user-generated tag to a photo.

        Args:
            photo_id: UUID of the photo
            tag: Tag text
            user_id: Optional user ID who created the tag

        Returns:
            Created Tag object
        """
        tag_obj = Tag(
            photo_id=photo_id,
            tag=tag,
            source="user",
            confidence=None,  # User tags don't have confidence
        )

        self.db.add(tag_obj)
        self.db.commit()
        self.db.refresh(tag_obj)

        return tag_obj

    def remove_tag(self, tag_id: UUID) -> bool:
        """
        Remove a tag by ID.

        Args:
            tag_id: UUID of the tag

        Returns:
            True if removed, False if not found
        """
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()

        if tag:
            self.db.delete(tag)
            self.db.commit()
            return True

        return False

    def get_tags_by_photo(self, photo_id: UUID) -> List[Tag]:
        """
        Get all tags for a photo.

        Args:
            photo_id: UUID of the photo

        Returns:
            List of Tag objects
        """
        return (
            self.db.query(Tag)
            .filter(Tag.photo_id == photo_id)
            .all()
        )

    def search_photos_by_tags(
        self,
        tags: List[str],
        match_all: bool = False,
    ) -> List[UUID]:
        """
        Search for photos by tags.

        Args:
            tags: List of tag texts to search for
            match_all: If True, match all tags; if False, match any tag

        Returns:
            List of photo IDs
        """
        query = self.db.query(Tag.photo_id).filter(Tag.tag.in_(tags))

        if match_all:
            # Group by photo_id and count distinct tags
            # Only return photos that have all tags
            query = (
                query.group_by(Tag.photo_id)
                .having(self.db.func.count(Tag.tag.distinct()) == len(tags))
            )

        results = query.distinct().all()
        return [result[0] for result in results]

    def _generate_damage_tags(
        self, damage_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate tags from damage detection results"""
        tags = []
        results = damage_result.get("results", {})
        confidence = damage_result.get("confidence", 0.0)

        if not results.get("has_damage"):
            return tags

        # Severity tag
        severity = results.get("severity", "unknown")
        tags.append({
            "tag": f"damage_{severity}",
            "source": "ai",
            "confidence": confidence,
        })

        # Specific damage type tags
        damage_types = results.get("damage_types", [])
        for damage_type in damage_types:
            tags.append({
                "tag": damage_type,
                "source": "ai",
                "confidence": confidence,
            })

        # Insurance claim tag for severe damage
        if severity in ["severe", "critical"]:
            tags.append({
                "tag": "insurance_claim",
                "source": "ai",
                "confidence": confidence,
            })

        # Specific damage indicators
        if "roof" in str(damage_types).lower():
            tags.append({
                "tag": "roof_damage",
                "source": "ai",
                "confidence": confidence,
            })

        if "hail" in str(damage_types).lower():
            tags.append({
                "tag": "hail_impact",
                "source": "ai",
                "confidence": confidence,
            })

        if "wind" in str(damage_types).lower():
            tags.append({
                "tag": "wind_damage",
                "source": "ai",
                "confidence": confidence,
            })

        if "missing" in str(damage_types).lower() or "shingle" in str(damage_types).lower():
            tags.append({
                "tag": "missing_shingles",
                "source": "ai",
                "confidence": confidence,
            })

        return tags

    def _generate_material_tags(
        self, material_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate tags from material detection results"""
        tags = []
        results = material_result.get("results", {})
        confidence = material_result.get("confidence", 0.0)

        materials = results.get("materials", [])
        if not materials:
            return tags

        # Delivery confirmation tag
        tags.append({
            "tag": "delivery_confirmation",
            "source": "ai",
            "confidence": confidence,
        })

        # Material type tags
        for material in materials:
            material_type = material.get("material_type", "unknown")
            tags.append({
                "tag": f"material_{material_type}",
                "source": "ai",
                "confidence": material.get("confidence", confidence),
            })

            # Brand tags
            brand = material.get("brand")
            if brand:
                tags.append({
                    "tag": f"brand_{brand}",
                    "source": "ai",
                    "confidence": material.get("confidence", confidence),
                })

        # Quantity variance alert
        if results.get("has_variance"):
            tags.append({
                "tag": "quantity_alert",
                "source": "ai",
                "confidence": confidence,
            })

        return tags

    def _generate_volume_tags(
        self, volume_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate tags from volume estimation results"""
        tags = []
        results = volume_result.get("results", {})
        confidence = volume_result.get("confidence", 0.0)

        if not results.get("volume_cubic_feet"):
            return tags

        # Volume estimated tag
        tags.append({
            "tag": "volume_estimated",
            "source": "ai",
            "confidence": confidence,
        })

        # Material type tag
        material_type = results.get("material_type")
        if material_type:
            tags.append({
                "tag": f"volume_{material_type}",
                "source": "ai",
                "confidence": confidence,
            })

        # Low confidence warning
        if confidence < 0.7:
            tags.append({
                "tag": "requires_confirmation",
                "source": "ai",
                "confidence": confidence,
            })

        return tags

    def _generate_cross_detection_tags(
        self,
        damage_result: Optional[Dict[str, Any]],
        material_result: Optional[Dict[str, Any]],
        volume_result: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate tags based on combinations of detection results"""
        tags = []

        # Count how many detection types have results
        detection_count = sum([
            1 for r in [damage_result, material_result, volume_result]
            if r is not None
        ])

        # Multi-detection tag
        if detection_count > 1:
            tags.append({
                "tag": "multi_detection",
                "source": "ai",
                "confidence": 1.0,
            })

        # High confidence tag if all detections are high confidence
        all_high_confidence = True
        for result in [damage_result, material_result, volume_result]:
            if result and result.get("confidence", 0.0) < 0.85:
                all_high_confidence = False
                break

        if all_high_confidence and detection_count > 0:
            tags.append({
                "tag": "high_confidence",
                "source": "ai",
                "confidence": 1.0,
            })

        # Potential claim tag if damage and material both detected
        if damage_result and material_result:
            damage_has_damage = damage_result.get("results", {}).get("has_damage", False)
            if damage_has_damage:
                tags.append({
                    "tag": "potential_claim",
                    "source": "ai",
                    "confidence": 0.9,
                })

        return tags

    def _store_tags(
        self, photo_id: UUID, tags_data: List[Dict[str, Any]]
    ) -> List[Tag]:
        """Store tags in database"""
        try:
            tag_objects = []

            for tag_data in tags_data:
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
