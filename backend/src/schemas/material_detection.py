"""Pydantic schemas for material detection responses"""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class MaterialType(str, Enum):
    """Material types that can be detected"""
    SHINGLES = "shingles"
    PLYWOOD = "plywood"
    DRYWALL = "drywall"
    INSULATION = "insulation"
    OTHER = "other"


class MaterialUnit(str, Enum):
    """Units for material counting"""
    BUNDLES = "bundles"
    SHEETS = "sheets"
    BAGS = "bags"
    ROLLS = "rolls"
    UNITS = "units"


class AlertType(str, Enum):
    """Alert types for quantity discrepancies"""
    UNDERAGE = "underage"
    OVERAGE = "overage"
    QUANTITY_MISMATCH = "quantity_mismatch"


class BoundingBox(BaseModel):
    """Bounding box for detected material"""
    x: int = Field(..., description="X coordinate of top-left corner")
    y: int = Field(..., description="Y coordinate of top-left corner")
    width: int = Field(..., description="Width of bounding box")
    height: int = Field(..., description="Height of bounding box")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class QuantityAlert(BaseModel):
    """Alert for quantity discrepancies"""
    type: AlertType = Field(..., description="Type of alert")
    message: str = Field(..., description="Human-readable alert message")
    variance_percentage: float = Field(..., description="Percentage variance from expected quantity")


class MaterialDetection(BaseModel):
    """Single material detection result"""
    type: MaterialType = Field(..., description="Type of material detected")
    brand: Optional[str] = Field(None, description="Brand detected via OCR")
    count: int = Field(..., ge=0, description="Count of material units")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    unit: MaterialUnit = Field(..., description="Unit of measurement")
    expected_quantity: Optional[int] = Field(None, description="Expected quantity if provided")
    alert: Optional[QuantityAlert] = Field(None, description="Alert if quantity mismatch detected")
    bounding_boxes: List[BoundingBox] = Field(default_factory=list, description="Bounding boxes for detected units")


class MaterialSummary(BaseModel):
    """Summary statistics for material detection"""
    total_materials_detected: int = Field(..., ge=0, description="Total number of material types detected")
    total_units: int = Field(..., ge=0, description="Total count of all material units")
    discrepancy_alerts: int = Field(..., ge=0, description="Number of discrepancy alerts generated")


class MaterialDetectionResponse(BaseModel):
    """Complete material detection response"""
    materials: List[MaterialDetection] = Field(default_factory=list, description="List of detected materials")
    tags: List[str] = Field(default_factory=list, description="Descriptive tags for the detection")
    summary: MaterialSummary = Field(..., description="Summary statistics")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")
    model_version: str = Field(..., description="Version of the detection model")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
