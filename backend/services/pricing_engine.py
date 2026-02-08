"""
Pricing Engine

The core pricing engine that queries cloud provider pricing APIs and calculates
monthly costs for Terraform resources. Uses a multi-layer pricing strategy:

1. Redis cache (fastest, 1-hour TTL)
2. Cloud provider APIs (authoritative, real-time)
3. Static fallback data (always available, updated weekly)

Supports AWS (Price List API) and GCP (Cloud Billing Catalog).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.pricing import (
    CloudProvider,
    CostComponent,
    CostConfidence,
    CostEstimate,
    ResourceCost,
    PricingDimension,
)
from models.terraform import ResourceAction, ResourceChange, TerraformPlan
from pricing_data.resource_mappings import RESOURCE_MAPPINGS, get_resource_mapping
from pricing_data.aws_pricing import get_aws_price
from pricing_data.gcp_pricing import get_gcp_price
from services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PricingEngine:
    """Main pricing engine that orchestrates cost estimation for Terraform resources.

    The engine follows a cache-first strategy:
    1. Check Redis for a cached price
    2. On miss, query the appropriate cloud API
    3. On API failure, fall back to static pricing data
    4. Cache the result for future lookups

    Usage:
        engine = PricingEngine(cache_service)
        cost = await engine.estimate_resource_cost(resource_change, region)
    """

    def __init__(self, cache: Optional[CacheService] = None):
        """Initialize the pricing engine.

        Args:
            cache: Redis cache service for price caching.
                   If None, caching is disabled (useful for testing).
        """
        self.cache = cache

    async def estimate_plan_cost(self, plan: TerraformPlan) -> CostEstimate:
        """Estimate the total cost for a Terraform plan.

        Processes all resource changes in the plan and aggregates costs into
        a CostEstimate with per-resource breakdown.

        Args:
            plan: The parsed Terraform plan.

        Returns:
            A CostEstimate with total costs and per-resource breakdown.
        """
        resource_costs: list[ResourceCost] = []
        total_before = 0.0
        total_after = 0.0

        for change in plan.resource_changes:
            try:
                # Get the default region from provider config
                from services.terraform_parser import get_default_region
                region = get_default_region(change.provider, plan.provider_configs)

                # Override with resource-specific region if available
                config = change.config
                if "region" in config:
                    region = config["region"]
                elif "availability_zone" in config:
                    # Strip the AZ suffix to get the region
                    region = config["availability_zone"][:-1]

                # Calculate cost based on the action
                if change.action == ResourceAction.CREATE:
                    cost_after = await self.estimate_resource_cost(
                        change.resource_type, config, region, change.provider
                    )
                    resource_costs.append(cost_after)
                    total_after += cost_after.monthly_cost

                elif change.action == ResourceAction.DELETE:
                    cost_before = await self.estimate_resource_cost(
                        change.resource_type, change.previous_config, region, change.provider
                    )
                    # For deletes, we invert: the cost was there before, now it's gone
                    cost_before.monthly_cost = -cost_before.monthly_cost
                    resource_costs.append(cost_before)
                    total_before += abs(cost_before.monthly_cost)

                elif change.action == ResourceAction.UPDATE:
                    cost_before_res = await self.estimate_resource_cost(
                        change.resource_type, change.previous_config, region, change.provider
                    )
                    cost_after_res = await self.estimate_resource_cost(
                        change.resource_type, config, region, change.provider
                    )
                    # Create a delta resource cost
                    delta_cost = ResourceCost(
                        resource_type=change.resource_type,
                        resource_name=change.resource_name,
                        provider=cost_after_res.provider,
                        region=region,
                        monthly_cost=cost_after_res.monthly_cost - cost_before_res.monthly_cost,
                        cost_components=cost_after_res.cost_components,
                        dimensions=cost_after_res.dimensions,
                        confidence=cost_after_res.confidence,
                        is_fallback=cost_after_res.is_fallback,
                        notes=f"Updated from ${cost_before_res.monthly_cost:.2f}/mo to ${cost_after_res.monthly_cost:.2f}/mo",
                    )
                    resource_costs.append(delta_cost)
                    total_before += cost_before_res.monthly_cost
                    total_after += cost_after_res.monthly_cost

                elif change.action == ResourceAction.REPLACE:
                    # Replace = delete old + create new
                    cost_before_res = await self.estimate_resource_cost(
                        change.resource_type, change.previous_config, region, change.provider
                    )
                    cost_after_res = await self.estimate_resource_cost(
                        change.resource_type, config, region, change.provider
                    )
                    delta_cost = ResourceCost(
                        resource_type=change.resource_type,
                        resource_name=change.resource_name,
                        provider=cost_after_res.provider,
                        region=region,
                        monthly_cost=cost_after_res.monthly_cost - cost_before_res.monthly_cost,
                        cost_components=cost_after_res.cost_components,
                        dimensions=cost_after_res.dimensions,
                        confidence=cost_after_res.confidence,
                        is_fallback=cost_after_res.is_fallback,
                        notes="Resource replaced (destroy + create)",
                    )
                    resource_costs.append(delta_cost)
                    total_before += cost_before_res.monthly_cost
                    total_after += cost_after_res.monthly_cost

            except Exception as e:
                logger.error(
                    "Failed to estimate cost for %s.%s: %s",
                    change.resource_type,
                    change.resource_name,
                    e,
                )
                # Add a zero-cost entry with an error note
                resource_costs.append(
                    ResourceCost(
                        resource_type=change.resource_type,
                        resource_name=change.resource_name,
                        provider=CloudProvider(change.provider) if change.provider in ("aws", "gcp") else CloudProvider.AWS,
                        monthly_cost=0.0,
                        confidence=CostConfidence.LOW,
                        notes=f"Cost estimation failed: {e}",
                    )
                )

        return CostEstimate(
            resources=resource_costs,
            total_monthly_cost_before=round(total_before, 2),
            total_monthly_cost_after=round(total_after, 2),
        )

    async def estimate_resource_cost(
        self,
        resource_type: str,
        config: dict[str, Any],
        region: str = "us-east-1",
        provider: str = "aws",
    ) -> ResourceCost:
        """Estimate the monthly cost for a single Terraform resource.

        Uses the cache → API → fallback strategy for price resolution.

        Args:
            resource_type: Terraform resource type (e.g., "aws_instance").
            config: Resource configuration from the Terraform plan.
            region: Cloud region (e.g., "us-east-1").
            provider: Cloud provider name (e.g., "aws", "google").

        Returns:
            A ResourceCost with the monthly cost estimate and breakdown.
        """
        # Get the resource mapping (defines how to extract pricing dimensions)
        mapping = get_resource_mapping(resource_type)
        if not mapping:
            logger.warning("No resource mapping for %s, using default", resource_type)
            return ResourceCost(
                resource_type=resource_type,
                resource_name=config.get("tags", {}).get("Name", resource_type),
                provider=CloudProvider(provider) if provider in ("aws", "gcp") else CloudProvider.AWS,
                region=region,
                monthly_cost=0.0,
                confidence=CostConfidence.LOW,
                notes="Unsupported resource type — no cost estimate available",
            )

        # Extract pricing dimensions from config
        dimensions = mapping.extract_dimensions(config, region)

        # Build cache key
        cache_key = self._build_cache_key(resource_type, dimensions, region)

        # 1. Check cache
        if self.cache:
            cached = await self.cache.get_price(cache_key)
            if cached is not None:
                logger.debug("Cache HIT for %s: $%.2f/mo", resource_type, cached["monthly_cost"])
                return ResourceCost(
                    resource_type=resource_type,
                    resource_name=config.get("tags", {}).get("Name", resource_type.split("_")[-1]),
                    provider=CloudProvider(provider) if provider in ("aws", "gcp") else CloudProvider.AWS,
                    region=region,
                    monthly_cost=cached["monthly_cost"],
                    cost_components=[CostComponent(**c) for c in cached.get("components", [])],
                    dimensions=[PricingDimension(name=k, value=str(v)) for k, v in dimensions.items()],
                    confidence=CostConfidence(cached.get("confidence", "medium")),
                    is_fallback=cached.get("is_fallback", False),
                )

        # 2. Query cloud pricing API
        try:
            if provider == "aws":
                result = await get_aws_price(resource_type, dimensions, region)
            elif provider in ("google", "gcp"):
                result = await get_gcp_price(resource_type, dimensions, region)
            else:
                result = None

            if result:
                # Cache the result
                if self.cache:
                    await self.cache.set_price(cache_key, {
                        "monthly_cost": result.monthly_cost,
                        "components": [c.model_dump() for c in result.cost_components],
                        "confidence": result.confidence.value,
                        "is_fallback": False,
                    })
                return result

        except Exception as e:
            logger.warning(
                "Pricing API failed for %s in %s: %s. Using fallback.",
                resource_type, region, e,
            )

        # 3. Fall back to static pricing data
        fallback_cost = mapping.default_monthly_cost
        logger.info(
            "Using fallback pricing for %s: $%.2f/mo", resource_type, fallback_cost
        )

        resource_cost = ResourceCost(
            resource_type=resource_type,
            resource_name=config.get("tags", {}).get("Name", resource_type.split("_")[-1]),
            provider=CloudProvider(provider) if provider in ("aws", "gcp") else CloudProvider.AWS,
            region=region,
            monthly_cost=fallback_cost,
            cost_components=[
                CostComponent(
                    name="Estimated cost",
                    unit="month",
                    unit_price=fallback_cost,
                    quantity=1,
                    monthly_cost=fallback_cost,
                    description="Fallback estimate (pricing API unavailable)",
                )
            ],
            dimensions=[PricingDimension(name=k, value=str(v)) for k, v in dimensions.items()],
            confidence=CostConfidence.LOW,
            is_fallback=True,
            notes="Using fallback pricing — actual costs may differ",
        )

        # Cache the fallback too (shorter TTL would be ideal, but simplify for now)
        if self.cache:
            await self.cache.set_price(cache_key, {
                "monthly_cost": fallback_cost,
                "components": [c.model_dump() for c in resource_cost.cost_components],
                "confidence": "low",
                "is_fallback": True,
            })

        return resource_cost

    def _build_cache_key(
        self,
        resource_type: str,
        dimensions: dict[str, Any],
        region: str,
    ) -> str:
        """Build a deterministic cache key for a pricing lookup.

        The key includes the resource type, region, and a hash of the
        pricing dimensions to ensure uniqueness.
        """
        # Sort dimensions for deterministic key
        dims_str = "|".join(f"{k}={v}" for k, v in sorted(dimensions.items()))
        return f"price:{resource_type}:{region}:{dims_str}"
