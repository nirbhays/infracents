"""
Security Utilities

Provides webhook signature verification, JWT validation, and other
security-related helpers.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def verify_github_signature(
    payload: bytes,
    signature_header: Optional[str],
) -> bool:
    """Verify a GitHub webhook signature (HMAC-SHA256).

    GitHub signs every webhook payload with the shared webhook secret.
    We recompute the HMAC and compare using constant-time comparison
    to prevent timing attacks.

    Args:
        payload: The raw request body bytes.
        signature_header: The X-Hub-Signature-256 header value.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not settings.github_webhook_secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not configured — skipping signature verification")
        return True  # Skip in development if not configured

    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    # The header format is: sha256=<hex-digest>
    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format (expected sha256= prefix)")
        return False

    expected_signature = signature_header[7:]  # Remove "sha256=" prefix

    # Compute the HMAC-SHA256
    computed = hmac.new(
        key=settings.github_webhook_secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(computed, expected_signature)

    if not is_valid:
        logger.warning("GitHub webhook signature verification FAILED")

    return is_valid


def verify_stripe_signature(
    payload: bytes,
    signature_header: Optional[str],
) -> bool:
    """Verify a Stripe webhook signature.

    Uses Stripe's signature verification format which includes a timestamp
    to prevent replay attacks.

    Args:
        payload: The raw request body bytes.
        signature_header: The Stripe-Signature header value.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not settings.stripe_webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured — skipping verification")
        return True

    if not signature_header:
        logger.warning("Missing Stripe-Signature header")
        return False

    try:
        # Parse the Stripe signature header
        # Format: t=timestamp,v1=signature
        elements = {}
        for part in signature_header.split(","):
            key, value = part.split("=", 1)
            elements[key.strip()] = value.strip()

        timestamp = elements.get("t", "")
        signature = elements.get("v1", "")

        if not timestamp or not signature:
            return False

        # Build the signed payload: timestamp + "." + payload
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"

        # Compute expected signature
        computed = hmac.new(
            key=settings.stripe_webhook_secret.encode("utf-8"),
            msg=signed_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, signature)

    except Exception as e:
        logger.error("Stripe signature verification error: %s", e)
        return False


async def validate_clerk_jwt(token: str) -> Optional[dict[str, Any]]:
    """Validate a Clerk JWT token and extract claims.

    Fetches Clerk's JWKS (JSON Web Key Set) to validate the token signature.
    Extracts the user ID and organization ID from the claims.

    Args:
        token: The JWT token from the Authorization header.

    Returns:
        The decoded JWT claims, or None if validation fails.
    """
    if not settings.clerk_jwt_issuer:
        logger.warning("CLERK_JWT_ISSUER not configured — returning mock claims")
        # In development, return mock claims
        return {
            "sub": "user_dev",
            "org_id": "org_dev",
            "email": "dev@infracents.dev",
        }

    try:
        import jwt as pyjwt
        from jwt import PyJWKClient

        # Fetch JWKS from Clerk
        jwks_url = f"{settings.clerk_jwt_issuer}/.well-known/jwks.json"
        jwks_client = PyJWKClient(jwks_url)

        # Get the signing key
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the JWT
        claims = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_jwt_issuer,
            options={"verify_aud": False},  # Clerk doesn't always set audience
        )

        return claims

    except Exception as e:
        logger.warning("JWT validation failed: %s", e)
        return None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract the token from a Bearer authorization header.

    Args:
        authorization: The Authorization header value.

    Returns:
        The token string, or None if the header is missing/malformed.
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    return authorization[7:]
