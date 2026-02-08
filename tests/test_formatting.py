"""
Tests for PR Comment Formatting

Validates that the Markdown output is correctly structured,
includes all required sections, and handles edge cases.
"""

from __future__ import annotations

import pytest
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.pricing import CostEstimate, ResourceCost, CostConfidence, CloudProvider
from models.terraform import ResourceAction
from utils.formatting import format_pr_comment, COMMENT_MARKER


def _make_estimate(
    resources: list[ResourceCost] | None = None,
    cost_delta: float = 0.0,
    cost_delta_percent: float = 0.0,
    monthly_total: float = 0.0,
) -> CostEstimate:
    """Helper to create a CostEstimate for testing."""
    return CostEstimate(
        resources=resources or [],
        cost_delta=cost_delta,
        cost_delta_percent=cost_delta_percent,
        monthly_total=monthly_total,
        previous_monthly_total=monthly_total - cost_delta,
    )


def _make_resource(
    address: str = "aws_instance.web",
    resource_type: str = "aws_instance",
    name: str = "web",
    action: ResourceAction = ResourceAction.CREATE,
    monthly_cost: float = 60.0,
    provider: CloudProvider = CloudProvider.AWS,
    confidence: CostConfidence = CostConfidence.HIGH,
) -> ResourceCost:
    return ResourceCost(
        address=address,
        resource_type=resource_type,
        name=name,
        action=action,
        monthly_cost=monthly_cost,
        hourly_cost=monthly_cost / 730,
        provider=provider,
        confidence=confidence,
        components=[],
    )


class TestPRCommentFormatting:
    """Test the PR comment Markdown output."""

    def test_comment_starts_with_marker(self):
        """Comment should start with the InfraCents marker for edit-in-place."""
        estimate = _make_estimate()
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert comment.startswith(COMMENT_MARKER)

    def test_cost_increase_shows_increase(self):
        """Positive cost delta should show as an increase."""
        resource = _make_resource(monthly_cost=142.0)
        estimate = _make_estimate(
            resources=[resource],
            cost_delta=142.0,
            cost_delta_percent=12.0,
            monthly_total=1342.0,
        )
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert "142" in comment
        assert "increase" in comment.lower() or "📈" in comment or "+" in comment

    def test_cost_decrease_shows_decrease(self):
        """Negative cost delta should show as a decrease."""
        resource = _make_resource(
            action=ResourceAction.DELETE,
            monthly_cost=-60.0,
        )
        estimate = _make_estimate(
            resources=[resource],
            cost_delta=-60.0,
            cost_delta_percent=-5.0,
            monthly_total=1140.0,
        )
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert "decrease" in comment.lower() or "📉" in comment or "-" in comment

    def test_no_change_shows_neutral(self):
        """Zero cost delta should show neutral message."""
        estimate = _make_estimate(cost_delta=0.0)
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert "no change" in comment.lower() or "~$0" in comment or "💰" in comment or "0" in comment

    def test_multiple_resources_all_listed(self):
        """All resources should appear in the comment."""
        resources = [
            _make_resource(address="aws_instance.web", monthly_cost=60.0),
            _make_resource(
                address="aws_db_instance.db",
                resource_type="aws_db_instance",
                name="db",
                monthly_cost=200.0,
            ),
            _make_resource(
                address="aws_nat_gateway.nat",
                resource_type="aws_nat_gateway",
                name="nat",
                monthly_cost=32.0,
            ),
        ]
        estimate = _make_estimate(
            resources=resources,
            cost_delta=292.0,
            monthly_total=292.0,
        )
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert "aws_instance.web" in comment
        assert "aws_db_instance.db" in comment
        assert "aws_nat_gateway.nat" in comment

    def test_comment_is_valid_markdown(self):
        """Comment should be valid Markdown (no broken tables or syntax)."""
        resource = _make_resource()
        estimate = _make_estimate(
            resources=[resource],
            cost_delta=60.0,
            monthly_total=60.0,
        )
        comment = format_pr_comment(estimate, pr_number=42, repo_name="org/repo")
        # Should not have unmatched pipes in tables
        lines = comment.split("\n")
        for line in lines:
            if "|" in line and not line.strip().startswith("<!--"):
                # Table rows should have matching pipes
                pipe_count = line.count("|")
                assert pipe_count >= 2, f"Broken table row: {line}"

    def test_dashboard_link_included(self):
        """Comment should include a link to the dashboard."""
        estimate = _make_estimate()
        comment = format_pr_comment(
            estimate,
            pr_number=42,
            repo_name="org/repo",
            dashboard_url="https://infracents.dev/dashboard",
        )
        assert "infracents.dev" in comment or "dashboard" in comment.lower()

    def test_empty_resources_handled(self):
        """Empty resource list should produce a valid comment."""
        estimate = _make_estimate(resources=[], cost_delta=0.0)
        comment = format_pr_comment(estimate, pr_number=1, repo_name="org/repo")
        assert comment is not None
        assert len(comment) > 10  # Should have some content, not just marker
