"""
Terraform Resource to Pricing Dimension Mappings

Maps each supported Terraform resource type to:
1. The cloud provider and service name
2. A function that extracts pricing dimensions from the resource config
3. Default (fallback) monthly cost estimates

This is the "brain" of the pricing engine — it knows which Terraform configuration
fields matter for pricing and how to map them to cloud pricing API parameters.

To add a new resource type:
1. Add an entry to RESOURCE_MAPPINGS
2. Create a dimensions extractor function
3. Set a reasonable default monthly cost
4. Add pricing lookup logic in aws_pricing.py or gcp_pricing.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ResourceMapping:
    """Defines how a Terraform resource type maps to pricing dimensions.

    Attributes:
        provider: Cloud provider (aws, gcp).
        service: Cloud service name (for API lookups).
        description: Human-readable description.
        extract_dimensions: Function to extract pricing dimensions from config.
        default_monthly_cost: Fallback cost estimate in USD.
        confidence: Default confidence level (high, medium, low).
    """
    provider: str
    service: str
    description: str
    extract_dimensions: Callable[[dict[str, Any], str], dict[str, Any]]
    default_monthly_cost: float
    confidence: str = "medium"


# =============================================================================
# Dimension Extractor Functions
# =============================================================================
# Each function takes (config, region) and returns a dict of pricing dimensions.


def _extract_aws_instance_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_instance (EC2)."""
    return {
        "instance_type": config.get("instance_type", "t3.micro"),
        "region": region,
        "operating_system": "Linux",  # Default; AMI-based detection is complex
        "tenancy": config.get("tenancy", "default"),
        "ebs_optimized": config.get("ebs_optimized", False),
    }


def _extract_aws_db_instance_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_db_instance (RDS)."""
    return {
        "instance_class": config.get("instance_class", "db.t3.micro"),
        "engine": config.get("engine", "mysql"),
        "region": region,
        "multi_az": config.get("multi_az", False),
        "allocated_storage": config.get("allocated_storage", 20),
        "storage_type": config.get("storage_type", "gp2"),
    }


def _extract_aws_s3_bucket_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_s3_bucket."""
    return {
        "region": region,
        "storage_class": "STANDARD",  # Default
        "estimated_gb": 100,  # Conservative estimate — can't know actual usage
    }


def _extract_aws_lambda_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_lambda_function."""
    return {
        "region": region,
        "memory_size": config.get("memory_size", 128),
        "estimated_invocations": 1_000_000,  # 1M/month estimate
        "estimated_duration_ms": 200,  # 200ms average
    }


def _extract_aws_lb_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_lb (ALB/NLB)."""
    lb_type = config.get("load_balancer_type", "application")
    return {
        "region": region,
        "lb_type": lb_type,
        "estimated_lcus": 5,  # Load Balancer Capacity Units estimate
    }


def _extract_aws_nat_gateway_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_nat_gateway."""
    return {
        "region": region,
        "estimated_gb_processed": 100,  # 100 GB/month estimate
    }


def _extract_aws_ecs_service_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_ecs_service (Fargate)."""
    return {
        "region": region,
        "cpu": config.get("cpu", 256),  # In CPU units (256 = 0.25 vCPU)
        "memory": config.get("memory", 512),  # In MB
        "desired_count": config.get("desired_count", 1),
    }


def _extract_aws_elasticache_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_elasticache_cluster."""
    return {
        "region": region,
        "node_type": config.get("node_type", "cache.t3.micro"),
        "engine": config.get("engine", "redis"),
        "num_cache_nodes": config.get("num_cache_nodes", 1),
    }


def _extract_aws_dynamodb_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_dynamodb_table."""
    billing_mode = config.get("billing_mode", "PROVISIONED")
    return {
        "region": region,
        "billing_mode": billing_mode,
        "read_capacity": config.get("read_capacity", 5) if billing_mode == "PROVISIONED" else 0,
        "write_capacity": config.get("write_capacity", 5) if billing_mode == "PROVISIONED" else 0,
    }


