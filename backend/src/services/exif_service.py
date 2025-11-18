"""EXIF data extraction service for photo metadata"""

import logging
from typing import Dict, Optional, Any
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from io import BytesIO
import httpx

logger = logging.getLogger(__name__)


class ExifService:
    """Service for extracting EXIF metadata from photos"""

    @staticmethod
    def _convert_to_degrees(value: tuple) -> Optional[float]:
        """
        Convert GPS coordinates to degrees.

        Args:
            value: Tuple of (degrees, minutes, seconds)

        Returns:
            Decimal degrees
        """
        try:
            d, m, s = value
            return float(d) + (float(m) / 60.0) + (float(s) / 3600.0)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def _get_gps_coordinates(gps_info: Dict) -> Optional[Dict[str, float]]:
        """
        Extract GPS coordinates from GPS info.

        Args:
            gps_info: GPS info dictionary

        Returns:
            Dictionary with latitude and longitude or None
        """
        try:
            gps_latitude = gps_info.get("GPSLatitude")
            gps_latitude_ref = gps_info.get("GPSLatitudeRef")
            gps_longitude = gps_info.get("GPSLongitude")
            gps_longitude_ref = gps_info.get("GPSLongitudeRef")

            if not all([gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref]):
                return None

            lat = ExifService._convert_to_degrees(gps_latitude)
            lon = ExifService._convert_to_degrees(gps_longitude)

            if lat is None or lon is None:
                return None

            # Adjust for hemisphere
            if gps_latitude_ref == "S":
                lat = -lat
            if gps_longitude_ref == "W":
                lon = -lon

            return {
                "latitude": lat,
                "longitude": lon,
            }
        except Exception as e:
            logger.warning(f"Failed to extract GPS coordinates: {e}")
            return None

    @staticmethod
    def extract_exif_from_bytes(image_bytes: bytes) -> Dict[str, Any]:
        """
        Extract EXIF data from image bytes.

        Args:
            image_bytes: Image file bytes

        Returns:
            Dictionary containing EXIF metadata
        """
        exif_data = {}

        try:
            image = Image.open(BytesIO(image_bytes))

            # Get image dimensions
            exif_data["width"] = image.width
            exif_data["height"] = image.height

            # Extract EXIF data
            exif_raw = image.getexif()

            if not exif_raw:
                logger.info("No EXIF data found in image")
                return exif_data

            # Extract standard EXIF tags
            for tag_id, value in exif_raw.items():
                tag_name = TAGS.get(tag_id, tag_id)

                # Convert bytes to string for storage
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="ignore")
                    except:
                        value = str(value)

                # Extract specific fields we care about
                if tag_name == "Make":
                    exif_data["camera_make"] = str(value).strip()
                elif tag_name == "Model":
                    exif_data["camera_model"] = str(value).strip()
                elif tag_name == "DateTime":
                    exif_data["timestamp"] = str(value)
                elif tag_name == "DateTimeOriginal":
                    exif_data["timestamp_original"] = str(value)
                elif tag_name == "Orientation":
                    exif_data["orientation"] = int(value)
                elif tag_name == "Flash":
                    exif_data["flash"] = int(value)
                elif tag_name == "FocalLength":
                    exif_data["focal_length"] = float(value) if value else None
                elif tag_name == "ExposureTime":
                    exif_data["exposure_time"] = str(value)
                elif tag_name == "FNumber":
                    exif_data["f_number"] = float(value) if value else None
                elif tag_name == "ISOSpeedRatings":
                    exif_data["iso"] = int(value) if value else None

            # Extract GPS data if available
            gps_info_raw = exif_raw.get_ifd(0x8825)  # GPS IFD tag
            if gps_info_raw:
                gps_info = {}
                for tag_id, value in gps_info_raw.items():
                    tag_name = GPSTAGS.get(tag_id, tag_id)
                    gps_info[tag_name] = value

                gps_coordinates = ExifService._get_gps_coordinates(gps_info)
                if gps_coordinates:
                    exif_data["gps_coordinates"] = gps_coordinates

            logger.info(f"Extracted EXIF data: {len(exif_data)} fields")
            return exif_data

        except Exception as e:
            logger.warning(f"Failed to extract EXIF data: {e}")
            # Return at least the basic info we might have collected
            return exif_data

    @staticmethod
    async def extract_exif_from_url(url: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Download image from URL and extract EXIF data.

        Args:
            url: Image URL
            timeout: Request timeout in seconds

        Returns:
            Dictionary containing EXIF metadata
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content

            return ExifService.extract_exif_from_bytes(image_bytes)

        except httpx.HTTPError as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to extract EXIF from URL {url}: {e}")
            return {}

    @staticmethod
    def extract_exif_from_file(file_path: str) -> Dict[str, Any]:
        """
        Extract EXIF data from a file path.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary containing EXIF metadata
        """
        try:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
            return ExifService.extract_exif_from_bytes(image_bytes)
        except Exception as e:
            logger.error(f"Failed to extract EXIF from file {file_path}: {e}")
            return {}
