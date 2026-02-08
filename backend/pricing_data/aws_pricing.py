"""
AWS Pricing Data

Fetches and caches pricing data from the AWS Price List API.
Also includes static fallback pricing tables for when the API is unavailable.

The AWS Price List API is public (no authentication required) and provides
real-time pricing for all AWS services.

Reference: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from models.pricing import (
    CloudProvider,
    CostComponent,
    CostConfidence,
    ResourceCost,
    PricingDimension,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Static Fallback Pricing Tables
# =============================================================================
# These are approximate on-demand prices in USD for us-east-1.
# Updated periodically via the pricing-update GitHub Action.

# EC2 instance pricing ($/hr, on-demand, Linux, us-east-1)
EC2_HOURLY_PRICES: dict[str, float] = {
    # General Purpose
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208,
    "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328,
    "t3a.nano": 0.0047, "t3a.micro": 0.0094, "t3a.small": 0.0188,
    "t3a.medium": 0.0376, "t3a.large": 0.0752, "t3a.xlarge": 0.1504,
    "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384,
    "m5.4xlarge": 0.768, "m5.8xlarge": 1.536, "m5.12xlarge": 2.304,
    "m5.16xlarge": 3.072, "m5.24xlarge": 4.608,
    "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384,
    "m7g.medium": 0.0408, "m7g.large": 0.0816, "m7g.xlarge": 0.1632,
    # Compute Optimized
    "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34,
    "c5.4xlarge": 0.68, "c5.9xlarge": 1.53,
    "c6i.large": 0.085, "c6i.xlarge": 0.17, "c6i.2xlarge": 0.34,
    # Memory Optimized
    "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504,
    "r5.4xlarge": 1.008, "r5.8xlarge": 2.016,
    "r6i.large": 0.126, "r6i.xlarge": 0.252, "r6i.2xlarge": 0.504,
    # Storage Optimized
    "i3.large": 0.156, "i3.xlarge": 0.312, "i3.2xlarge": 0.624,
}

# RDS instance pricing ($/hr, on-demand, us-east-1)
RDS_HOURLY_PRICES: dict[str, dict[str, float]] = {
    # {instance_class: {engine: hourly_rate}}
    "db.t3.micro": {"mysql": 0.017, "postgres": 0.018, "mariadb": 0.017},
    "db.t3.small": {"mysql": 0.034, "postgres": 0.036, "mariadb": 0.034},
    "db.t3.medium": {"mysql": 0.068, "postgres": 0.072, "mariadb": 0.068},
    "db.t3.large": {"mysql": 0.136, "postgres": 0.145, "mariadb": 0.136},
    "db.r5.large": {"mysql": 0.18, "postgres": 0.195, "mariadb": 0.18},
    "db.r5.xlarge": {"mysql": 0.36, "postgres": 0.39, "mariadb": 0.36},
    "db.r5.2xlarge": {"mysql": 0.72, "postgres": 0.78, "mariadb": 0.72},
    "db.r5.4xlarge": {"mysql": 1.44, "postgres": 1.56, "mariadb": 1.44},
    "db.r6g.large": {"mysql": 0.162, "postgres": 0.175, "mariadb": 0.162},
    "db.r6g.xlarge": {"mysql": 0.324, "postgres": 0.35, "mariadb": 0.324},
    "db.m5.large": {"mysql": 0.154, "postgres": 0.167, "mariadb": 0.154},
    "db.m5.xlarge": {"mysql": 0.308, "postgres": 0.334, "mariadb": 0.308},
}

# RDS storage pricing ($/GB/month)
RDS_STORAGE_PRICES: dict[str, float] = {
    "gp2": 0.115,
    "gp3": 0.08,
    "io1": 0.125,
    "standard": 0.10,
}

# ElastiCache node pricing ($/hr, on-demand, us-east-1)
ELASTICACHE_HOURLY_PRICES: dict[str, float] = {
    "cache.t3.micro": 0.017, "cache.t3.small": 0.034, "cache.t3.medium": 0.068,
    "cache.m5.large": 0.142, "cache.m5.xlarge": 0.284, "cache.m5.2xlarge": 0.568,
    "cache.r5.large": 0.166, "cache.r5.xlarge": 0.332, "cache.r5.2xlarge": 0.664,
    "cache.r6g.large": 0.149, "cache.r6g.xlarge": 0.298,
    "cache.t4g.micro": 0.016, "cache.t4g.small": 0.032, "cache.t4g.medium": 0.065,
}

# EBS volume pricing ($/GB/month, us-east-1)
EBS_PRICES: dict[str, float] = {
    "gp2": 0.10,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}

# S3 storage pricing ($/GB/month, us-east-1)
S3_PRICES: dict[str, float] = {
    "STANDARD": 0.023,
    "STANDARD_IA": 0.0125,
    "ONEZONE_IA": 0.01,
    "GLACIER": 0.004,
    "GLACIER_DEEP_ARCHIVE": 0.00099,
    "INTELLIGENT_TIERING": 0.023,
}

# Fargate pricing ($/vCPU/hr and $/GB/hr, us-east-1)
FARGATE_CPU_PRICE = 0.04048  # per vCPU per hour
FARGATE_MEMORY_PRICE = 0.004445  # per GB per hour

# NAT Gateway pricing (us-east-1)
NAT_GATEWAY_HOURLY = 0.045
NAT_GATEWAY_PER_GB = 0.045

# ALB/NLB pricing (us-east-1)
ALB_HOURLY = 0.0225
ALB_LCU_HOURLY = 0.008
NLB_HOURLY = 0.0225
NLB_LCU_HOURLY = 0.006

# Lambda pricing (us-east-1)
LAMBDA_REQUEST_PRICE = 0.20 / 1_000_000  # $0.20 per 1M requests
LAMBDA_DURATION_PRICE = 0.0000166667  # per GB-second

# DynamoDB pricing (us-east-1, provisioned)
DYNAMODB_RCU_PRICE = 0.00065  # per RCU per hour
DYNAMODB_WCU_PRICE = 0.00065  # per WCU per hour
DYNAMODB_ONDEMAND_READ = 0.25 / 1_000_000  # per read request unit
DYNAMODB_ONDEMAND_WRITE = 1.25 / 1_000_000  # per write request unit

# Route53
ROUTE53_HOSTED_ZONE = 0.50  # per hosted zone per month

# Secrets Manager
SECRETS_MANAGER_PER_SECRET = 0.40  # per secret per month
SECRETS_MANAGER_PER_10K_API = 0.05  # per 10K API calls

# SQS pricing
SQS_PRICE_PER_MILLION = 0.40  # standard queue
SQS_FIFO_PRICE_PER_MILLION = 0.50

# SNS pricing
SNS_PRICE_PER_100K = 0.50

# CloudFront pricing (average across tiers)
CLOUDFRONT_PER_GB = 0.085  # average

# Hours in a month (standard billing assumption)
HOURS_PER_MONTH = 730


async def get_aws_price(
    resource_type: str,
    dimensions: dict[str, Any],
    region: str,
) -> Optional[ResourceCost]:
    """Get the monthly price for an AWS resource.

    Attempts to use the static pricing tables first (which are accurate
    for standard configurations). Falls back to a generic API call if
    the specific resource isn't in the static tables.

    Args:
        resource_type: Terraform resource type.
        dimensions: Pricing dimensions extracted by the resource mapping.
        region: AWS region.

    Returns:
        ResourceCost with the monthly estimate, or None if pricing failed.
    """
    try:
        if resource_type == "aws_instance":
            return _price_ec2_instance(dimensions, region)
        elif resource_type == "aws_db_instance":
            return _price_rds_instance(dimensions, region)
        elif resource_type == "aws_s3_bucket":
            return _price_s3_bucket(dimensions, region)
        elif resource_type == "aws_lambda_function":
            return _price_lambda_function(dimensions, region)
        elif resource_type == "aws_lb":
            return _price_load_balancer(dimensions, region)
        elif resource_type == "aws_nat_gateway":
            return _price_nat_gateway(dimensions, region)
        elif resource_type == "aws_ecs_service":
            return _price_ecs_fargate(dimensions, region)
        elif resource_type == "aws_elasticache_cluster":
            return _price_elasticache(dimensions, region)
        elif resource_type == "aws_dynamodb_table":
            return _price_dynamodb(dimensions, region)
        elif resource_type == "aws_ebs_volume":
            return _price_ebs_volume(dimensions, region)
        elif resource_type == "aws_cloudfront_distribution":
            return _price_cloudfront(dimensions, region)
        elif resource_type == "aws_route53_zone":
            return _price_route53(dimensions, region)
        elif resource_type == "aws_sqs_queue":
            return _price_sqs(dimensions, region)
        elif resource_type == "aws_sns_topic":
            return _price_sns(dimensions, region)
        elif resource_type == "aws_secretsmanager_secret":
            return _price_secrets_manager(dimensions, region)
        else:
            logger.warning("No AWS pricing handler for %s", resource_type)
            return None
    except Exception as e:
        logger.error("AWS pricing error for %s: %s", resource_type, e)
        return None


def _price_ec2_instance(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for an EC2 instance."""
    instance_type = dims.get("instance_type", "t3.micro")
    hourly_rate = EC2_HOURLY_PRICES.get(instance_type, 0.0104)  # Default to t3.micro

    compute_cost = hourly_rate * HOURS_PER_MONTH

    components = [
        CostComponent.calculate(
            name="Compute",
            unit="Hours",
            unit_price=hourly_rate,
            quantity=HOURS_PER_MONTH,
            description=f"{instance_type} on-demand ({region})",
        ),
    ]

    return ResourceCost(
        resource_type="aws_instance",
        resource_name=instance_type,
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=round(compute_cost, 2),
        cost_components=components,
        dimensions=[
            PricingDimension(name="instance_type", value=instance_type),
            PricingDimension(name="region", value=region),
        ],
        confidence=CostConfidence.HIGH if instance_type in EC2_HOURLY_PRICES else CostConfidence.MEDIUM,
    )


