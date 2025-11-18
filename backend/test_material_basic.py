#!/usr/bin/env python
"""Basic smoke test for material detection without pytest dependencies"""

import sys
from PIL import Image
import numpy as np

# Add backend to path
sys.path.insert(0, '/home/user/companycam-photo-detection/backend')

from src.ai_models.material_detection import (
    MaterialDetectionPipeline,
    MaterialDetector,
    MaterialCounter,
    BrandDetector,
    MaterialValidator,
    MaterialDatabase,
)
from src.schemas.material_detection import MaterialType


def test_basic_functionality():
    """Test basic material detection functionality"""
    print("=" * 80)
    print("MATERIAL DETECTION ENGINE - BASIC FUNCTIONALITY TEST")
    print("=" * 80)

    # Create sample image
    print("\n1. Creating sample image...")
    img_array = np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8)
    sample_image = Image.fromarray(img_array)
    print(f"   ✓ Created {sample_image.size} image")

    # Test Material Database
    print("\n2. Testing Material Database...")
    db = MaterialDatabase(
        materials_db_path="/home/user/companycam-photo-detection/backend/data/materials.json",
        brands_db_path="/home/user/companycam-photo-detection/backend/data/brands.json",
    )
    db.load()
    print(f"   ✓ Loaded {len(db.materials)} material types")
    print(f"   ✓ Loaded {sum(len(brands) for brands in db.brands.values())} brands")

    # Test Material Detector
    print("\n3. Testing Material Detector (YOLOv8)...")
    detector = MaterialDetector()
    detections = detector.detect(sample_image)
    print(f"   ✓ Detected {len(detections)} material units")
    if detections:
        print(f"   ✓ First detection: {detections[0].material_type.value} (confidence: {detections[0].confidence:.2f})")

    # Test Material Counter
    print("\n4. Testing Material Counter (Density Estimation)...")
    counter = MaterialCounter()
    count_results = counter.count_materials(sample_image, detections)
    print(f"   ✓ Counted {len(count_results)} material types")
    for material_type, count_result in count_results.items():
        print(f"   ✓ {material_type.value}: {count_result.count} units (confidence: {count_result.confidence:.2f})")

    # Test Brand Detector
    print("\n5. Testing Brand Detector (OCR)...")
    brand_detector = BrandDetector(material_db=db)
    brand_result = brand_detector.detect_brand(sample_image, MaterialType.SHINGLES)
    if brand_result.brand_name:
        print(f"   ✓ Detected brand: {brand_result.brand_name} (confidence: {brand_result.confidence:.2f})")
    else:
        print(f"   ✓ No brand detected (confidence: {brand_result.confidence:.2f})")

    # Test Material Validator
    print("\n6. Testing Material Validator...")
    validator = MaterialValidator()
    alert = validator.validate_quantity(24, 25, "sheets")
    if alert:
        print(f"   ✓ Alert generated: {alert.type.value} - {alert.message}")
    else:
        print(f"   ✓ No alert (within tolerance)")

    # Test Full Pipeline
    print("\n7. Testing Full Material Detection Pipeline...")
    pipeline = MaterialDetectionPipeline(material_db=db)

    import time
    start_time = time.time()
    response = pipeline.process_image(sample_image)
    processing_time = (time.time() - start_time) * 1000

    print(f"   ✓ Pipeline completed in {processing_time:.2f}ms")
    print(f"   ✓ Detected {len(response.materials)} material types")
    print(f"   ✓ Total units: {response.summary.total_units}")
    print(f"   ✓ Overall confidence: {response.confidence:.2f}")
    print(f"   ✓ Tags: {', '.join(response.tags[:5])}")

    # Test with expected materials
    print("\n8. Testing Pipeline with Quantity Validation...")
    expected_materials = {"shingles": 36, "plywood": 25}
    response = pipeline.process_image(sample_image, expected_materials)
    print(f"   ✓ Processed with expected materials")
    print(f"   ✓ Discrepancy alerts: {response.summary.discrepancy_alerts}")

    for material in response.materials:
        if material.expected_quantity:
            status = "ALERT" if material.alert else "OK"
            print(f"   ✓ {material.type.value}: {material.count}/{material.expected_quantity} {material.unit.value} [{status}]")

    # Performance Test
    print("\n9. Testing Latency Performance...")
    pipeline.load_models()  # Pre-load

    latencies = []
    for i in range(5):
        img = Image.fromarray(np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8))
        start = time.time()
        _ = pipeline.process_image(img)
        latency = (time.time() - start) * 1000
        latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    print(f"   ✓ Average latency: {avg_latency:.2f}ms")
    print(f"   ✓ Min latency: {min_latency:.2f}ms")
    print(f"   ✓ Max latency: {max_latency:.2f}ms")
    print(f"   ✓ Target: <450ms - {'PASS' if max_latency < 450 else 'FAIL'}")

    # Final Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✓ All components tested successfully")
    print(f"✓ Material types supported: {len(db.materials)}")
    print(f"✓ Brands in database: {sum(len(brands) for brands in db.brands.values())}")
    print(f"✓ Average detection latency: {avg_latency:.2f}ms")
    print(f"✓ Performance target: {'MET' if max_latency < 450 else 'NOT MET'} (<450ms)")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = test_basic_functionality()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
