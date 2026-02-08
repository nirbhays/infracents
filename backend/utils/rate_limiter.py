"""
Rate Limiter

Provides rate limiting using Redis as the backend.
Implements a simple sliding window counter pattern.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request

from config import get_settings
from services.cache_service import CacheService

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimiter:
    """Rate limiter using Redis sliding window counters.

    Usage:
        limiter = RateLimiter(cache_service)
        await limiter.check("webhook", f"installation:{installation_id}", limit=100)
    """

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache

    async def check(
        self,
        category: str,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check if a request is within rate limits.

        Args:
            category: Rate limit category (webhook, api, billing).
            identifier: Unique identifier (installation ID, user ID, IP).
            limit: Max requests per window. If None, uses category defaults.
            window_seconds: Window size in seconds.

        Returns:
            Tuple of (allowed, remaining).

        Raises:
            HTTPException: 429 if rate limit exceeded.
        """
        if limit is None:
            limit = self._get_default_limit(category)

        if not self.cache or not self.cache.is_connected:
            return True, limit  # Fail open if Redis unavailable

        key = f"ratelimit:{category}:{identifier}"
        allowed, remaining = await self.cache.check_rate_limit(key, limit, window_seconds)

        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s/%s (limit=%d, window=%ds)",
                category, identifier, limit, window_seconds,
            )

        return allowed, remaining

    async def check_or_raise(
        self,
        category: str,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: int = 60,
    ) -> int:
        """Check rate limit and raise 429 if exceeded.

        Args:
            category: Rate limit category.
            identifier: Unique identifier.
            limit: Max requests per window.
            window_seconds: Window size.

        Returns:
            Remaining requests.

        Raises:
            HTTPException: 429 Too Many Requests if limit exceeded.
        """
        allowed, remaining = await self.check(category, identifier, limit, window_seconds)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "detail": "Rate limit exceeded",
                    "error_code": "RATE_LIMITED",
                    "retry_after_seconds": window_seconds,
                },
            )

        return remaining

    def _get_default_limit(self, category: str) -> int:
        """Get the default rate limit for a category."""
        defaults = {
            "webhook": settings.rate_limit_webhook,
            "api": settings.rate_limit_api,
            "billing": settings.rate_limit_billing,
        }
        return defaults.get(category, 60)


def get_client_ip(request: Request) -> str:
    """Extract the client IP from a request, respecting proxy headers."""
    # Check for Cloudflare/proxy headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (client IP)
        return forwarded_for.split(",")[0].strip()

    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"