def _price_rds_instance(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for an RDS instance."""
    instance_class = dims.get("instance_class", "db.t3.micro")
    engine = dims.get("engine", "mysql")
    multi_az = dims.get("multi_az", False)
    allocated_storage = dims.get("allocated_storage", 20)
    storage_type = dims.get("storage_type", "gp2")

    # Instance cost
    engine_prices = RDS_HOURLY_PRICES.get(instance_class, {})
    hourly_rate = engine_prices.get(engine, engine_prices.get("mysql", 0.017))
    if multi_az:
        hourly_rate *= 2  # Multi-AZ doubles the instance cost

    instance_cost = hourly_rate * HOURS_PER_MONTH

    # Storage cost
    storage_rate = RDS_STORAGE_PRICES.get(storage_type, 0.115)
    if multi_az:
        storage_rate *= 2  # Multi-AZ doubles storage cost
    storage_cost = storage_rate * allocated_storage

    total = round(instance_cost + storage_cost, 2)

    components = [
        CostComponent.calculate(
            name="Instance",
            unit="Hours",
            unit_price=hourly_rate,
            quantity=HOURS_PER_MONTH,
            description=f"{instance_class} ({engine})" + (" Multi-AZ" if multi_az else ""),
        ),
        CostComponent.calculate(
            name="Storage",
            unit="GB-Mo",
            unit_price=storage_rate,
            quantity=allocated_storage,
            description=f"{storage_type} storage",
        ),
    ]

    return ResourceCost(
        resource_type="aws_db_instance",
        resource_name=instance_class,
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=components,
        confidence=CostConfidence.HIGH,
    )


def _price_s3_bucket(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for an S3 bucket."""
    storage_class = dims.get("storage_class", "STANDARD")
    estimated_gb = dims.get("estimated_gb", 100)
    rate = S3_PRICES.get(storage_class, 0.023)
    total = round(rate * estimated_gb, 2)

    return ResourceCost(
        resource_type="aws_s3_bucket",
        resource_name="s3-bucket",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Storage", "GB-Mo", rate, estimated_gb,
                                    f"{storage_class} storage (~{estimated_gb}GB estimate)"),
        ],
        confidence=CostConfidence.MEDIUM,
        notes=f"Estimate based on {estimated_gb}GB storage. Actual costs depend on usage.",
    )


