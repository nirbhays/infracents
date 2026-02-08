"""
InfraCents — Terraform Cost Estimator API

Main FastAPI application entry point. Configures middleware, routers, startup/shutdown
events, and global error handling.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from api.webhooks import router as webhooks_router
from api.dashboard import router as dashboard_router
from api.billing import router as billing_router
from api.health import router as health_router
from services.cache_service import CacheService

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("infracents")


# ---------------------------------------------------------------------------
# Sentry Initialization (production only)
# ---------------------------------------------------------------------------
if settings.sentry_dsn and settings.is_production:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"infracents@{settings.app_version}",
        traces_sample_rate=0.1,
    )
    logger.info("Sentry initialized for production monitoring")


# ---------------------------------------------------------------------------
# Application Lifespan (startup/shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle — connect to services on startup,
    disconnect on shutdown."""
    logger.info(
        "Starting InfraCents API v%s (%s)", settings.app_version, settings.environment
    )

    # Initialize Redis cache
    cache = CacheService()
    await cache.connect()
    app.state.cache = cache
    logger.info("Redis cache connected")

    yield  # Application is running

    # Shutdown: close connections
    await cache.disconnect()
    logger.info("Redis cache disconnected")
    logger.info("InfraCents API shutdown complete")


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="InfraCents API",
        description="Terraform Cost Estimator — know what your changes cost before they ship.",
        version=settings.app_version,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Middleware ─────────────────────────────────────────────────────
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next) -> Response:
        """Add X-Process-Time header to all responses for performance monitoring."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response

    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        """Log all incoming requests with method, path, and status code."""
        logger.info("→ %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("← %s %s → %d", request.method, request.url.path, response.status_code)
        return response

    # ── Exception Handler ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unhandled exceptions and return a clean JSON error response.

        In production, we don't leak internal error details. In development,
        we include the exception message for debugging.
        """
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)

        detail = "Internal server error"
        if settings.is_development:
            detail = f"{type(exc).__name__}: {exc}"

        return JSONResponse(
            status_code=500,
            content={
                "detail": detail,
                "error_code": "INTERNAL_ERROR",
                "status_code": 500,
            },
        )

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(health_router, tags=["Health"])
    app.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(billing_router, prefix="/api/billing", tags=["Billing"])

    # ── Root Endpoint ─────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint — simple redirect hint to docs or landing page."""
        return {
            "name": "InfraCents API",
            "version": settings.app_version,
            "docs": "/docs" if settings.is_development else "https://infracents.dev",
        }

    return app


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
