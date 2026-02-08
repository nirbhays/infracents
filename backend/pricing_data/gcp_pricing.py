"""
GCP Pricing Data

Fetches and caches pricing data from the GCP Cloud Billing Catalog API.
Includes static fallback pricing tables for when the API is unavailable.

Reference: https://cloud.google.com/billing/docs/reference/rest
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.pricing import (
    CloudProvider,
    CostComponent,
    CostConfidence,
    ResourceCost,
    PricingDimension,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Static Fallback Pricing Tables (us-central1 prices in USD)
# =============================================================================

# Compute Engine machine type pricing ($/hr, on-demand, us-central1)
GCE_HOURLY_PRICES: dict[str, float] = {
    # E2 (cost-optimized)
    "e2-micro": 0.00838, "e2-small": 0.01675, "e2-medium": 0.03351,
    "e2-standard-2": 0.06701, "e2-standard-4": 0.13402, "e2-standard-8": 0.26805,
    "e2-standard-16": 0.53609, "e2-standard-32": 1.07219,
    "e2-highmem-2": 0.09040, "e2-highmem-4": 0.18080, "e2-highmem-8": 0.36160,
    "e2-highcpu-2": 0.04955, "e2-highcpu-4": 0.09910, "e2-highcpu-8": 0.19820,
    # N2 (general purpose)
    "n2-standard-2": 0.09710, "n2-standard-4": 0.19421, "n2-standard-8": 0.38841,
    "n2-standard-16": 0.77683, "n2-standard-32": 1.55365,
    "n2-highmem-2": 0.13110, "n2-highmem-4": 0.26220, "n2-highmem-8": 0.52440,
    "n2-highcpu-2": 0.07180, "n2-highcpu-4": 0.14361, "n2-highcpu-8": 0.28722,
    # N1 (legacy)
    "n1-standard-1": 0.04749, "n1-standard-2": 0.09498, "n1-standard-4": 0.18997,
    "n1-standard-8": 0.37993, "n1-standard-16": 0.75987,
    "n1-highmem-2": 0.11834, "n1-highmem-4": 0.23668,
    "n1-highcpu-2": 0.07092, "n1-highcpu-4": 0.14184,
    # Custom (we use n2-standard-2 as proxy)
    "f1-micro": 0.00760, "g1-small": 0.02700,
}

# Cloud SQL pricing ($/hr, us-central1)
CLOUD_SQL_HOURLY_PRICES: dict[str, float] = {
    "db-f1-micro": 0.0105,
    "db-g1-small": 0.0255,
    "db-n1-standard-1": 0.0510,
    "db-n1-standard-2": 0.1020,
    "db-n1-standard-4": 0.2040,
    "db-n1-standard-8": 0.4080,
    "db-n1-standard-16": 0.8160,
    "db-n1-highmem-2": 0.1255,
    "db-n1-highmem-4": 0.2510,
    "db-n1-highmem-8": 0.5020,
    "db-custom-1-3840": 0.0510,
    "db-custom-2-7680": 0.1020,
    "db-custom-4-15360": 0.2040,
}

# Cloud SQL storage pricing ($/GB/month)
CLOUD_SQL_STORAGE_PRICES: dict[str, float] = {
    "PD_SSD": 0.170,
    "PD_HDD": 0.090,
}

# Cloud Storage pricing ($/GB/month, us-central1)
GCS_PRICES: dict[str, float] = {
    "STANDARD": 0.026,
    "NEARLINE": 0.010,
    "COLDLINE": 0.007,
    "ARCHIVE": 0.004,
}

# Memorystore Redis pricing ($/GB/hour, us-central1)
MEMORYSTORE_HOURLY_PRICES: dict[str, float] = {
    "BASIC": 0.049,    # per GB per hour
    "STANDARD_HA": 0.078,  # per GB per hour (with replica)
}

# Persistent Disk pricing ($/GB/month)
PD_PRICES: dict[str, float] = {
    "pd-standard": 0.040,
    "pd-ssd": 0.170,
    "pd-balanced": 0.100,
    "pd-extreme": 0.125,
}

# Cloud Functions pricing (us-central1)
GCF_INVOKE_PRICE = 0.40 / 1_000_000  # per invocation
GCF_COMPUTE_PRICE = 0.0000025  # per GHz-second
GCF_MEMORY_PRICE = 0.0000025  # per GB-second

# Cloud NAT pricing
CLOUD_NAT_HOURLY = 0.0440  # per gateway per hour
CLOUD_NAT_PER_GB = 0.045  # per GB processed

# Pub/Sub pricing
PUBSUB_PER_TB = 40.00  # per TB of messages

# Static IP pricing
STATIC_IP_UNUSED_HOURLY = 0.010  # per unused hour
STATIC_IP_USED_HOURLY = 0.004  # per used hour (first 5 addresses free)

# GKE pricing (management fee)
GKE_MANAGEMENT_FEE = 0.10  # per cluster per hour

# Hours per month
HOURS_PER_MONTH = 730


async def get_gcp_price(
    resource_type: str,
    dimensions: dict[str, Any],
    region: str,
) -> Optional[ResourceCost]:
    """Get the monthly price for a GCP resource.

    Uses static pricing tables for reliable, fast estimates.

    Args:
        resource_type: Terraform resource type.
        dimensions: Pricing dimensions from the resource mapping.
        region: GCP region.

    Returns:
        ResourceCost with the monthly estimate, or None if pricing failed.
    """
    try:
        if resource_type == "google_compute_instance":
            return _price_compute_instance(dimensions, region)
        elif resource_type == "google_sql_database_instance":
            return _price_cloud_sql(dimensions, region)
        elif resource_type == "google_storage_bucket":
            return _price_cloud_storage(dimensions, region)
        elif resource_type == "google_cloudfunctions_function":
            return _price_cloud_functions(dimensions, region)
        elif resource_type == "google_container_node_pool":
            return _price_gke_node_pool(dimensions, region)
        elif resource_type == "google_compute_router_nat":
            return _price_cloud_nat(dimensions, region)
        elif resource_type == "google_pubsub_topic":
            return _price_pubsub(dimensions, region)
        elif resource_type == "google_redis_instance":
            return _price_memorystore(dimensions, region)
        elif resource_type == "google_compute_disk":
            return _price_persistent_disk(dimensions, region)
        elif resource_type == "google_compute_address":
            return _price_static_ip(dimensions, region)
        else:
            logger.warning("No GCP pricing handler for %s", resource_type)
            return None
    except Exception as e:
        logger.error("GCP pricing error for %s: %s", resource_type, e)
        return None


def _price_compute_instance(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a Compute Engine instance."""
    machine_type = dims.get("machine_type", "e2-micro")
    preemptible = dims.get("preemptible", False)

    hourly = GCE_HOURLY_PRICES.get(machine_type, 0.03351)  # Default to e2-medium
    if preemptible:
        hourly *= 0.2  # Preemptible is ~80% cheaper

    total = round(hourly * HOURS_PER_MONTH, 2)

    return ResourceCost(
        resource_type="google_compute_instance",
        resource_name=machine_type,
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate(
                "Compute", "Hours", hourly, HOURS_PER_MONTH,
                f"{machine_type}" + (" (preemptible)" if preemptible else ""),
            ),
        ],
        dimensions=[
            PricingDimension(name="machine_type", value=machine_type),
            PricingDimension(name="region", value=region),
        ],
        confidence=CostConfidence.HIGH if machine_type in GCE_HOURLY_PRICES else CostConfidence.MEDIUM,
    )


