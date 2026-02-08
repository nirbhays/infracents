"""
Redis Cache Service

Provides a caching layer on top of Redis for:
- Pricing data (1-hour TTL)
- Rate limiting counters
- General key-value caching

Designed for use with Upstash Redis (serverless) but compatible with
any Redis instance.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    """Async Redis cache service.

    Provides high-level methods for caching pricing data, rate limiting,
    and general key-value operations. All methods are async and safe to
    call even if Redis is unavailable (they'll log warnings and return None).
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize the cache service.

        Args:
            redis_url: Redis connection URL. If None, uses the settings default.
        """
        self._redis_url = redis_url or settings.redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis.

        Called during application startup. If the connection fails,
        the service degrades gracefully (cache misses everywhere).
        """
        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test the connection
            await self._redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning("Redis connection failed: %s — caching disabled", e)
            self._redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis. Called during application shutdown."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._redis is not None

    # -------------------------------------------------------------------------
    # Pricing Cache
    # -------------------------------------------------------------------------

    async def get_price(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Get a cached price by key.

        Args:
            cache_key: The pricing cache key (built by the pricing engine).

        Returns:
            The cached price data, or None on cache miss or Redis unavailability.
        """
        if not self._redis:
            return None

        try:
            data = await self._redis.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Redis GET failed for %s: %s", cache_key, e)
            return None

    async def set_price(
        self,
        cache_key: str,
        price_data: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Cache a price lookup result.

        Args:
            cache_key: The pricing cache key.
            price_data: The price data to cache.
            ttl: Time-to-live in seconds. Defaults to the configured price cache TTL.
        """
        if not self._redis:
            return

        ttl = ttl or settings.redis_price_cache_ttl

        try:
            await self._redis.setex(
                cache_key,
                ttl,
                json.dumps(price_data),
            )
        except Exception as e:
            logger.warning("Redis SET failed for %s: %s", cache_key, e)

    async def delete_price(self, cache_key: str) -> None:
        """Delete a cached price entry."""
        if not self._redis:
            return
        try:
            await self._redis.delete(cache_key)
        except Exception as e:
            logger.warning("Redis DELETE failed for %s: %s", cache_key, e)

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check and increment a rate limit counter.

        Uses Redis INCR with TTL for a sliding window rate limiter.

        Args:
            key: Rate limit key (e.g., "ratelimit:webhook:installation_123").
            limit: Maximum allowed requests in the window.
            window_seconds: Window size in seconds (default: 60).

        Returns:
            Tuple of (allowed, remaining). allowed is True if under limit.
        """
        if not self._redis:
            return True, limit  # If Redis is down, allow all requests

        try:
            # Increment the counter
            current = await self._redis.incr(key)

            # Set TTL only on first increment (when counter is 1)
            if current == 1:
                await self._redis.expire(key, window_seconds)

            remaining = max(0, limit - current)
            allowed = current <= limit

            return allowed, remaining

        except Exception as e:
            logger.warning("Rate limit check failed for %s: %s", key, e)
            return True, limit  # Fail open

    # -------------------------------------------------------------------------
    # General Key-Value Operations
    # -------------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """Get a string value by key."""
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning("Redis GET failed for %s: %s", key, e)
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a string value with optional TTL."""
        if not self._redis:
            return
        try:
            if ttl:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
        except Exception as e:
            logger.warning("Redis SET failed for %s: %s", key, e)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.warning("Redis DELETE failed for %s: %s", key, e)

    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self._redis:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