def _extract_aws_ebs_volume_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_ebs_volume."""
    return {
        "region": region,
        "volume_type": config.get("type", "gp3"),
        "size_gb": config.get("size", 20),
        "iops": config.get("iops", 3000),  # Default for gp3
        "throughput": config.get("throughput", 125),  # Default for gp3 (MB/s)
    }


def _extract_aws_cloudfront_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_cloudfront_distribution."""
    return {
        "price_class": config.get("price_class", "PriceClass_All"),
        "estimated_gb_month": 1000,  # 1TB/month estimate
    }


def _extract_aws_route53_zone_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_route53_zone."""
    return {
        "zone_type": "public" if not config.get("vpc") else "private",
    }


def _extract_aws_sqs_queue_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_sqs_queue."""
    return {
        "region": region,
        "fifo": config.get("fifo_queue", False),
        "estimated_requests_month": 1_000_000,  # 1M/month
    }


def _extract_aws_sns_topic_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_sns_topic."""
    return {
        "region": region,
        "estimated_notifications_month": 100_000,  # 100K/month
    }


def _extract_aws_secretsmanager_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for aws_secretsmanager_secret."""
    return {
        "region": region,
        "estimated_api_calls_month": 10_000,  # 10K/month
    }


# ---------------------------------------------------------------------------
# GCP Resource Dimension Extractors
# ---------------------------------------------------------------------------


def _extract_gcp_compute_instance_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_compute_instance."""
    return {
        "machine_type": config.get("machine_type", "e2-micro"),
        "region": region,
        "preemptible": config.get("scheduling", {}).get("preemptible", False)
                       if isinstance(config.get("scheduling"), dict) else False,
    }


def _extract_gcp_sql_instance_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_sql_database_instance."""
    settings_block = config.get("settings", {}) if isinstance(config.get("settings"), dict) else {}
    return {
        "tier": settings_block.get("tier", "db-f1-micro"),
        "region": region,
        "database_version": config.get("database_version", "MYSQL_8_0"),
        "disk_size": settings_block.get("disk_size", 10),
        "availability_type": settings_block.get("availability_type", "ZONAL"),
    }


def _extract_gcp_storage_bucket_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_storage_bucket."""
    return {
        "region": config.get("location", region),
        "storage_class": config.get("storage_class", "STANDARD"),
        "estimated_gb": 100,
    }


def _extract_gcp_cloud_function_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_cloudfunctions_function."""
    return {
        "region": region,
        "available_memory_mb": config.get("available_memory_mb", 256),
        "estimated_invocations": 1_000_000,
        "estimated_duration_ms": 200,
    }


def _extract_gcp_gke_node_pool_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_container_node_pool."""
    node_config = config.get("node_config", {}) if isinstance(config.get("node_config"), dict) else {}
    return {
        "machine_type": node_config.get("machine_type", "e2-medium"),
        "region": region,
        "node_count": config.get("node_count", config.get("initial_node_count", 1)),
        "preemptible": node_config.get("preemptible", False),
    }


def _extract_gcp_nat_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_compute_router_nat."""
    return {
        "region": region,
        "estimated_gb_processed": 100,
    }


def _extract_gcp_pubsub_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_pubsub_topic."""
    return {
        "region": region,
        "estimated_gb_month": 10,
    }


def _extract_gcp_redis_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_redis_instance."""
    return {
        "region": region,
        "tier": config.get("tier", "BASIC"),
        "memory_size_gb": config.get("memory_size_gb", 1),
    }


