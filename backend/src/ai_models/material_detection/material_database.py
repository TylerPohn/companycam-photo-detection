"""Material and brand database loader and query interface"""

import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

from src.schemas.material_detection import MaterialType, MaterialUnit

logger = logging.getLogger(__name__)


class MaterialInfo:
    """Information about a material type"""

    def __init__(self, data: dict):
        self.type = data["type"]
        self.unit = data["unit"]
        self.description = data["description"]
        self.detection_class = data["detection_class"]
        self.typical_brands = data.get("typical_brands", [])
        self.weight_per_unit_lbs = data.get("weight_per_unit_lbs", 0)


class BrandInfo:
    """Information about a material brand"""

    def __init__(self, data: dict):
        self.name = data["name"]
        self.aliases = data.get("aliases", [])
        self.logo_keywords = data.get("logo_keywords", [])


class MaterialDatabase:
    """
    Material and brand reference database.

    Provides query interface for material types and brands.
    """

    def __init__(
        self,
        materials_db_path: str = "backend/data/materials.json",
        brands_db_path: str = "backend/data/brands.json",
    ):
        self.materials_db_path = materials_db_path
        self.brands_db_path = brands_db_path
        self.materials: Dict[str, MaterialInfo] = {}
        self.brands: Dict[str, List[BrandInfo]] = {}
        self._loaded = False

    def load(self):
        """Load materials and brands databases from JSON files"""
        try:
            # Load materials database
            materials_path = Path(self.materials_db_path)
            if materials_path.exists():
                with open(materials_path, "r") as f:
                    materials_data = json.load(f)
                    for material in materials_data.get("materials", []):
                        material_info = MaterialInfo(material)
                        self.materials[material_info.type] = material_info
                logger.info(f"Loaded {len(self.materials)} material types from {self.materials_db_path}")
            else:
                logger.warning(f"Materials database not found at {self.materials_db_path}")

            # Load brands database
            brands_path = Path(self.brands_db_path)
            if brands_path.exists():
                with open(brands_path, "r") as f:
                    brands_data = json.load(f)
                    for material_type, brands_list in brands_data.get("brands", {}).items():
                        self.brands[material_type] = [
                            BrandInfo(brand) for brand in brands_list
                        ]
                brand_count = sum(len(brands) for brands in self.brands.values())
                logger.info(f"Loaded {brand_count} brands from {self.brands_db_path}")
            else:
                logger.warning(f"Brands database not found at {self.brands_db_path}")

            self._loaded = True

        except Exception as e:
            logger.error(f"Failed to load material/brand databases: {e}")
            raise

    def get_material_info(self, material_type: str) -> Optional[MaterialInfo]:
        """
        Get information for a material type.

        Args:
            material_type: Material type (e.g., 'shingles', 'plywood')

        Returns:
            MaterialInfo or None if not found
        """
        if not self._loaded:
            self.load()
        return self.materials.get(material_type)

    def get_material_unit(self, material_type: str) -> MaterialUnit:
        """
        Get the unit for a material type.

        Args:
            material_type: Material type

        Returns:
            MaterialUnit enum value
        """
        material_info = self.get_material_info(material_type)
        if material_info:
            try:
                return MaterialUnit(material_info.unit)
            except ValueError:
                pass
        return MaterialUnit.UNITS

    def get_brands_for_material(self, material_type: str) -> List[BrandInfo]:
        """
        Get all known brands for a material type.

        Args:
            material_type: Material type

        Returns:
            List of BrandInfo objects
        """
        if not self._loaded:
            self.load()
        return self.brands.get(material_type, [])

    def find_brand_by_name(
        self, material_type: str, brand_name: str
    ) -> Optional[BrandInfo]:
        """
        Find a brand by exact name match.

        Args:
            material_type: Material type
            brand_name: Brand name to search for

        Returns:
            BrandInfo or None if not found
        """
        brands = self.get_brands_for_material(material_type)
        for brand in brands:
            if brand.name.lower() == brand_name.lower():
                return brand
            # Check aliases
            for alias in brand.aliases:
                if alias.lower() == brand_name.lower():
                    return brand
        return None

    def search_brands(
        self, material_type: str, text: str, threshold: int = 80
    ) -> List[tuple[BrandInfo, int]]:
        """
        Search for brands using fuzzy matching.

        Args:
            material_type: Material type
            text: Text to search for brand matches
            threshold: Fuzzy match threshold (0-100)

        Returns:
            List of (BrandInfo, score) tuples sorted by score
        """
        if not self._loaded:
            self.load()

        brands = self.get_brands_for_material(material_type)
        matches = []

        # Simple fuzzy matching (in production, use fuzzywuzzy library)
        text_lower = text.lower()

        for brand in brands:
            # Check exact matches first
            if brand.name.lower() in text_lower:
                matches.append((brand, 100))
                continue

            # Check aliases
            for alias in brand.aliases:
                if alias.lower() in text_lower:
                    matches.append((brand, 95))
                    break

            # Check logo keywords
            for keyword in brand.logo_keywords:
                if keyword.lower() in text_lower:
                    matches.append((brand, 85))
                    break

        # Filter by threshold and sort by score
        matches = [(brand, score) for brand, score in matches if score >= threshold]
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    def get_all_material_types(self) -> List[str]:
        """Get list of all supported material types"""
        if not self._loaded:
            self.load()
        return list(self.materials.keys())

    def get_stats(self) -> dict:
        """Get database statistics"""
        if not self._loaded:
            self.load()

        brand_count = sum(len(brands) for brands in self.brands.values())

        return {
            "loaded": self._loaded,
            "material_types": len(self.materials),
            "total_brands": brand_count,
            "materials": list(self.materials.keys()),
        }


# Singleton instance
_material_db_instance: Optional[MaterialDatabase] = None


def get_material_database(
    materials_db_path: str = "backend/data/materials.json",
    brands_db_path: str = "backend/data/brands.json",
) -> MaterialDatabase:
    """
    Get singleton MaterialDatabase instance.

    Args:
        materials_db_path: Path to materials JSON file
        brands_db_path: Path to brands JSON file

    Returns:
        MaterialDatabase instance
    """
    global _material_db_instance
    if _material_db_instance is None:
        _material_db_instance = MaterialDatabase(materials_db_path, brands_db_path)
        _material_db_instance.load()
    return _material_db_instance
