"""S3 service for managing photo uploads and pre-signed URLs"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional, Any
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from src.config import settings

logger = logging.getLogger(__name__)


class S3ServiceError(Exception):
    """Base exception for S3 service errors"""
    pass


class S3ConnectionError(S3ServiceError):
    """S3 connection error"""
    pass


class InvalidFileTypeError(S3ServiceError):
    """Invalid file type error"""
    pass


class FileTooLargeError(S3ServiceError):
    """File too large error"""
    pass


class S3Service:
    """Service for S3 operations including pre-signed URL generation"""

    # Constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MIN_FILE_SIZE = 1024  # 1KB
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
    PRESIGNED_URL_EXPIRATION = 900  # 15 minutes in seconds

    def __init__(self):
        """Initialize S3 client with retry configuration"""
        retry_config = Config(
            retries={
                "max_attempts": 3,
                "mode": "standard",
            },
            connect_timeout=5,
            read_timeout=10,
        )

        client_kwargs = {
            "region_name": settings.aws_region,
            "config": retry_config,
        }

        # Add credentials if provided (not needed for IAM roles)
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        # Use custom endpoint for local development (MinIO)
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        try:
            self.s3_client = boto3.client("s3", **client_kwargs)
            logger.info(f"S3 client initialized for bucket: {settings.s3_bucket}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise S3ConnectionError(f"Failed to initialize S3 client: {e}")

    def validate_file(self, file_size: int, mime_type: str) -> None:
        """
        Validate file size and MIME type.

        Args:
            file_size: File size in bytes
            mime_type: MIME type of the file

        Raises:
            FileTooLargeError: If file exceeds maximum size
            InvalidFileTypeError: If MIME type is not allowed
        """
        if file_size > self.MAX_FILE_SIZE:
            raise FileTooLargeError(
                f"File size {file_size} bytes exceeds maximum of {self.MAX_FILE_SIZE} bytes"
            )

        if file_size < self.MIN_FILE_SIZE:
            raise FileTooLargeError(
                f"File size {file_size} bytes is below minimum of {self.MIN_FILE_SIZE} bytes"
            )

        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise InvalidFileTypeError(
                f"MIME type {mime_type} not allowed. Allowed types: {self.ALLOWED_MIME_TYPES}"
            )

    def generate_s3_key(self, project_id: str, photo_id: str, file_extension: str) -> str:
        """
        Generate S3 key following the structure:
        {project_id}/{year}/{month}/{day}/{photo_id}.{extension}

        Args:
            project_id: Project UUID
            photo_id: Photo UUID
            file_extension: File extension (jpg, png, etc.)

        Returns:
            S3 key string
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        return f"{project_id}/{year}/{month}/{day}/{photo_id}.{file_extension}"

    def generate_presigned_upload_url(
        self,
        s3_key: str,
        mime_type: str,
        file_size: int,
        expiration: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Generate a pre-signed URL for uploading a file to S3.

        Args:
            s3_key: S3 key where the file will be stored
            mime_type: MIME type of the file
            file_size: Expected file size in bytes
            expiration: URL expiration time in seconds (default: 900)

        Returns:
            Dict containing upload_url and other metadata

        Raises:
            S3ConnectionError: If S3 operation fails
        """
        if expiration is None:
            expiration = self.PRESIGNED_URL_EXPIRATION

        try:
            # Generate pre-signed URL for PUT operation
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": s3_key,
                    "ContentType": mime_type,
                    "ContentLength": file_size,
                },
                ExpiresIn=expiration,
            )

            # Generate the final S3 URL for the object
            if settings.aws_endpoint_url:
                # For local development with MinIO
                s3_url = f"{settings.aws_endpoint_url}/{settings.s3_bucket}/{s3_key}"
            else:
                # For AWS S3
                s3_url = f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"

            logger.info(f"Generated pre-signed URL for key: {s3_key}")

            return {
                "upload_url": presigned_url,
                "s3_url": s3_url,
                "s3_key": s3_key,
                "expires_in_seconds": expiration,
                "headers": {
                    "Content-Type": mime_type,
                    "Content-Length": str(file_size),
                },
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 ClientError generating pre-signed URL: {error_code} - {e}")
            raise S3ConnectionError(f"Failed to generate pre-signed URL: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error generating pre-signed URL: {e}")
            raise S3ConnectionError(f"Failed to generate pre-signed URL: {str(e)}")

    def check_object_exists(self, s3_key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            s3_key: S3 key to check

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=settings.s3_bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Error checking if object exists: {e}")
            raise S3ConnectionError(f"Failed to check object existence: {e}")

    def get_object_metadata(self, s3_key: str) -> Optional[Dict]:
        """
        Get metadata for an S3 object.

        Args:
            s3_key: S3 key of the object

        Returns:
            Dictionary with object metadata or None if not found
        """
        try:
            response = self.s3_client.head_object(Bucket=settings.s3_bucket, Key=s3_key)
            return {
                "content_type": response.get("ContentType"),
                "content_length": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag"),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            logger.error(f"Error getting object metadata: {e}")
            raise S3ConnectionError(f"Failed to get object metadata: {e}")

    def delete_object(self, s3_key: str) -> bool:
        """
        Delete an object from S3.

        Args:
            s3_key: S3 key of the object to delete

        Returns:
            True if deletion was successful
        """
        try:
            self.s3_client.delete_object(Bucket=settings.s3_bucket, Key=s3_key)
            logger.info(f"Deleted object: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting object: {e}")
            raise S3ConnectionError(f"Failed to delete object: {e}")

    async def download_file_bytes(self, bucket: Optional[str], s3_key: str) -> bytes:
        """
        Download file bytes from S3.

        Args:
            bucket: S3 bucket name (uses default if None)
            s3_key: S3 key of the object

        Returns:
            File bytes

        Raises:
            S3ConnectionError: If download fails
        """
        bucket_name = bucket or settings.s3_bucket

        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            file_bytes = response["Body"].read()
            logger.debug(f"Downloaded {len(file_bytes)} bytes from {bucket_name}/{s3_key}")
            return file_bytes
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Error downloading file: {error_code} - {e}")
            raise S3ConnectionError(f"Failed to download file: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            raise S3ConnectionError(f"Failed to download file: {str(e)}")

    def upload_bytes(
        self, file_bytes: bytes, s3_key: str, content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload bytes to S3.

        Args:
            file_bytes: Bytes to upload
            s3_key: S3 key for the object
            content_type: Content type of the file

        Returns:
            S3 URL of uploaded object

        Raises:
            S3ConnectionError: If upload fails
        """
        try:
            self.s3_client.put_object(
                Bucket=settings.s3_bucket,
                Key=s3_key,
                Body=file_bytes,
                ContentType=content_type,
            )

            # Generate the S3 URL
            if settings.aws_endpoint_url:
                # For local development with MinIO
                s3_url = f"{settings.aws_endpoint_url}/{settings.s3_bucket}/{s3_key}"
            else:
                # For AWS S3
                s3_url = f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"

            logger.info(f"Uploaded {len(file_bytes)} bytes to {s3_url}")
            return s3_url

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Error uploading bytes: {error_code} - {e}")
            raise S3ConnectionError(f"Failed to upload bytes: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error uploading bytes: {e}")
            raise S3ConnectionError(f"Failed to upload bytes: {str(e)}")

    def upload_json(self, s3_key: str, data: Dict[str, Any]) -> str:
        """
        Upload JSON data to S3.

        Args:
            s3_key: S3 key for the object
            data: Dictionary to serialize as JSON

        Returns:
            S3 URL of uploaded object

        Raises:
            S3ConnectionError: If upload fails
        """
        try:
            json_bytes = json.dumps(data, default=str).encode("utf-8")
            return self.upload_bytes(json_bytes, s3_key, content_type="application/json")
        except Exception as e:
            logger.error(f"Error uploading JSON: {e}")
            raise S3ConnectionError(f"Failed to upload JSON: {str(e)}")

    def download_json(self, s3_key: str) -> Dict[str, Any]:
        """
        Download and parse JSON from S3.

        Args:
            s3_key: S3 key of the JSON object

        Returns:
            Parsed JSON dictionary

        Raises:
            S3ConnectionError: If download or parsing fails
        """
        try:
            response = self.s3_client.get_object(Bucket=settings.s3_bucket, Key=s3_key)
            json_bytes = response["Body"].read()
            data = json.loads(json_bytes.decode("utf-8"))
            logger.debug(f"Downloaded JSON from {s3_key}")
            return data
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Error downloading JSON: {error_code} - {e}")
            raise S3ConnectionError(f"Failed to download JSON: {error_code}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}")
            raise S3ConnectionError(f"Failed to parse JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error downloading JSON: {e}")
            raise S3ConnectionError(f"Failed to download JSON: {str(e)}")

    def upload_file_obj(
        self, file_obj: bytes, s3_key: str, content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file object (bytes) to S3.
        Alias for upload_bytes for compatibility.

        Args:
            file_obj: Bytes to upload
            s3_key: S3 key for the object
            content_type: Content type of the file

        Returns:
            S3 URL of uploaded object
        """
        return self.upload_bytes(file_obj, s3_key, content_type)

    def download_file(self, s3_key: str) -> bytes:
        """
        Download file bytes from S3.
        Synchronous version of download_file_bytes.

        Args:
            s3_key: S3 key of the object

        Returns:
            File bytes

        Raises:
            S3ConnectionError: If download fails
        """
        try:
            response = self.s3_client.get_object(Bucket=settings.s3_bucket, Key=s3_key)
            file_bytes = response["Body"].read()
            logger.debug(f"Downloaded {len(file_bytes)} bytes from {s3_key}")
            return file_bytes
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Error downloading file: {error_code} - {e}")
            raise S3ConnectionError(f"Failed to download file: {error_code}")
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            raise S3ConnectionError(f"Failed to download file: {str(e)}")
