"""
Tests for the Cost Calculator Service

Validates the end-to-end cost calculation pipeline:
parsing → pricing → aggregation → result formatting.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.pricing import CostEstimate, ResourceCost, CostConfidence, CloudProvider
from models.terraform import ResourceChange, ResourceAction, TerraformPlan
from services.cost_calculator import CostCalculator


class TestCostCalculator:
    """Test the cost calculator orchestration logic."""

    @pytest.fixture
    def mock_github(self):
        service = AsyncMock()
        service.get_pr_files = AsyncMock(return_value=[
            {"filename": "main.tf", "status": "modified"},
        ])
        service.get_file_content = AsyncMock(return_value='resource "aws_instance" "web" { instance_type = "t3.large" }')
        return service

    @pytest.fixture
    def mock_pricing(self):
        engine = AsyncMock()
        engine.estimate_resource_cost = AsyncMock(return_value=ResourceCost(
            address="aws_instance.web",
            resource_type="aws_instance",
            name="web",
            action=ResourceAction.CREATE,
            monthly_cost=60.0,
            hourly_cost=0.0832,
            provider=CloudProvider.AWS,
            confidence=CostConfidence.HIGH,
            components=[],
        ))
        return engine

    @pytest.fixture
    def calculator(self, mock_github, mock_pricing):
        return CostCalculator(
            github_service=mock_github,
            pricing_engine=mock_pricing,
        )

    @pytest.mark.asyncio
    async def test_analyze_pr_returns_estimate(self, calculator):
        """Basic PR analysis should return a CostEstimate."""
        result = await calculator.analyze_pull_request(
            installation_id=12345,
            repo_full_name="org/repo",
            pr_number=42,
        )
        assert result is not None
        assert isinstance(result, CostEstimate)

    @pytest.mark.asyncio
    async def test_estimate_has_resources(self, calculator):
        """Estimate should contain at least one resource cost."""
        result = await calculator.analyze_pull_request(
            installation_id=12345,
            repo_full_name="org/repo",
            pr_number=42,
        )
        assert len(result.resources) >= 1

    @pytest.mark.asyncio
    async def test_estimate_cost_delta_positive_for_create(self, calculator):
        """Creating resources should show a positive cost delta."""
        result = await calculator.analyze_pull_request(
            installation_id=12345,
            repo_full_name="org/repo",
            pr_number=42,
        )
        assert result.cost_delta >= 0

    @pytest.mark.asyncio
    async def test_no_tf_files_returns_zero_estimate(self, calculator, mock_github):
        """PR with no .tf files should return zero-cost estimate."""
        mock_github.get_pr_files = AsyncMock(return_value=[
            {"filename": "README.md", "status": "modified"},
        ])
        result = await calculator.analyze_pull_request(
            installation_id=12345,
            repo_full_name="org/repo",
            pr_number=42,
        )
        assert result.cost_delta == 0
        assert len(result.resources) == 0

    @pytest.mark.asyncio
    async def test_multiple_resources_summed(self, mock_github, mock_pricing):
        """Multiple resource costs should be summed correctly."""
        costs = [
            ResourceCost(
                address="aws_instance.web",
                resource_type="aws_instance",
                name="web",
                action=ResourceAction.CREATE,
                monthly_cost=60.0,
                hourly_cost=0.0832,
                provider=CloudProvider.AWS,
                confidence=CostConfidence.HIGH,
                components=[],
            ),
            ResourceCost(
                address="aws_db_instance.db",
                resource_type="aws_db_instance",
                name="db",
                action=ResourceAction.CREATE,
                monthly_cost=200.0,
                hourly_cost=0.277,
                provider=CloudProvider.AWS,
                confidence=CostConfidence.MEDIUM,
                components=[],
            ),
        ]
        mock_pricing.estimate_resource_cost = AsyncMock(side_effect=costs)
        mock_github.get_pr_files = AsyncMock(return_value=[
            {"filename": "main.tf", "status": "modified"},
        ])
        mock_github.get_file_content = AsyncMock(return_value='''
resource "aws_instance" "web" { instance_type = "t3.large" }
resource "aws_db_instance" "db" { instance_class = "db.r5.large" }
''')

        calc = CostCalculator(mock_github, mock_pricing)
        result = await calc.analyze_pull_request(12345, "org/repo", 42)
        assert result.cost_delta == pytest.approx(260.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_resource_deletion_reduces_cost(self, mock_github, mock_pricing):
        """Deleting a resource should show a negative cost delta."""
        mock_pricing.estimate_resource_cost = AsyncMock(return_value=ResourceCost(
            address="aws_instance.old",
            resource_type="aws_instance",
            name="old",
            action=ResourceAction.DELETE,
            monthly_cost=-60.0,
            hourly_cost=-0.0832,
            provider=CloudProvider.AWS,
            confidence=CostConfidence.HIGH,
            components=[],
        ))
        calc = CostCalculator(mock_github, mock_pricing)
        result = await calc.analyze_pull_request(12345, "org/repo", 42)
        assert result.cost_delta < 0

    @pytest.mark.asyncio
    async def test_pricing_error_handled_gracefully(self, mock_github, mock_pricing):
        """If pricing engine throws, calculator should handle gracefully."""
        mock_pricing.estimate_resource_cost = AsyncMock(
            side_effect=Exception("Pricing API unavailable")
        )
        calc = CostCalculator(mock_github, mock_pricing)
        # Should not raise — should return estimate with errors noted
        result = await calc.analyze_pull_request(12345, "org/repo", 42)
        assert result is not None

    @pytest.mark.asyncio
    async def test_github_api_error_handled(self, mock_github, mock_pricing):
        """If GitHub API fails, calculator should handle gracefully."""
        mock_github.get_pr_files = AsyncMock(
            side_effect=Exception("GitHub API rate limit")
        )
        calc = CostCalculator(mock_github, mock_pricing)
        with pytest.raises(Exception):
            await calc.analyze_pull_request(12345, "org/repo", 42)