def _price_cloud_sql(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a Cloud SQL instance."""
    tier = dims.get("tier", "db-f1-micro")
    disk_size = dims.get("disk_size", 10)
    availability = dims.get("availability_type", "ZONAL")

    hourly = CLOUD_SQL_HOURLY_PRICES.get(tier, 0.0105)
    if availability == "REGIONAL":
        hourly *= 2  # HA doubles the cost

    instance_cost = hourly * HOURS_PER_MONTH
    storage_cost = CLOUD_SQL_STORAGE_PRICES["PD_SSD"] * disk_size
    total = round(instance_cost + storage_cost, 2)

    return ResourceCost(
        resource_type="google_sql_database_instance",
        resource_name=tier,
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Instance", "Hours", hourly, HOURS_PER_MONTH,
                                    f"{tier}" + (" HA" if availability == "REGIONAL" else "")),
            CostComponent.calculate("Storage", "GB-Mo", CLOUD_SQL_STORAGE_PRICES["PD_SSD"],
                                    disk_size, f"{disk_size}GB SSD"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_cloud_storage(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Cloud Storage."""
    storage_class = dims.get("storage_class", "STANDARD")
    estimated_gb = dims.get("estimated_gb", 100)
    rate = GCS_PRICES.get(storage_class, 0.026)
    total = round(rate * estimated_gb, 2)

    return ResourceCost(
        resource_type="google_storage_bucket",
        resource_name="gcs-bucket",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Storage", "GB-Mo", rate, estimated_gb,
                                    f"{storage_class} (~{estimated_gb}GB estimate)"),
        ],
        confidence=CostConfidence.MEDIUM,
    )


