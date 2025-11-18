"""S3 archival service for long-term storage of detection results"""

import json
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from src.services.s3_service import S3Service


class S3ArchivalService:
    """
    Service for archiving detection results, segmentation masks, and depth maps
    to S3 for long-term storage and analytics.
    """

    def __init__(self, s3_service: S3Service):
        """Initialize with S3 service"""
        self.s3_service = s3_service

    def archive_detection_result(
        self,
        detection_id: UUID,
        photo_id: UUID,
        detection_type: str,
        results: Dict[str, Any],
        model_version: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Archive detection result to S3.

        Args:
            detection_id: UUID of the detection
            photo_id: UUID of the photo
            detection_type: Type of detection
            results: Detection results
            model_version: Model version
            confidence: Confidence score
            metadata: Additional metadata

        Returns:
            S3 key of the archived result
        """
        # Create archive object
        archive_data = {
            "detection_id": str(detection_id),
            "photo_id": str(photo_id),
            "detection_type": detection_type,
            "model_version": model_version,
            "confidence": confidence,
            "results": results,
            "archived_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        # Generate S3 key
        s3_key = self._generate_archive_key(
            detection_type, photo_id, detection_id
        )

        # Upload to S3
        self.s3_service.upload_json(s3_key, archive_data)

        return s3_key

    def archive_aggregated_results(
        self,
        photo_id: UUID,
        aggregated_results: Dict[str, Any],
    ) -> str:
        """
        Archive aggregated detection results to S3.

        Args:
            photo_id: UUID of the photo
            aggregated_results: Aggregated detection results

        Returns:
            S3 key of the archived result
        """
        # Add archival metadata
        archive_data = {
            **aggregated_results,
            "archived_at": datetime.utcnow().isoformat(),
        }

        # Generate S3 key
        s3_key = self._generate_aggregated_archive_key(photo_id)

        # Upload to S3
        self.s3_service.upload_json(s3_key, archive_data)

        return s3_key

    def archive_segmentation_mask(
        self,
        detection_id: UUID,
        photo_id: UUID,
        mask_data: bytes,
        format: str = "png",
    ) -> str:
        """
        Archive segmentation mask to S3.

        Args:
            detection_id: UUID of the detection
            photo_id: UUID of the photo
            mask_data: Binary mask data
            format: Image format (png, jpg, etc.)

        Returns:
            S3 key of the archived mask
        """
        # Generate S3 key
        s3_key = self._generate_mask_key(photo_id, detection_id, format)

        # Upload to S3
        content_type = f"image/{format}"
        self.s3_service.upload_file_obj(
            mask_data, s3_key, content_type=content_type
        )

        return s3_key

    def archive_depth_map(
        self,
        detection_id: UUID,
        photo_id: UUID,
        depth_data: bytes,
        format: str = "npy",
    ) -> str:
        """
        Archive depth map to S3.

        Args:
            detection_id: UUID of the detection
            photo_id: UUID of the photo
            depth_data: Binary depth map data
            format: Data format (npy, png, etc.)

        Returns:
            S3 key of the archived depth map
        """
        # Generate S3 key
        s3_key = self._generate_depth_map_key(photo_id, detection_id, format)

        # Upload to S3
        content_type = "application/octet-stream"
        if format == "png":
            content_type = "image/png"

        self.s3_service.upload_file_obj(
            depth_data, s3_key, content_type=content_type
        )

        return s3_key

    def retrieve_archived_result(
        self, s3_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve archived detection result from S3.

        Args:
            s3_key: S3 key of the archived result

        Returns:
            Archived result dictionary or None if not found
        """
        try:
            data = self.s3_service.download_json(s3_key)
            return data
        except Exception as e:
            print(f"Failed to retrieve archived result: {str(e)}")
            return None

    def retrieve_archived_mask(self, s3_key: str) -> Optional[bytes]:
        """
        Retrieve archived segmentation mask from S3.

        Args:
            s3_key: S3 key of the archived mask

        Returns:
            Binary mask data or None if not found
        """
        try:
            data = self.s3_service.download_file(s3_key)
            return data
        except Exception as e:
            print(f"Failed to retrieve archived mask: {str(e)}")
            return None

    def retrieve_archived_depth_map(self, s3_key: str) -> Optional[bytes]:
        """
        Retrieve archived depth map from S3.

        Args:
            s3_key: S3 key of the archived depth map

        Returns:
            Binary depth map data or None if not found
        """
        try:
            data = self.s3_service.download_file(s3_key)
            return data
        except Exception as e:
            print(f"Failed to retrieve archived depth map: {str(e)}")
            return None

    @staticmethod
    def _generate_archive_key(
        detection_type: str, photo_id: UUID, detection_id: UUID
    ) -> str:
        """
        Generate S3 key for detection result archive.

        Format: detections/{detection_type}/{year}/{month}/{photo_id}/{detection_id}.json
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        return f"detections/{detection_type}/{year}/{month}/{photo_id}/{detection_id}.json"

    @staticmethod
    def _generate_aggregated_archive_key(photo_id: UUID) -> str:
        """
        Generate S3 key for aggregated results archive.

        Format: detections/aggregated/{year}/{month}/{photo_id}.json
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        return f"detections/aggregated/{year}/{month}/{photo_id}.json"

    @staticmethod
    def _generate_mask_key(
        photo_id: UUID, detection_id: UUID, format: str
    ) -> str:
        """
        Generate S3 key for segmentation mask.

        Format: masks/{year}/{month}/{photo_id}/{detection_id}.{format}
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        return f"masks/{year}/{month}/{photo_id}/{detection_id}.{format}"

    @staticmethod
    def _generate_depth_map_key(
        photo_id: UUID, detection_id: UUID, format: str
    ) -> str:
        """
        Generate S3 key for depth map.

        Format: depth_maps/{year}/{month}/{photo_id}/{detection_id}.{format}
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        return f"depth_maps/{year}/{month}/{photo_id}/{detection_id}.{format}"
