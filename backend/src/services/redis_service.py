"""Redis service for caching and token blacklisting"""

import redis.asyncio as redis
from typing import Optional
from datetime import timedelta
from src.config import settings


class RedisService:
    """Service for Redis operations including token blacklisting"""

    _client: Optional[redis.Redis] = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """Get or create Redis client"""
        if cls._client is None:
            cls._client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return cls._client

    @classmethod
    async def close(cls):
        """Close Redis connection"""
        if cls._client:
            await cls._client.close()
            cls._client = None

    async def blacklist_token(self, token: str, expiration_seconds: int):
        """
        Add a token to the blacklist

        Args:
            token: JWT token to blacklist
            expiration_seconds: How long to keep the token in blacklist (should match token expiration)
        """
        client = await self.get_client()
        key = f"blacklist:{token}"
        await client.setex(key, expiration_seconds, "1")

    async def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted

        Args:
            token: JWT token to check

        Returns:
            True if token is blacklisted, False otherwise
        """
        client = await self.get_client()
        key = f"blacklist:{token}"
        result = await client.get(key)
        return result is not None

    async def increment_login_attempts(self, ip_address: str) -> int:
        """
        Increment failed login attempts for an IP address

        Args:
            ip_address: IP address to track

        Returns:
            Current number of attempts
        """
        client = await self.get_client()
        key = f"login_attempts:{ip_address}"
        count = await client.incr(key)

        # Set expiration on first attempt
        if count == 1:
            await client.expire(key, 900)  # 15 minutes

        return count

    async def reset_login_attempts(self, ip_address: str):
        """
        Reset failed login attempts for an IP address

        Args:
            ip_address: IP address to reset
        """
        client = await self.get_client()
        key = f"login_attempts:{ip_address}"
        await client.delete(key)

    async def get_login_attempts(self, ip_address: str) -> int:
        """
        Get current failed login attempts for an IP address

        Args:
            ip_address: IP address to check

        Returns:
            Number of failed attempts
        """
        client = await self.get_client()
        key = f"login_attempts:{ip_address}"
        result = await client.get(key)
        return int(result) if result else 0

    async def set_cache(self, key: str, value: str, expiration: int = 3600):
        """
        Set a cache value

        Args:
            key: Cache key
            value: Value to cache
            expiration: Expiration time in seconds (default 1 hour)
        """
        client = await self.get_client()
        await client.setex(key, expiration, value)

    async def get_cache(self, key: str) -> Optional[str]:
        """
        Get a cache value

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        client = await self.get_client()
        return await client.get(key)

    async def delete_cache(self, key: str):
        """
        Delete a cache value

        Args:
            key: Cache key
        """
        client = await self.get_client()
        await client.delete(key)