def _price_cloud_functions(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Cloud Functions."""
    memory_mb = dims.get("available_memory_mb", 256)
    invocations = dims.get("estimated_invocations", 1_000_000)
    duration_ms = dims.get("estimated_duration_ms", 200)

    invoke_cost = invocations * GCF_INVOKE_PRICE
    memory_gb = memory_mb / 1024
    duration_s = duration_ms / 1000
    gb_seconds = invocations * memory_gb * duration_s
    compute_cost = gb_seconds * GCF_MEMORY_PRICE
    total = round(invoke_cost + compute_cost, 2)

    return ResourceCost(
        resource_type="google_cloudfunctions_function",
        resource_name="cloud-function",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Invocations", "Invocations", GCF_INVOKE_PRICE, invocations),
            CostComponent.calculate("Compute", "GB-s", GCF_MEMORY_PRICE, gb_seconds,
                                    f"{memory_mb}MB × {duration_ms}ms"),
        ],
        confidence=CostConfidence.MEDIUM,
    )


def _price_gke_node_pool(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a GKE node pool."""
    machine_type = dims.get("machine_type", "e2-medium")
    node_count = dims.get("node_count", 1)
    preemptible = dims.get("preemptible", False)

    hourly = GCE_HOURLY_PRICES.get(machine_type, 0.03351)
    if preemptible:
        hourly *= 0.2

    # GKE management fee (free for Autopilot/first cluster)
    management_cost = GKE_MANAGEMENT_FEE * HOURS_PER_MONTH
    node_cost = hourly * HOURS_PER_MONTH * node_count
    total = round(management_cost + node_cost, 2)

    return ResourceCost(
        resource_type="google_container_node_pool",
        resource_name=f"gke-{machine_type}",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("GKE Management", "Hours", GKE_MANAGEMENT_FEE,
                                    HOURS_PER_MONTH, "Cluster management fee"),
            CostComponent.calculate("Nodes", "Hours", hourly,
                                    HOURS_PER_MONTH * node_count,
                                    f"{node_count}× {machine_type}"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_cloud_nat(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Cloud NAT."""
    estimated_gb = dims.get("estimated_gb_processed", 100)
    base = CLOUD_NAT_HOURLY * HOURS_PER_MONTH
    data = CLOUD_NAT_PER_GB * estimated_gb
    total = round(base + data, 2)

    return ResourceCost(
        resource_type="google_compute_router_nat",
        resource_name="cloud-nat",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Gateway", "Hours", CLOUD_NAT_HOURLY, HOURS_PER_MONTH),
            CostComponent.calculate("Data", "GB", CLOUD_NAT_PER_GB, estimated_gb),
        ],
        confidence=CostConfidence.MEDIUM,
    )


def _price_pubsub(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Pub/Sub."""
    estimated_gb = dims.get("estimated_gb_month", 10)
    total = round((estimated_gb / 1024) * PUBSUB_PER_TB, 2)
    # Minimum cost if very small
    total = max(total, 0.01)

    return ResourceCost(
        resource_type="google_pubsub_topic",
        resource_name="pubsub",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Messages", "GB", PUBSUB_PER_TB / 1024, estimated_gb),
        ],
        confidence=CostConfidence.LOW,
    )


def _price_memorystore(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Memorystore Redis."""
    tier = dims.get("tier", "BASIC")
    memory_gb = dims.get("memory_size_gb", 1)

    tier_key = "STANDARD_HA" if tier != "BASIC" else "BASIC"
    hourly_per_gb = MEMORYSTORE_HOURLY_PRICES.get(tier_key, 0.049)
    total = round(hourly_per_gb * memory_gb * HOURS_PER_MONTH, 2)

    return ResourceCost(
        resource_type="google_redis_instance",
        resource_name="memorystore",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Redis", "GB-Hours", hourly_per_gb,
                                    memory_gb * HOURS_PER_MONTH,
                                    f"{memory_gb}GB {tier}"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_persistent_disk(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a Persistent Disk."""
    disk_type = dims.get("type", "pd-standard")
    size_gb = dims.get("size_gb", 10)
    rate = PD_PRICES.get(disk_type, 0.040)
    total = round(rate * size_gb, 2)

    return ResourceCost(
        resource_type="google_compute_disk",
        resource_name=disk_type,
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Storage", "GB-Mo", rate, size_gb,
                                    f"{size_gb}GB {disk_type}"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_static_ip(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a static IP address."""
    address_type = dims.get("address_type", "EXTERNAL")

    if address_type == "INTERNAL":
        total = 0.0
        note = "Internal IPs are free"
    else:
        # Assume unused (worst case); used IPs may be cheaper or free
        total = round(STATIC_IP_UNUSED_HOURLY * HOURS_PER_MONTH, 2)
        note = "External IP (charged when unused; may be free when in use)"

    return ResourceCost(
        resource_type="google_compute_address",
        resource_name="static-ip",
        provider=CloudProvider.GCP,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("IP Address", "Hours",
                                    STATIC_IP_UNUSED_HOURLY if address_type == "EXTERNAL" else 0,
                                    HOURS_PER_MONTH, note),
        ],
        confidence=CostConfidence.HIGH,
        notes=note,
    )
