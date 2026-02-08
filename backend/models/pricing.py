"""
Pricing Data Models

Pydantic models for pricing lookups, cost estimates, and the pricing engine's
internal data structures.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CostConfidence(str, Enum):
    """Confidence level for a cost estimate.

    - HIGH: ±10% accuracy (fixed pricing, well-known dimensions)
    - MEDIUM: ±30% accuracy (some usage-dependent components)
    - LOW: ±50% accuracy (heavily usage-dependent pricing)
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"  # Future support


class PricingDimension(BaseModel):
    """A single dimension that affects pricing (e.g., instance type, region).

    Each cloud resource's price is determined by a combination of dimensions.
    """
    name: str = Field(..., description="Dimension name (e.g., 'instance_type')")
    value: str = Field(..., description="Dimension value (e.g., 't3.large')")
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description",
    )


class CostComponent(BaseModel):
    """A single cost component within a resource estimate.

    A resource may have multiple cost components (e.g., compute + storage + data transfer).
    """
    name: str = Field(..., description="Component name (e.g., 'Compute', 'Storage')")
    unit: str = Field(..., description="Pricing unit (e.g., 'Hrs', 'GB-Mo', 'Requests')")
    unit_price: float = Field(..., description="Price per unit in USD")
    quantity: float = Field(..., description="Estimated monthly quantity")
    monthly_cost: float = Field(..., description="Monthly cost (unit_price × quantity)")
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this cost component",
    )

    @classmethod
    def calculate(
        cls,
        name: str,
        unit: str,
        unit_price: float,
        quantity: float,
        description: Optional[str] = None,
    ) -> CostComponent:
        """Create a CostComponent with auto-calculated monthly cost."""
        return cls(
            name=name,
            unit=unit,
            unit_price=unit_price,
            quantity=quantity,
            monthly_cost=round(unit_price * quantity, 4),
            description=description,
        )


class ResourceCost(BaseModel):
    """Complete cost estimate for a single cloud resource.

    Includes the breakdown by cost component, confidence level, and
    the pricing dimensions used for the lookup.
    """
    resource_type: str = Field(..., description="Terraform resource type")
    resource_name: str = Field(..., description="Resource name")
    provider: CloudProvider = Field(..., description="Cloud provider")
    region: str = Field(default="us-east-1", description="Cloud region")
    monthly_cost: float = Field(..., description="Total monthly cost in USD")
    cost_components: list[CostComponent] = Field(
        default_factory=list,
        description="Breakdown of cost components",
    )
    dimensions: list[PricingDimension] = Field(
        default_factory=list,
        description="Pricing dimensions used for lookup",
    )
    confidence: CostConfidence = Field(
        default=CostConfidence.MEDIUM,
        description="Confidence level of the estimate",
    )
    is_fallback: bool = Field(
        default=False,
        description="Whether fallback (static) pricing was used",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about the estimate",
    )

    @property
    def formatted_cost(self) -> str:
        """Format the monthly cost as a human-readable string."""
        if self.monthly_cost >= 1000:
            return f"${self.monthly_cost:,.0f}/mo"
        elif self.monthly_cost >= 1:
            return f"${self.monthly_cost:,.2f}/mo"
        else:
            return f"${self.monthly_cost:,.4f}/mo"


class CostEstimate(BaseModel):
    """Aggregate cost estimate for an entire Terraform plan.

    Contains per-resource costs, totals, and the delta (change) calculation.
    """
    # Per-resource breakdown
    resources: list[ResourceCost] = Field(
        default_factory=list,
        description="Cost estimates for each resource",
    )

    # Totals
    total_monthly_cost_before: float = Field(
        default=0.0,
        description="Total monthly cost before the change",
    )
    total_monthly_cost_after: float = Field(
        default=0.0,
        description="Total monthly cost after the change",
    )

    @property
    def cost_delta(self) -> float:
        """Calculate the cost change (positive = increase, negative = decrease)."""
        return round(self.total_monthly_cost_after - self.total_monthly_cost_before, 2)

    @property
    def cost_delta_percent(self) -> float:
        """Calculate the percentage change. Returns 0 if there was no previous cost."""
        if self.total_monthly_cost_before == 0:
            return 100.0 if self.total_monthly_cost_after > 0 else 0.0
        return round(
            (self.cost_delta / self.total_monthly_cost_before) * 100, 1
        )

    @property
    def is_increase(self) -> bool:
        """Check if this change increases costs."""
        return self.cost_delta > 0

    @property
    def is_decrease(self) -> bool:
        """Check if this change decreases costs."""
        return self.cost_delta < 0

    @property
    def resources_by_provider(self) -> dict[str, list[ResourceCost]]:
        """Group resources by cloud provider."""
        result: dict[str, list[ResourceCost]] = {}
        for resource in self.resources:
            provider = resource.provider.value
            if provider not in result:
                result[provider] = []
            result[provider].append(resource)
        return result

    @property
    def cost_by_provider(self) -> dict[str, float]:
        """Calculate total cost per provider."""
        result: dict[str, float] = {}
        for resource in self.resources:
            provider = resource.provider.value
            result[provider] = result.get(provider, 0) + resource.monthly_cost
        return result


class PricingAPIResponse(BaseModel):
    """Raw response from a cloud pricing API (before processing)."""
    provider: CloudProvider
    service: str
    products: list[dict[str, Any]] = Field(default_factory=list)
    next_token: Optional[str] = None
    cached: bool = False


class PricingCacheEntry(BaseModel):
    """A cached pricing lookup result."""
    cache_key: str
    provider: CloudProvider
    resource_type: str
    monthly_cost: float
    cost_components: list[CostComponent]
    confidence: CostConfidence
    cached_at: str  # ISO 8601 timestamp
    ttl_seconds: int