def _extract_gcp_compute_disk_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_compute_disk."""
    return {
        "region": region,
        "type": config.get("type", "pd-standard"),
        "size_gb": config.get("size", 10),
    }


def _extract_gcp_compute_address_dims(config: dict[str, Any], region: str) -> dict[str, Any]:
    """Extract pricing dimensions for google_compute_address."""
    return {
        "region": region,
        "address_type": config.get("address_type", "EXTERNAL"),
    }


# =============================================================================
# Resource Mappings Registry
# =============================================================================

RESOURCE_MAPPINGS: dict[str, ResourceMapping] = {
    # -------------------------------------------------------------------------
    # AWS Resources (15 types)
    # -------------------------------------------------------------------------
    "aws_instance": ResourceMapping(
        provider="aws",
        service="AmazonEC2",
        description="EC2 Instance",
        extract_dimensions=_extract_aws_instance_dims,
        default_monthly_cost=30.00,  # t3.micro Linux on-demand
        confidence="high",
    ),
    "aws_db_instance": ResourceMapping(
        provider="aws",
        service="AmazonRDS",
        description="RDS Database Instance",
        extract_dimensions=_extract_aws_db_instance_dims,
        default_monthly_cost=25.00,  # db.t3.micro
        confidence="high",
    ),
    "aws_s3_bucket": ResourceMapping(
        provider="aws",
        service="AmazonS3",
        description="S3 Bucket",
        extract_dimensions=_extract_aws_s3_bucket_dims,
        default_monthly_cost=2.30,  # 100GB standard
        confidence="medium",
    ),
    "aws_lambda_function": ResourceMapping(
        provider="aws",
        service="AWSLambda",
        description="Lambda Function",
        extract_dimensions=_extract_aws_lambda_dims,
        default_monthly_cost=2.00,
        confidence="medium",
    ),
    "aws_lb": ResourceMapping(
        provider="aws",
        service="ElasticLoadBalancing",
        description="Load Balancer (ALB/NLB)",
        extract_dimensions=_extract_aws_lb_dims,
        default_monthly_cost=22.00,  # ALB base cost
        confidence="high",
    ),
    "aws_nat_gateway": ResourceMapping(
        provider="aws",
        service="AmazonEC2",
        description="NAT Gateway",
        extract_dimensions=_extract_aws_nat_gateway_dims,
        default_monthly_cost=36.00,  # $0.045/hr + data processing
        confidence="medium",
    ),
    "aws_ecs_service": ResourceMapping(
        provider="aws",
        service="AmazonECS",
        description="ECS Fargate Service",
        extract_dimensions=_extract_aws_ecs_service_dims,
        default_monthly_cost=36.00,  # 0.25 vCPU + 0.5GB
        confidence="high",
    ),
    "aws_elasticache_cluster": ResourceMapping(
        provider="aws",
        service="AmazonElastiCache",
        description="ElastiCache Cluster",
        extract_dimensions=_extract_aws_elasticache_dims,
        default_monthly_cost=12.50,  # cache.t3.micro
        confidence="high",
    ),
    "aws_dynamodb_table": ResourceMapping(
        provider="aws",
        service="AmazonDynamoDB",
        description="DynamoDB Table",
        extract_dimensions=_extract_aws_dynamodb_dims,
        default_monthly_cost=6.50,  # 5 RCU + 5 WCU provisioned
        confidence="medium",
    ),
    "aws_ebs_volume": ResourceMapping(
        provider="aws",
        service="AmazonEC2",
        description="EBS Volume",
        extract_dimensions=_extract_aws_ebs_volume_dims,
        default_monthly_cost=1.60,  # 20GB gp3
        confidence="high",
    ),
    "aws_cloudfront_distribution": ResourceMapping(
        provider="aws",
        service="AmazonCloudFront",
        description="CloudFront Distribution",
        extract_dimensions=_extract_aws_cloudfront_dims,
        default_monthly_cost=85.00,  # ~1TB/month
        confidence="low",
    ),
    "aws_route53_zone": ResourceMapping(
        provider="aws",
        service="AmazonRoute53",
        description="Route 53 Hosted Zone",
        extract_dimensions=_extract_aws_route53_zone_dims,
        default_monthly_cost=0.50,  # $0.50/zone/month
        confidence="high",
    ),
    "aws_sqs_queue": ResourceMapping(
        provider="aws",
        service="AWSQueueService",
        description="SQS Queue",
        extract_dimensions=_extract_aws_sqs_queue_dims,
        default_monthly_cost=0.40,  # 1M requests
        confidence="low",
    ),
    "aws_sns_topic": ResourceMapping(
        provider="aws",
        service="AmazonSNS",
        description="SNS Topic",
        extract_dimensions=_extract_aws_sns_topic_dims,
        default_monthly_cost=0.50,  # 100K notifications
        confidence="low",
    ),
    "aws_secretsmanager_secret": ResourceMapping(
        provider="aws",
        service="AWSSecretsManager",
        description="Secrets Manager Secret",
        extract_dimensions=_extract_aws_secretsmanager_dims,
        default_monthly_cost=0.40,  # $0.40/secret/month
        confidence="high",
    ),

    # -------------------------------------------------------------------------
    # GCP Resources (10 types)
    # -------------------------------------------------------------------------
    "google_compute_instance": ResourceMapping(
        provider="gcp",
        service="Compute Engine",
        description="Compute Engine VM",
        extract_dimensions=_extract_gcp_compute_instance_dims,
        default_monthly_cost=25.00,  # e2-micro
        confidence="high",
    ),
    "google_sql_database_instance": ResourceMapping(
        provider="gcp",
        service="Cloud SQL",
        description="Cloud SQL Instance",
        extract_dimensions=_extract_gcp_sql_instance_dims,
        default_monthly_cost=9.50,  # db-f1-micro
        confidence="high",
    ),
    "google_storage_bucket": ResourceMapping(
        provider="gcp",
        service="Cloud Storage",
        description="Cloud Storage Bucket",
        extract_dimensions=_extract_gcp_storage_bucket_dims,
        default_monthly_cost=2.60,  # 100GB standard
        confidence="medium",
    ),
    "google_cloudfunctions_function": ResourceMapping(
        provider="gcp",
        service="Cloud Functions",
        description="Cloud Function",
        extract_dimensions=_extract_gcp_cloud_function_dims,
        default_monthly_cost=1.80,
        confidence="medium",
    ),
    "google_container_node_pool": ResourceMapping(
        provider="gcp",
        service="Kubernetes Engine",
        description="GKE Node Pool",
        extract_dimensions=_extract_gcp_gke_node_pool_dims,
        default_monthly_cost=25.00,  # 1x e2-medium
        confidence="high",
    ),
    "google_compute_router_nat": ResourceMapping(
        provider="gcp",
        service="Cloud NAT",
        description="Cloud NAT Gateway",
        extract_dimensions=_extract_gcp_nat_dims,
        default_monthly_cost=32.00,
        confidence="medium",
    ),
    "google_pubsub_topic": ResourceMapping(
        provider="gcp",
        service="Pub/Sub",
        description="Pub/Sub Topic",
        extract_dimensions=_extract_gcp_pubsub_dims,
        default_monthly_cost=0.60,  # 10GB/month
        confidence="low",
    ),
    "google_redis_instance": ResourceMapping(
        provider="gcp",
        service="Memorystore",
        description="Memorystore Redis Instance",
        extract_dimensions=_extract_gcp_redis_dims,
        default_monthly_cost=36.00,  # 1GB Basic tier
        confidence="high",
    ),
    "google_compute_disk": ResourceMapping(
        provider="gcp",
        service="Compute Engine",
        description="Persistent Disk",
        extract_dimensions=_extract_gcp_compute_disk_dims,
        default_monthly_cost=0.40,  # 10GB pd-standard
        confidence="high",
    ),
    "google_compute_address": ResourceMapping(
        provider="gcp",
        service="Compute Engine",
        description="Static IP Address",
        extract_dimensions=_extract_gcp_compute_address_dims,
        default_monthly_cost=7.20,  # Unused external IP ~$0.01/hr
        confidence="high",
    ),
}


def get_resource_mapping(resource_type: str) -> Optional[ResourceMapping]:
    """Get the resource mapping for a Terraform resource type.

    Args:
        resource_type: The Terraform resource type (e.g., "aws_instance").

    Returns:
        The ResourceMapping if supported, or None.
    """
    return RESOURCE_MAPPINGS.get(resource_type)


def get_supported_resource_types() -> list[str]:
    """Get a sorted list of all supported resource types."""
    return sorted(RESOURCE_MAPPINGS.keys())


def is_supported(resource_type: str) -> bool:
    """Check if a resource type is supported by the pricing engine."""
    return resource_type in RESOURCE_MAPPINGS
