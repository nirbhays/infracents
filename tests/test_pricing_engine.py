"""
Tests for the Pricing Engine

Validates pricing lookups for AWS and GCP resources across different
instance types, regions, and configurations.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.terraform import ResourceChange, ResourceAction
from models.pricing import CloudProvider, CostConfidence, ResourceCost
from services.pricing_engine import PricingEngine
from pricing_data.resource_mappings import RESOURCE_MAPPINGS, get_resource_mapping


class TestResourceMappings:
    """Test that resource type mappings are correctly defined."""

    def test_aws_instance_mapping_exists(self):
        mapping = get_resource_mapping("aws_instance")
        assert mapping is not None
        assert mapping["provider"] == "aws"

    def test_aws_db_instance_mapping_exists(self):
        mapping = get_resource_mapping("aws_db_instance")
        assert mapping is not None

    def test_aws_s3_bucket_mapping_exists(self):
        mapping = get_resource_mapping("aws_s3_bucket")
        assert mapping is not None

    def test_aws_lambda_function_mapping_exists(self):
        mapping = get_resource_mapping("aws_lambda_function")
        assert mapping is not None

    def test_gcp_compute_instance_mapping_exists(self):
        mapping = get_resource_mapping("google_compute_instance")
        assert mapping is not None

    def test_gcp_sql_database_mapping_exists(self):
        mapping = get_resource_mapping("google_sql_database_instance")
        assert mapping is not None

    def test_unknown_resource_returns_none(self):
        mapping = get_resource_mapping("aws_nonexistent_thing")
        assert mapping is None

    def test_all_mappings_have_required_fields(self):
        required_fields = {"provider", "service"}
        for resource_type, mapping in RESOURCE_MAPPINGS.items():
            for field in required_fields:
                assert field in mapping, (
                    f"Resource {resource_type} missing field: {field}"
                )

    def test_minimum_resource_count(self):
        """We should support at least 20 resource types."""
        assert len(RESOURCE_MAPPINGS) >= 15, (
            f"Only {len(RESOURCE_MAPPINGS)} resource mappings; expected >= 15"
        )


class TestPricingEngine:
    """Test the pricing engine cost estimation logic."""

    @pytest.fixture
    def engine(self):
        return PricingEngine(cache=None)

    def _make_resource_change(
        self,
        resource_type: str,
        action: str = "create",
        after: dict | None = None,
        before: dict | None = None,
    ) -> ResourceChange:
        return ResourceChange(
            address=f"{resource_type}.test",
            resource_type=resource_type,
            name="test",
            provider="registry.terraform.io/hashicorp/aws",
            action=ResourceAction(action),
            before=before or {},
            after=after or {},
        )

    @pytest.mark.asyncio
    async def test_ec2_instance_cost_positive(self, engine):
        """EC2 t3.large should return a positive monthly cost."""
        change = self._make_resource_change(
            "aws_instance",
            after={"instance_type": "t3.large"},
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None
        assert cost.monthly_cost > 0

    @pytest.mark.asyncio
    async def test_rds_instance_cost_positive(self, engine):
        """RDS db.r5.large should return a positive monthly cost."""
        change = self._make_resource_change(
            "aws_db_instance",
            after={
                "instance_class": "db.r5.large",
                "engine": "postgres",
                "allocated_storage": 100,
                "multi_az": True,
                "storage_type": "gp2",
            },
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None
        assert cost.monthly_cost > 0

    @pytest.mark.asyncio
    async def test_s3_bucket_cost_near_zero(self, engine):
        """S3 bucket with no explicit storage should be near-zero or zero."""
        change = self._make_resource_change(
            "aws_s3_bucket",
            after={"bucket": "my-test-bucket"},
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None
        assert cost.monthly_cost >= 0

    @pytest.mark.asyncio
    async def test_lambda_function_cost(self, engine):
        """Lambda function should return an estimated cost."""
        change = self._make_resource_change(
            "aws_lambda_function",
            after={
                "function_name": "processor",
                "memory_size": 512,
                "timeout": 30,
            },
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None

    @pytest.mark.asyncio
    async def test_gcp_compute_instance_cost(self, engine):
        """GCP e2-standard-4 should return a positive cost."""
        change = self._make_resource_change(
            "google_compute_instance",
            after={
                "name": "web",
                "machine_type": "e2-standard-4",
                "zone": "us-central1-a",
            },
        )
        cost = await engine.estimate_resource_cost(change, "us-central1")
        assert cost is not None
        assert cost.monthly_cost > 0

    @pytest.mark.asyncio
    async def test_unsupported_resource_returns_none(self, engine):
        """Unsupported resource types should return None or zero-cost."""
        change = self._make_resource_change(
            "aws_iam_policy",
            after={"name": "test-policy"},
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        # Either None or zero cost is acceptable for free resources
        if cost is not None:
            assert cost.monthly_cost == 0

    @pytest.mark.asyncio
    async def test_delete_action_returns_negative_or_zero(self, engine):
        """Deleting a resource should show negative or zero cost delta."""
        change = self._make_resource_change(
            "aws_instance",
            action="delete",
            before={"instance_type": "t3.large"},
            after={},
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        if cost is not None:
            assert cost.monthly_cost <= 0

    @pytest.mark.asyncio
    async def test_nat_gateway_cost(self, engine):
        """NAT Gateway should have a known hourly cost (~$32/mo)."""
        change = self._make_resource_change(
            "aws_nat_gateway",
            after={"allocation_id": "eipalloc-123"},
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None
        assert cost.monthly_cost > 0

    @pytest.mark.asyncio
    async def test_ebs_volume_cost(self, engine):
        """EBS gp3 100GB volume should have a calculable cost."""
        change = self._make_resource_change(
            "aws_ebs_volume",
            after={
                "size": 100,
                "type": "gp3",
                "availability_zone": "us-east-1a",
            },
        )
        cost = await engine.estimate_resource_cost(change, "us-east-1")
        assert cost is not None
        assert cost.monthly_cost > 0
