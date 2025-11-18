"""Material detection AI models module"""

from .pipeline import MaterialDetectionPipeline
from .detector import MaterialDetector
from .counter import MaterialCounter
from .brand_detector import BrandDetector
from .material_validator import MaterialValidator
from .material_database import MaterialDatabase, get_material_database
from .config import (
    MaterialDetectionConfig,
    DetectorConfig,
    CounterConfig,
    BrandDetectorConfig,
    ValidatorConfig,
)

__all__ = [
    "MaterialDetectionPipeline",
    "MaterialDetector",
    "MaterialCounter",
    "BrandDetector",
    "MaterialValidator",
    "MaterialDatabase",
    "get_material_database",
    "MaterialDetectionConfig",
    "DetectorConfig",
    "CounterConfig",
    "BrandDetectorConfig",
    "ValidatorConfig",
]
