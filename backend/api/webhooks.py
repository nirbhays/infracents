"""
Webhook API Endpoints

Handles incoming webhooks from GitHub and Stripe.
These are the primary entry points for the cost estimation pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request

from config import get_settings
from models.github import PullRequestEvent, InstallationEvent
from services.github_service import GitHubService, has_terraform_changes, get_terraform_files
from services.pricing_engine import PricingEngine
from services.cost_calculator import CostCalculator
from services.billing_service import BillingService
from utils.security import verify_github_signature, verify_stripe_signature
from utils.formatting import format_pr_comment, format_scan_limit_comment, format_error_comment

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: str = Header(None, alias="X-GitHub-Delivery"),
) -> dict[str, Any]:
    """Handle incoming GitHub webhook events.

    This is the main entry point for the cost estimation pipeline.
    It processes pull_request events by:
    1. Verifying the webhook signature
    2. Checking if the PR has .tf file changes
    3. Running the cost estimation pipeline
    4. Posting a cost estimate comment on the PR

    Also handles installation events (app installed/uninstalled).
    """
    # Read the raw body for signature verification
    body = await request.body()

    # Step 1: Verify the webhook signature
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Invalid webhook signature",
                "error_code": "INVALID_SIGNATURE",
            },
        )

    # Parse the payload
    payload = json.loads(body)

    # Route to the appropriate handler based on event type
    if x_github_event == "pull_request":
        return await _handle_pull_request(payload, request)
    elif x_github_event == "installation":
        return await _handle_installation(payload)
    elif x_github_event == "ping":
        return {"status": "pong", "zen": payload.get("zen", "")}
    else:
        logger.debug("Ignoring unsupported event: %s", x_github_event)
        return {"status": "ignored", "event": x_github_event}


async def _handle_pull_request(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Handle a pull_request webhook event."""
    event = PullRequestEvent(**payload)

    # Skip events that shouldn't trigger analysis
    if not event.should_process:
        logger.info(
            "Skipping PR #%d action=%s (not processable)",
            event.number, event.action,
        )
        return {"status": "skipped", "reason": f"action_{event.action}"}

    installation_id = event.installation_id
    if not installation_id:
        logger.warning("PR event missing installation_id")
        return {"status": "skipped", "reason": "no_installation_id"}

    repo_name = event.repo_full_name
    pr_number = event.number
    head_sha = event.pull_request.head.sha
    base_sha = event.pull_request.base.sha

    logger.info(
        "Processing PR #%d in %s (action=%s, head=%s)",
        pr_number, repo_name, event.action, head_sha[:8],
    )

    # Initialize services
    github_service = GitHubService()
    cache = getattr(request.app.state, "cache", None)
    pricing_engine = PricingEngine(cache)
    calculator = CostCalculator(github_service, pricing_engine)

    # Step 1: Check for Terraform file changes
    try:
        files = await github_service.get_pr_files(installation_id, repo_name, pr_number)
    except Exception as e:
        logger.error("Failed to fetch PR files: %s", e)
        return {"status": "error", "reason": "failed_to_fetch_files"}

    if not has_terraform_changes(files):
        logger.info("No .tf files changed in PR #%d", pr_number)
        return {"status": "skipped", "reason": "no_terraform_changes"}

    tf_files = get_terraform_files(files)
    logger.info("Found %d Terraform files changed", len(tf_files))

    # Step 2: Run cost estimation
    try:
        estimate = await calculator.analyze_pull_request(
            installation_id=installation_id,
            repo_full_name=repo_name,
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha=base_sha,
        )
    except Exception as e:
        logger.error("Cost estimation failed for PR #%d: %s", pr_number, e)
        # Post an error comment
        error_comment = format_error_comment(str(e))
        try:
            await github_service.create_or_update_comment(
                installation_id, repo_name, pr_number, error_comment
            )
        except Exception:
            pass
        return {"status": "error", "reason": "estimation_failed"}

    # Step 3: Format and post the comment
    comment_body = format_pr_comment(
        estimate=estimate,
        pr_number=pr_number,
        repo_name=repo_name,
    )

    try:
        comment_id = await github_service.create_or_update_comment(
            installation_id, repo_name, pr_number, comment_body
        )
    except Exception as e:
        logger.error("Failed to post comment on PR #%d: %s", pr_number, e)
        comment_id = None

    scan_id = str(uuid4())

    logger.info(
        "PR #%d analysis complete: delta=$%.2f/mo, comment=%s, scan=%s",
        pr_number, estimate.cost_delta, comment_id, scan_id,
    )

    return {
        "status": "processed",
        "scan_id": scan_id,
        "cost_delta": estimate.cost_delta,
        "cost_delta_percent": estimate.cost_delta_percent,
        "resources_analyzed": len(estimate.resources),
        "comment_id": comment_id,
    }


async def _handle_installation(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle a GitHub App installation event."""
    event = InstallationEvent(**payload)

    if event.action == "created":
        logger.info(
            "GitHub App installed by %s (installation_id=%d)",
            event.installation.account.login if event.installation.account else "unknown",
            event.installation.id,
        )
        # TODO: Create organization record in database
        return {"status": "installed", "installation_id": event.installation.id}

    elif event.action == "deleted":
        logger.info(
            "GitHub App uninstalled (installation_id=%d)",
            event.installation.id,
        )
        # TODO: Deactivate organization in database
        return {"status": "uninstalled", "installation_id": event.installation.id}

    return {"status": "ignored", "action": event.action}


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
) -> dict[str, Any]:
    """Handle incoming Stripe webhook events.

    Processes subscription lifecycle events to keep billing state in sync.
    """
    body = await request.body()

    # Verify the webhook signature
    if not verify_stripe_signature(body, stripe_signature):
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Invalid Stripe signature",
                "error_code": "INVALID_SIGNATURE",
            },
        )

    payload = json.loads(body)
    event_type = payload.get("type", "unknown")

    logger.info("Received Stripe event: %s", event_type)

    billing_service = BillingService()
    await billing_service.handle_webhook_event(payload)

    return {"status": "processed", "event_type": event_type}
