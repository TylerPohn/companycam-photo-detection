"""Tests for material database"""

import pytest

from src.ai_models.material_detection import MaterialDatabase, get_material_database
from src.schemas.material_detection import MaterialUnit


@pytest.fixture
def material_db():
    """Create material database instance"""
    db = MaterialDatabase(
        materials_db_path="/home/user/companycam-photo-detection/backend/data/materials.json",
        brands_db_path="/home/user/companycam-photo-detection/backend/data/brands.json",
    )
    return db


def test_database_initialization(material_db):
    """Test database initializes correctly"""
    assert not material_db._loaded
    assert material_db.materials == {}
    assert material_db.brands == {}


def test_database_load(material_db):
    """Test loading database files"""
    material_db.load()

    assert material_db._loaded
    assert len(material_db.materials) > 0
    assert len(material_db.brands) > 0


def test_database_get_material_info(material_db):
    """Test getting material information"""
    material_db.load()

    # Get shingles info
    shingles_info = material_db.get_material_info("shingles")

    assert shingles_info is not None
    assert shingles_info.type == "shingles"
    assert shingles_info.unit == "bundles"
    assert shingles_info.detection_class == "shingles"
    assert len(shingles_info.typical_brands) > 0


def test_database_get_material_unit(material_db):
    """Test getting material unit"""
    material_db.load()

    # Shingles should be bundles
    unit = material_db.get_material_unit("shingles")
    assert unit == MaterialUnit.BUNDLES

    # Plywood should be sheets
    unit = material_db.get_material_unit("plywood")
    assert unit == MaterialUnit.SHEETS


def test_database_get_brands_for_material(material_db):
    """Test getting brands for material type"""
    material_db.load()

    # Get shingle brands
    brands = material_db.get_brands_for_material("shingles")

    assert len(brands) > 0

    # Check brand info structure
    for brand in brands:
        assert brand.name is not None
        assert isinstance(brand.aliases, list)
        assert isinstance(brand.logo_keywords, list)


def test_database_find_brand_by_name(material_db):
    """Test finding brand by exact name"""
    material_db.load()

    # Find CertainTeed
    brand = material_db.find_brand_by_name("shingles", "CertainTeed")

    assert brand is not None
    assert brand.name == "CertainTeed"


def test_database_find_brand_by_alias(material_db):
    """Test finding brand by alias"""
    material_db.load()

    # Find Owens Corning by alias "OC"
    brand = material_db.find_brand_by_name("shingles", "OC")

    assert brand is not None
    assert brand.name == "Owens Corning"


def test_database_find_brand_not_found(material_db):
    """Test finding non-existent brand"""
    material_db.load()

    brand = material_db.find_brand_by_name("shingles", "NonExistentBrand")

    assert brand is None


def test_database_search_brands(material_db):
    """Test fuzzy brand search"""
    material_db.load()

    # Search for "CertainTeed" in text
    matches = material_db.search_brands("shingles", "CertainTeed Roofing Products")

    # Should find CertainTeed
    assert len(matches) > 0

    # Best match should be CertainTeed
    best_brand, score = matches[0]
    assert best_brand.name == "CertainTeed"
    assert score >= 80  # Good match


def test_database_search_brands_threshold(material_db):
    """Test search with threshold"""
    material_db.load()

    # Search with high threshold
    matches = material_db.search_brands("shingles", "some random text", threshold=95)

    # May not find any matches
    # All matches should have score >= 95
    for brand, score in matches:
        assert score >= 95


def test_database_get_all_material_types(material_db):
    """Test getting all material types"""
    material_db.load()

    material_types = material_db.get_all_material_types()

    # Should have multiple material types
    assert len(material_types) >= 4

    # Should include key material types
    assert "shingles" in material_types
    assert "plywood" in material_types
    assert "drywall" in material_types
    assert "insulation" in material_types


def test_database_stats(material_db):
    """Test getting database statistics"""
    material_db.load()

    stats = material_db.get_stats()

    assert stats["loaded"]
    assert stats["material_types"] > 0
    assert stats["total_brands"] > 0
    assert "materials" in stats
    assert isinstance(stats["materials"], list)


def test_database_singleton():
    """Test that get_material_database returns singleton"""
    db1 = get_material_database()
    db2 = get_material_database()

    # Should be same instance
    assert db1 is db2


def test_database_multiple_material_types(material_db):
    """Test database has various material types"""
    material_db.load()

    # Check shingles
    shingles = material_db.get_material_info("shingles")
    assert shingles.unit == "bundles"

    # Check plywood
    plywood = material_db.get_material_info("plywood")
    assert plywood.unit == "sheets"

    # Check drywall
    drywall = material_db.get_material_info("drywall")
    assert drywall.unit == "sheets"

    # Check insulation
    insulation = material_db.get_material_info("insulation")
    assert insulation.unit == "bags"


def test_database_brand_aliases(material_db):
    """Test that brands have aliases"""
    material_db.load()

    brands = material_db.get_brands_for_material("shingles")

    # Check that some brands have aliases
    brands_with_aliases = [b for b in brands if len(b.aliases) > 0]
    assert len(brands_with_aliases) > 0


def test_database_brand_keywords(material_db):
    """Test that brands have logo keywords"""
    material_db.load()

    brands = material_db.get_brands_for_material("shingles")

    # Check that brands have keywords
    for brand in brands:
        assert len(brand.logo_keywords) > 0


def test_database_case_insensitive_search(material_db):
    """Test case-insensitive brand search"""
    material_db.load()

    # Search with different cases
    matches1 = material_db.search_brands("shingles", "CERTAINTEED")
    matches2 = material_db.search_brands("shingles", "certainteed")
    matches3 = material_db.search_brands("shingles", "CertainTeed")

    # All should find CertainTeed
    assert len(matches1) > 0
    assert len(matches2) > 0
    assert len(matches3) > 0
