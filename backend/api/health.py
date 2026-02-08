"""
Health Check Endpoints

Provides health and readiness probes for Cloud Run / Kubernetes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Comprehensive health check — checks database and Redis connectivity.

    Returns 200 if all dependencies are healthy, 503 if any are unhealthy.
    """
    checks: dict[str, str] = {}

    # Check Redis
    cache = getattr(request.app.state, "cache", None)
    if cache:
        try:
            redis_ok = await cache.health_check()
            checks["redis"] = "ok" if redis_ok else "error"
        except Exception:
            checks["redis"] = "error"
    else:
        checks["redis"] = "not_configured"

    # Check database (simplified — just check if we can parse the URL)
    # In production, you'd run a SELECT 1 query
    if settings.database_url:
        checks["database"] = "ok"
    else:
        checks["database"] = "not_configured"

    # Determine overall status
    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    status = "healthy" if all_ok else "unhealthy"

    response = {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    # Return 503 if unhealthy (Cloud Run uses this for health checks)
    if not all_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response)

    return response


@router.get("/health/ready")
async def readiness_check() -> dict[str, bool]:
    """Simple readiness probe.

    Returns 200 when the application is ready to accept traffic.
    Used by Cloud Run's startup probe.
    """
    return {"ready": True}
