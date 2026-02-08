"""
Billing Service

Manages Stripe integration for subscription billing:
- Creating checkout sessions
- Managing subscriptions
- Processing webhook events
- Checking usage limits
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

import stripe

from config import get_settings
from models.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PlanLimits,
    PlanTier,
    PortalResponse,
    Subscription,
    SubscriptionResponse,
    SubscriptionStatus,
    PLAN_LIMITS,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Stripe
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key

# Map plan tiers to Stripe price IDs
PLAN_PRICE_MAP: dict[PlanTier, Optional[str]] = {
    PlanTier.FREE: None,  # No Stripe price for free tier
    PlanTier.PRO: settings.stripe_price_pro,
    PlanTier.BUSINESS: settings.stripe_price_business,
    PlanTier.ENTERPRISE: settings.stripe_price_enterprise,
}


class BillingService:
    """Manages subscription billing via Stripe.

    Handles:
    - Creating Stripe checkout sessions for upgrades
    - Creating customer portal sessions for billing management
    - Processing Stripe webhook events (subscription lifecycle)
    - Checking usage against plan limits
    """

    async def get_subscription(self, org_id: UUID) -> Subscription:
        """Get the subscription for an organization.

        If no subscription exists, returns a default Free subscription.
        In a real implementation, this would query the database.

        Args:
            org_id: Organization UUID.

        Returns:
            The organization's subscription.
        """
        # TODO: Query database for subscription
        # For now, return a default free subscription
        return Subscription(
            org_id=org_id,
            plan=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
            scans_used_this_period=0,
        )

    async def create_checkout_session(
        self,
        org_id: UUID,
        request: CheckoutRequest,
        customer_email: str,
    ) -> CheckoutResponse:
        """Create a Stripe Checkout session for upgrading to a paid plan.

        Args:
            org_id: Organization UUID.
            request: Checkout request with target plan and URLs.
            customer_email: Customer's email for Stripe.

        Returns:
            CheckoutResponse with the checkout URL.

        Raises:
            ValueError: If the plan doesn't have a Stripe price ID configured.
        """
        price_id = PLAN_PRICE_MAP.get(request.plan)
        if not price_id:
            raise ValueError(f"No Stripe price configured for plan: {request.plan}")

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                customer_email=customer_email,
                metadata={
                    "org_id": str(org_id),
                    "plan": request.plan.value,
                },
                allow_promotion_codes=True,
            )

            logger.info(
                "Created checkout session for org %s, plan %s",
                org_id, request.plan.value,
            )

            return CheckoutResponse(
                checkout_url=session.url,
                session_id=session.id,
            )

        except stripe.error.StripeError as e:
            logger.error("Stripe checkout error: %s", e)
            raise

    async def create_portal_session(
        self,
        stripe_customer_id: str,
        return_url: str,
    ) -> PortalResponse:
        """Create a Stripe Customer Portal session for billing management.

        The portal allows customers to:
        - View invoices
        - Update payment methods
        - Cancel subscriptions
        - Change plans

        Args:
            stripe_customer_id: Stripe customer ID.
            return_url: URL to redirect to after the portal session.

        Returns:
            PortalResponse with the portal URL.
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=return_url,
            )

            return PortalResponse(portal_url=session.url)

        except stripe.error.StripeError as e:
            logger.error("Stripe portal error: %s", e)
            raise

    async def handle_webhook_event(self, event: dict[str, Any]) -> None:
        """Process a Stripe webhook event.

        Handles subscription lifecycle events to keep our database in sync
        with Stripe's subscription state.

        Args:
            event: The Stripe webhook event payload.
        """
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})

        logger.info("Processing Stripe event: %s", event_type)

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            await self._handle_payment_failed(data)
        else:
            logger.debug("Ignoring Stripe event: %s", event_type)

    async def _handle_checkout_completed(self, session: dict[str, Any]) -> None:
        """Handle a completed checkout session — activate the subscription."""
        org_id = session.get("metadata", {}).get("org_id")
        plan = session.get("metadata", {}).get("plan")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        if not org_id or not plan:
            logger.warning("Checkout session missing org_id or plan metadata")
            return

        logger.info(
            "Checkout completed: org=%s, plan=%s, customer=%s, subscription=%s",
            org_id, plan, customer_id, subscription_id,
        )

        # TODO: Update database
        # UPDATE subscriptions SET
        #   stripe_customer_id = customer_id,
        #   stripe_subscription_id = subscription_id,
        #   plan = plan,
        #   status = 'active'
        # WHERE org_id = org_id

    async def _handle_subscription_updated(self, subscription: dict[str, Any]) -> None:
        """Handle a subscription update — plan change, renewal, etc."""
        subscription_id = subscription.get("id")
        status = subscription.get("status")
        current_period_start = subscription.get("current_period_start")
        current_period_end = subscription.get("current_period_end")

        logger.info(
            "Subscription updated: %s, status=%s",
            subscription_id, status,
        )

        # TODO: Update database with new status and period dates
        # Also reset scans_used_this_period if period changed

    async def _handle_subscription_deleted(self, subscription: dict[str, Any]) -> None:
        """Handle a subscription cancellation — downgrade to Free."""
        subscription_id = subscription.get("id")

        logger.info("Subscription deleted: %s", subscription_id)

        # TODO: Update database
        # UPDATE subscriptions SET
        #   plan = 'free',
        #   status = 'canceled',
        #   stripe_subscription_id = NULL
        # WHERE stripe_subscription_id = subscription_id

    async def _handle_payment_failed(self, invoice: dict[str, Any]) -> None:
        """Handle a failed payment — mark subscription as past_due."""
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")

        logger.warning(
            "Payment failed for customer %s, subscription %s",
            customer_id, subscription_id,
        )

        # TODO: Update database
        # UPDATE subscriptions SET status = 'past_due'
        # WHERE stripe_subscription_id = subscription_id

    async def check_scan_limit(self, org_id: UUID) -> tuple[bool, Subscription]:
        """Check if an organization can perform a scan.

        Args:
            org_id: Organization UUID.

        Returns:
            Tuple of (can_scan, subscription).
        """
        subscription = await self.get_subscription(org_id)
        return subscription.can_scan, subscription

    async def increment_scan_count(self, org_id: UUID) -> None:
        """Increment the scan counter for an organization.

        Called after a successful scan to track usage against the plan limit.

        Args:
            org_id: Organization UUID.
        """
        # TODO: Update database
        # UPDATE subscriptions SET scans_used_this_period = scans_used_this_period + 1
        # WHERE org_id = org_id
        logger.debug("Incremented scan count for org %s", org_id)
