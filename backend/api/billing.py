"""
Billing API Endpoints

Manages subscription billing via Stripe:
- Get subscription status
- Create checkout sessions (upgrade)
- Create portal sessions (manage billing)
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException

from models.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionResponse,
)
from services.billing_service import BillingService
from utils.security import extract_bearer_token, validate_clerk_jwt

logger = logging.getLogger(__name__)
router = APIRouter()

billing_service = BillingService()


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    """Dependency: Extract and validate the current user from JWT."""
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    claims = await validate_clerk_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return claims


@router.get("/subscription")
async def get_subscription(
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current subscription status for the authenticated organization."""
    org_id = UUID(user.get("org_id", str(uuid4())))

    subscription = await billing_service.get_subscription(org_id)
    response = SubscriptionResponse.from_subscription(subscription)

    return response.model_dump()


@router.post("/checkout")
async def create_checkout(
    request: CheckoutRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Stripe Checkout session for upgrading to a paid plan."""
    org_id = UUID(user.get("org_id", str(uuid4())))
    email = user.get("email", "user@example.com")

    try:
        result = await billing_service.create_checkout_session(
            org_id=org_id,
            request=request,
            customer_email=email,
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Checkout session creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/portal")
async def create_portal(
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Stripe Customer Portal session for managing billing."""
    org_id = UUID(user.get("org_id", str(uuid4())))

    subscription = await billing_service.get_subscription(org_id)

    if not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No active Stripe subscription. Please upgrade first.",
        )

    try:
        result = await billing_service.create_portal_session(
            stripe_customer_id=subscription.stripe_customer_id,
            return_url="https://infracents.dev/dashboard/settings",
        )
        return result.model_dump()
    except Exception as e:
        logger.error("Portal session creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create portal session")
