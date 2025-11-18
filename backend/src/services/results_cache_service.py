"""Results cache service for Redis-based caching of detection results"""

import json
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import timedelta
from src.services.redis_service import RedisService


class ResultsCacheService:
    """
    Service for caching detection results in Redis for fast retrieval.
    Implements TTL-based caching with invalidation on updates.
    """

    # Cache TTL configurations
    ACTIVE_RESULT_TTL = timedelta(hours=24)  # 24 hours for recent results
    OLDER_RESULT_TTL = timedelta(hours=1)  # 1 hour for older results
    AGGREGATED_RESULT_TTL = timedelta(hours=12)  # 12 hours for aggregated results

    def __init__(self, redis_service: RedisService):
        """Initialize with Redis service"""
        self.redis = redis_service

    def cache_detection_result(
        self,
        detection_id: UUID,
        result: Dict[str, Any],
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """
        Cache a detection result in Redis.

        Args:
            detection_id: UUID of the detection
            result: Detection result as dictionary
            ttl: Time to live for cache entry (defaults to ACTIVE_RESULT_TTL)

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            key = self._get_detection_key(detection_id)
            ttl = ttl or self.ACTIVE_RESULT_TTL

            # Serialize result to JSON
            value = json.dumps(result, default=str)

            # Store in Redis with TTL
            self.redis.set(key, value, ex=int(ttl.total_seconds()))

            return True

        except Exception as e:
            # Log error but don't fail - caching is not critical
            print(f"Failed to cache detection result: {str(e)}")
            return False

    def get_cached_detection_result(
        self, detection_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached detection result from Redis.

        Args:
            detection_id: UUID of the detection

        Returns:
            Detection result dictionary or None if not cached
        """
        try:
            key = self._get_detection_key(detection_id)
            value = self.redis.get(key)

            if value:
                return json.loads(value)

            return None

        except Exception as e:
            print(f"Failed to retrieve cached detection result: {str(e)}")
            return None

    def cache_aggregated_result(
        self,
        photo_id: UUID,
        aggregated_result: Dict[str, Any],
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """
        Cache an aggregated detection result in Redis.

        Args:
            photo_id: UUID of the photo
            aggregated_result: Aggregated result dictionary
            ttl: Time to live (defaults to AGGREGATED_RESULT_TTL)

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            key = self._get_aggregated_key(photo_id)
            ttl = ttl or self.AGGREGATED_RESULT_TTL

            value = json.dumps(aggregated_result, default=str)
            self.redis.set(key, value, ex=int(ttl.total_seconds()))

            return True

        except Exception as e:
            print(f"Failed to cache aggregated result: {str(e)}")
            return False

    def get_cached_aggregated_result(
        self, photo_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached aggregated result from Redis.

        Args:
            photo_id: UUID of the photo

        Returns:
            Aggregated result dictionary or None if not cached
        """
        try:
            key = self._get_aggregated_key(photo_id)
            value = self.redis.get(key)

            if value:
                return json.loads(value)

            return None

        except Exception as e:
            print(f"Failed to retrieve cached aggregated result: {str(e)}")
            return None

    def invalidate_detection_cache(self, detection_id: UUID) -> bool:
        """
        Invalidate cached detection result.

        Args:
            detection_id: UUID of the detection

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            key = self._get_detection_key(detection_id)
            self.redis.delete(key)
            return True

        except Exception as e:
            print(f"Failed to invalidate detection cache: {str(e)}")
            return False

    def invalidate_aggregated_cache(self, photo_id: UUID) -> bool:
        """
        Invalidate cached aggregated result.

        Args:
            photo_id: UUID of the photo

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            key = self._get_aggregated_key(photo_id)
            self.redis.delete(key)
            return True

        except Exception as e:
            print(f"Failed to invalidate aggregated cache: {str(e)}")
            return False

    def invalidate_photo_caches(self, photo_id: UUID, detection_ids: list[UUID]) -> bool:
        """
        Invalidate all caches related to a photo (aggregated + individual detections).

        Args:
            photo_id: UUID of the photo
            detection_ids: List of detection IDs to invalidate

        Returns:
            True if all invalidated successfully, False otherwise
        """
        try:
            # Invalidate aggregated cache
            self.invalidate_aggregated_cache(photo_id)

            # Invalidate individual detection caches
            for detection_id in detection_ids:
                self.invalidate_detection_cache(detection_id)

            return True

        except Exception as e:
            print(f"Failed to invalidate photo caches: {str(e)}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics from Redis.

        Returns:
            Dictionary with cache statistics
        """
        try:
            info = self.redis.info("stats")

            return {
                "total_keys": info.get("db0", {}).get("keys", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0),
                ),
            }

        except Exception as e:
            print(f"Failed to get cache stats: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def _get_detection_key(detection_id: UUID) -> str:
        """Generate Redis key for detection result"""
        return f"detection:result:{detection_id}"

    @staticmethod
    def _get_aggregated_key(photo_id: UUID) -> str:
        """Generate Redis key for aggregated result"""
        return f"detection:aggregated:{photo_id}"

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round(hits / total, 4)