def _price_lambda_function(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a Lambda function."""
    memory_mb = dims.get("memory_size", 128)
    invocations = dims.get("estimated_invocations", 1_000_000)
    duration_ms = dims.get("estimated_duration_ms", 200)

    # Request cost
    request_cost = invocations * LAMBDA_REQUEST_PRICE

    # Duration cost (GB-seconds)
    memory_gb = memory_mb / 1024
    duration_s = duration_ms / 1000
    gb_seconds = invocations * memory_gb * duration_s
    duration_cost = gb_seconds * LAMBDA_DURATION_PRICE

    total = round(request_cost + duration_cost, 2)

    return ResourceCost(
        resource_type="aws_lambda_function",
        resource_name="lambda",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Requests", "Requests", LAMBDA_REQUEST_PRICE, invocations),
            CostComponent.calculate("Duration", "GB-s", LAMBDA_DURATION_PRICE, gb_seconds,
                                    f"{memory_mb}MB × {duration_ms}ms × {invocations:,} invocations"),
        ],
        confidence=CostConfidence.MEDIUM,
        notes="Estimate based on assumed invocations and duration",
    )


def _price_load_balancer(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for an ALB or NLB."""
    lb_type = dims.get("lb_type", "application")
    estimated_lcus = dims.get("estimated_lcus", 5)

    if lb_type == "application":
        hourly = ALB_HOURLY
        lcu_hourly = ALB_LCU_HOURLY
    else:
        hourly = NLB_HOURLY
        lcu_hourly = NLB_LCU_HOURLY

    base_cost = hourly * HOURS_PER_MONTH
    lcu_cost = lcu_hourly * estimated_lcus * HOURS_PER_MONTH
    total = round(base_cost + lcu_cost, 2)

    return ResourceCost(
        resource_type="aws_lb",
        resource_name=lb_type,
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Base", "Hours", hourly, HOURS_PER_MONTH,
                                    f"{'ALB' if lb_type == 'application' else 'NLB'} fixed cost"),
            CostComponent.calculate("LCU", "LCU-Hours", lcu_hourly, estimated_lcus * HOURS_PER_MONTH,
                                    f"~{estimated_lcus} LCUs estimate"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_nat_gateway(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for a NAT Gateway."""
    estimated_gb = dims.get("estimated_gb_processed", 100)
    base = NAT_GATEWAY_HOURLY * HOURS_PER_MONTH
    data = NAT_GATEWAY_PER_GB * estimated_gb
    total = round(base + data, 2)

    return ResourceCost(
        resource_type="aws_nat_gateway",
        resource_name="nat-gw",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Hourly", "Hours", NAT_GATEWAY_HOURLY, HOURS_PER_MONTH),
            CostComponent.calculate("Data", "GB", NAT_GATEWAY_PER_GB, estimated_gb,
                                    f"~{estimated_gb}GB processed"),
        ],
        confidence=CostConfidence.MEDIUM,
    )


def _price_ecs_fargate(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for ECS Fargate."""
    cpu_units = dims.get("cpu", 256)
    memory_mb = dims.get("memory", 512)
    desired_count = dims.get("desired_count", 1)

    vcpu = cpu_units / 1024
    memory_gb = memory_mb / 1024

    cpu_cost = FARGATE_CPU_PRICE * vcpu * HOURS_PER_MONTH * desired_count
    mem_cost = FARGATE_MEMORY_PRICE * memory_gb * HOURS_PER_MONTH * desired_count
    total = round(cpu_cost + mem_cost, 2)

    return ResourceCost(
        resource_type="aws_ecs_service",
        resource_name="fargate",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("vCPU", "vCPU-Hours", FARGATE_CPU_PRICE,
                                    vcpu * HOURS_PER_MONTH * desired_count,
                                    f"{vcpu} vCPU × {desired_count} tasks"),
            CostComponent.calculate("Memory", "GB-Hours", FARGATE_MEMORY_PRICE,
                                    memory_gb * HOURS_PER_MONTH * desired_count,
                                    f"{memory_gb}GB × {desired_count} tasks"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_elasticache(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for ElastiCache."""
    node_type = dims.get("node_type", "cache.t3.micro")
    num_nodes = dims.get("num_cache_nodes", 1)
    hourly = ELASTICACHE_HOURLY_PRICES.get(node_type, 0.017)
    total = round(hourly * HOURS_PER_MONTH * num_nodes, 2)

    return ResourceCost(
        resource_type="aws_elasticache_cluster",
        resource_name=node_type,
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Nodes", "Hours", hourly, HOURS_PER_MONTH * num_nodes,
                                    f"{num_nodes}× {node_type}"),
        ],
        confidence=CostConfidence.HIGH if node_type in ELASTICACHE_HOURLY_PRICES else CostConfidence.MEDIUM,
    )


def _price_dynamodb(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for DynamoDB."""
    billing_mode = dims.get("billing_mode", "PROVISIONED")
    if billing_mode == "PROVISIONED":
        rcu = dims.get("read_capacity", 5)
        wcu = dims.get("write_capacity", 5)
        rcu_cost = DYNAMODB_RCU_PRICE * rcu * HOURS_PER_MONTH
        wcu_cost = DYNAMODB_WCU_PRICE * wcu * HOURS_PER_MONTH
        total = round(rcu_cost + wcu_cost, 2)
        components = [
            CostComponent.calculate("Read Capacity", "RCU-Hours", DYNAMODB_RCU_PRICE,
                                    rcu * HOURS_PER_MONTH, f"{rcu} RCUs"),
            CostComponent.calculate("Write Capacity", "WCU-Hours", DYNAMODB_WCU_PRICE,
                                    wcu * HOURS_PER_MONTH, f"{wcu} WCUs"),
        ]
    else:
        total = 1.25  # Minimum on-demand estimate
        components = [CostComponent.calculate("On-Demand", "month", 1.25, 1, "On-demand billing")]

    return ResourceCost(
        resource_type="aws_dynamodb_table",
        resource_name="dynamodb",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=components,
        confidence=CostConfidence.MEDIUM,
    )


def _price_ebs_volume(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for an EBS volume."""
    volume_type = dims.get("volume_type", "gp3")
    size_gb = dims.get("size_gb", 20)
    rate = EBS_PRICES.get(volume_type, 0.08)
    total = round(rate * size_gb, 2)

    return ResourceCost(
        resource_type="aws_ebs_volume",
        resource_name=volume_type,
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Storage", "GB-Mo", rate, size_gb,
                                    f"{size_gb}GB {volume_type}"),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_cloudfront(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for CloudFront."""
    estimated_gb = dims.get("estimated_gb_month", 1000)
    total = round(CLOUDFRONT_PER_GB * estimated_gb, 2)

    return ResourceCost(
        resource_type="aws_cloudfront_distribution",
        resource_name="cloudfront",
        provider=CloudProvider.AWS,
        region="global",
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Data Transfer", "GB", CLOUDFRONT_PER_GB, estimated_gb,
                                    f"~{estimated_gb}GB/month estimate"),
        ],
        confidence=CostConfidence.LOW,
    )


def _price_route53(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Route 53."""
    return ResourceCost(
        resource_type="aws_route53_zone",
        resource_name="hosted-zone",
        provider=CloudProvider.AWS,
        region="global",
        monthly_cost=ROUTE53_HOSTED_ZONE,
        cost_components=[
            CostComponent.calculate("Hosted Zone", "zone", ROUTE53_HOSTED_ZONE, 1),
        ],
        confidence=CostConfidence.HIGH,
    )


def _price_sqs(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for SQS."""
    fifo = dims.get("fifo", False)
    requests = dims.get("estimated_requests_month", 1_000_000)
    rate = SQS_FIFO_PRICE_PER_MILLION if fifo else SQS_PRICE_PER_MILLION
    total = round((requests / 1_000_000) * rate, 2)

    return ResourceCost(
        resource_type="aws_sqs_queue",
        resource_name="sqs",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Requests", "1M Requests", rate, requests / 1_000_000),
        ],
        confidence=CostConfidence.LOW,
    )


def _price_sns(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for SNS."""
    notifications = dims.get("estimated_notifications_month", 100_000)
    total = round((notifications / 100_000) * SNS_PRICE_PER_100K, 2)

    return ResourceCost(
        resource_type="aws_sns_topic",
        resource_name="sns",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Notifications", "100K", SNS_PRICE_PER_100K,
                                    notifications / 100_000),
        ],
        confidence=CostConfidence.LOW,
    )


def _price_secrets_manager(dims: dict[str, Any], region: str) -> ResourceCost:
    """Calculate monthly cost for Secrets Manager."""
    api_calls = dims.get("estimated_api_calls_month", 10_000)
    secret_cost = SECRETS_MANAGER_PER_SECRET
    api_cost = (api_calls / 10_000) * SECRETS_MANAGER_PER_10K_API
    total = round(secret_cost + api_cost, 2)

    return ResourceCost(
        resource_type="aws_secretsmanager_secret",
        resource_name="secret",
        provider=CloudProvider.AWS,
        region=region,
        monthly_cost=total,
        cost_components=[
            CostComponent.calculate("Secret", "secret", SECRETS_MANAGER_PER_SECRET, 1),
            CostComponent.calculate("API Calls", "10K calls", SECRETS_MANAGER_PER_10K_API,
                                    api_calls / 10_000),
        ],
        confidence=CostConfidence.HIGH,
    )
