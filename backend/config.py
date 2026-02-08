"""
InfraCents Backend Configuration

Centralized configuration management using environment variables with sensible defaults.
All configuration is loaded once at startup and validated using Pydantic.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables can be set directly or loaded from a .env file.
    All secrets should be provided via environment variables (never hardcoded).
    """

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    environment: str = Field(default="development", description="Runtime environment")
    app_version: str = Field(default="0.1.0", description="Application version")
    log_level: str = Field(default="info", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    # -------------------------------------------------------------------------
    # Database (PostgreSQL / Supabase)
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql://infracents:infracents@localhost:5432/infracents",
        description="PostgreSQL connection string",
    )
    db_pool_size: int = Field(default=5, description="Connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")

    # -------------------------------------------------------------------------
    # Redis (Upstash)
    # -------------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string",
    )
    redis_price_cache_ttl: int = Field(
        default=3600, description="Price cache TTL in seconds (1 hour)"
    )

    # -------------------------------------------------------------------------
    # GitHub App
    # -------------------------------------------------------------------------
    github_app_id: Optional[str] = Field(
        default=None, description="GitHub App ID"
    )
    github_app_client_id: Optional[str] = Field(
        default=None, description="GitHub App Client ID"
    )
    github_app_client_secret: Optional[str] = Field(
        default=None, description="GitHub App Client Secret"
    )
    github_webhook_secret: Optional[str] = Field(
        default=None, description="GitHub webhook HMAC secret"
    )
    github_private_key: Optional[str] = Field(
        default=None, description="GitHub App private key (PEM format)"
    )

    # -------------------------------------------------------------------------
    # Stripe
    # -------------------------------------------------------------------------
    stripe_secret_key: Optional[str] = Field(
        default=None, description="Stripe secret API key"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None, description="Stripe webhook signing secret"
    )
    stripe_price_pro: Optional[str] = Field(
        default=None, description="Stripe Price ID for Pro plan"
    )
    stripe_price_business: Optional[str] = Field(
        default=None, description="Stripe Price ID for Business plan"
    )
    stripe_price_enterprise: Optional[str] = Field(
        default=None, description="Stripe Price ID for Enterprise plan"
    )

    # -------------------------------------------------------------------------
    # Clerk Authentication
    # -------------------------------------------------------------------------
    clerk_secret_key: Optional[str] = Field(
        default=None, description="Clerk secret key for JWT validation"
    )
    clerk_jwt_issuer: Optional[str] = Field(
        default=None, description="Clerk JWT issuer URL"
    )

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------
    sentry_dsn: Optional[str] = Field(
        default=None, description="Sentry DSN for error tracking"
    )

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    rate_limit_webhook: int = Field(
        default=100, description="Max webhook requests per minute per installation"
    )
    rate_limit_api: int = Field(
        default=60, description="Max API requests per minute per user"
    )
    rate_limit_billing: int = Field(
        default=10, description="Max billing API requests per minute per user"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings.

    Uses lru_cache to ensure settings are only loaded once.
    In tests, you can override this with dependency injection.
    """
    return Settings()
