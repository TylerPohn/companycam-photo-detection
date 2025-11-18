"""Unit tests for EXIF service"""

import pytest
from PIL import Image
from io import BytesIO

from src.services.exif_service import ExifService


@pytest.fixture
def sample_jpeg_with_exif():
    """Create a sample JPEG image with EXIF data"""
    # Create a simple test image
    img = Image.new("RGB", (800, 600), color="red")

    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return img_bytes.getvalue()


@pytest.fixture
def sample_png_no_exif():
    """Create a sample PNG image without EXIF data"""
    img = Image.new("RGB", (1024, 768), color="blue")

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    return img_bytes.getvalue()


class TestExifExtraction:
    """Test EXIF data extraction"""

    def test_extract_exif_from_bytes_jpeg(self, sample_jpeg_with_exif):
        """Test EXIF extraction from JPEG bytes"""
        exif_data = ExifService.extract_exif_from_bytes(sample_jpeg_with_exif)

        # Should at least have dimensions
        assert "width" in exif_data
        assert "height" in exif_data
        assert exif_data["width"] == 800
        assert exif_data["height"] == 600

    def test_extract_exif_from_bytes_png(self, sample_png_no_exif):
        """Test EXIF extraction from PNG bytes"""
        exif_data = ExifService.extract_exif_from_bytes(sample_png_no_exif)

        # Should at least have dimensions
        assert "width" in exif_data
        assert "height" in exif_data
        assert exif_data["width"] == 1024
        assert exif_data["height"] == 768

    def test_extract_exif_from_invalid_bytes(self):
        """Test EXIF extraction from invalid image bytes"""
        invalid_bytes = b"not an image"

        exif_data = ExifService.extract_exif_from_bytes(invalid_bytes)

        # Should return empty dict without crashing
        assert isinstance(exif_data, dict)

    def test_extract_exif_from_empty_bytes(self):
        """Test EXIF extraction from empty bytes"""
        exif_data = ExifService.extract_exif_from_bytes(b"")

        # Should return empty dict without crashing
        assert isinstance(exif_data, dict)


class TestGPSConversion:
    """Test GPS coordinate conversion"""

    def test_convert_to_degrees_valid(self):
        """Test GPS coordinate conversion"""
        # Example: 40°26'46"N = 40.446111
        value = (40, 26, 46)
        degrees = ExifService._convert_to_degrees(value)

        assert degrees is not None
        assert abs(degrees - 40.446111) < 0.0001

    def test_convert_to_degrees_zero(self):
        """Test GPS coordinate conversion with zeros"""
        value = (0, 0, 0)
        degrees = ExifService._convert_to_degrees(value)

        assert degrees == 0.0

    def test_convert_to_degrees_invalid(self):
        """Test GPS coordinate conversion with invalid input"""
        # Invalid tuple length
        value = (40, 26)
        degrees = ExifService._convert_to_degrees(value)

        assert degrees is None

    def test_get_gps_coordinates_valid(self):
        """Test GPS coordinate extraction"""
        gps_info = {
            "GPSLatitude": (40, 26, 46),
            "GPSLatitudeRef": "N",
            "GPSLongitude": (79, 58, 56),
            "GPSLongitudeRef": "W",
        }

        coords = ExifService._get_gps_coordinates(gps_info)

        assert coords is not None
        assert "latitude" in coords
        assert "longitude" in coords
        assert coords["latitude"] > 0  # North
        assert coords["longitude"] < 0  # West

    def test_get_gps_coordinates_southern_hemisphere(self):
        """Test GPS coordinates in southern hemisphere"""
        gps_info = {
            "GPSLatitude": (33, 52, 0),
            "GPSLatitudeRef": "S",
            "GPSLongitude": (151, 12, 0),
            "GPSLongitudeRef": "E",
        }

        coords = ExifService._get_gps_coordinates(gps_info)

        assert coords is not None
        assert coords["latitude"] < 0  # South
        assert coords["longitude"] > 0  # East

    def test_get_gps_coordinates_incomplete(self):
        """Test GPS coordinate extraction with incomplete data"""
        gps_info = {
            "GPSLatitude": (40, 26, 46),
            "GPSLatitudeRef": "N",
            # Missing longitude
        }

        coords = ExifService._get_gps_coordinates(gps_info)

        assert coords is None


@pytest.mark.asyncio
class TestAsyncExifExtraction:
    """Test async EXIF extraction from URLs"""

    async def test_extract_exif_from_invalid_url(self):
        """Test EXIF extraction from invalid URL"""
        exif_data = await ExifService.extract_exif_from_url("http://invalid-url-12345.com/image.jpg", timeout=5)

        # Should return empty dict without crashing
        assert isinstance(exif_data, dict)
        assert len(exif_data) == 0
