"""
Billing & Subscription Models

Pydantic models for Stripe billing integration, subscription management,
and plan definitions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    """Available subscription tiers."""
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Stripe subscription statuses."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    UNPAID = "unpaid"


# ---------------------------------------------------------------------------
# Plan Definitions (static configuration)
# ---------------------------------------------------------------------------

class PlanLimits(BaseModel):
    """Limits for a subscription plan."""
    max_repos: int = Field(..., description="Maximum number of tracked repositories")
    max_scans_per_month: int = Field(..., description="Maximum scans per billing period")
    max_team_members: int = Field(..., description="Maximum team members")
    history_days: int = Field(..., description="Days of historical data retained")
    slack_integration: bool = Field(default=False)
    custom_thresholds: bool = Field(default=False)
    custom_rules: bool = Field(default=False)
    sso: bool = Field(default=False)
    audit_logs: bool = Field(default=False)
    priority_support: bool = Field(default=False)
    sla: Optional[str] = Field(default=None, description="SLA guarantee (e.g., '99.9%')")


# Define the limits for each plan tier
PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        max_repos=3,
        max_scans_per_month=50,
        max_team_members=1,
        history_days=7,
    ),
    PlanTier.PRO: PlanLimits(
        max_repos=15,
        max_scans_per_month=500,
        max_team_members=5,
        history_days=90,
        slack_integration=True,
    ),
    PlanTier.BUSINESS: PlanLimits(
        max_repos=999999,  # Unlimited
        max_scans_per_month=5000,
        max_team_members=999999,
        history_days=365,
        slack_integration=True,
        custom_thresholds=True,
        sso=True,
        audit_logs=True,
        priority_support=True,
        sla="99.9%",
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        max_repos=999999,
        max_scans_per_month=999999,  # Unlimited
        max_team_members=999999,
        history_days=999999,  # Unlimited
        slack_integration=True,
        custom_thresholds=True,
        custom_rules=True,
        sso=True,
        audit_logs=True,
        priority_support=True,
        sla="99.95%",
    ),
}


# ---------------------------------------------------------------------------
# Subscription Models
# ---------------------------------------------------------------------------

class Subscription(BaseModel):
    """An organization's subscription status."""
    id: Optional[UUID] = None
    org_id: UUID
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    plan: PlanTier = PlanTier.FREE
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    scans_used_this_period: int = 0
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @property
    def limits(self) -> PlanLimits:
        """Get the limits for the current plan."""
        return PLAN_LIMITS[self.plan]

    @property
    def scans_remaining(self) -> int:
        """Calculate remaining scans for this billing period."""
        return max(0, self.limits.max_scans_per_month - self.scans_used_this_period)

    @property
    def is_active(self) -> bool:
        """Check if the subscription is active (including trialing)."""
        return self.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}

    @property
    def can_scan(self) -> bool:
        """Check if the organization can perform a scan."""
        return self.is_active and self.scans_remaining > 0


# ---------------------------------------------------------------------------
# API Request/Response Models
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    plan: PlanTier = Field(..., description="Target plan tier")
    success_url: str = Field(..., description="URL to redirect on success")
    cancel_url: str = Field(..., description="URL to redirect on cancellation")


class CheckoutResponse(BaseModel):
    """Response with the Stripe Checkout session URL."""
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    """Response with the Stripe Customer Portal URL."""
    portal_url: str


class SubscriptionResponse(BaseModel):
    """API response with subscription details."""
    plan: PlanTier
    status: SubscriptionStatus
    scan_limit: int
    repo_limit: int
    scans_used: int
    scans_remaining: int
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    cancel_at_period_end: bool = False

    @classmethod
    def from_subscription(cls, sub: Subscription) -> SubscriptionResponse:
        """Create a response from a Subscription model."""
        return cls(
            plan=sub.plan,
            status=sub.status,
            scan_limit=sub.limits.max_scans_per_month,
            repo_limit=sub.limits.max_repos,
            scans_used=sub.scans_used_this_period,
            scans_remaining=sub.scans_remaining,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            stripe_customer_id=sub.stripe_customer_id,
        )
