"""
Terraform Plan Parser

Parses Terraform plan JSON output (`terraform show -json tfplan`) and extracts
resource changes for cost estimation. Also supports parsing raw .tf files
to extract resource definitions when a full plan isn't available.

The parser handles:
- Standard Terraform plan JSON format (v4)
- Resource create/update/delete/replace actions
- Module-nested resources
- Count and for_each meta-arguments
- Provider alias detection
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from models.terraform import (
    ParsedResourceConfig,
    ResourceAction,
    ResourceChange,
    TerraformFileChange,
    TerraformPlan,
)

logger = logging.getLogger(__name__)

# Terraform resource types we can estimate costs for
SUPPORTED_RESOURCE_TYPES: set[str] = {
    # AWS resources
    "aws_instance",
    "aws_db_instance",
    "aws_s3_bucket",
    "aws_lambda_function",
    "aws_lb",
    "aws_nat_gateway",
    "aws_ecs_service",
    "aws_elasticache_cluster",
    "aws_dynamodb_table",
    "aws_ebs_volume",
    "aws_cloudfront_distribution",
    "aws_route53_zone",
    "aws_sqs_queue",
    "aws_sns_topic",
    "aws_secretsmanager_secret",
    # GCP resources
    "google_compute_instance",
    "google_sql_database_instance",
    "google_storage_bucket",
    "google_cloudfunctions_function",
    "google_container_node_pool",
    "google_compute_router_nat",
    "google_pubsub_topic",
    "google_redis_instance",
    "google_compute_disk",
    "google_compute_address",
}


def parse_plan_json(plan_json: dict[str, Any]) -> TerraformPlan:
    """Parse a Terraform plan JSON output into a structured TerraformPlan.

    This is the primary entry point for the parser. It handles the standard
    `terraform show -json` output format.

    Args:
        plan_json: The parsed JSON from `terraform show -json tfplan`

    Returns:
        A TerraformPlan with all resource changes extracted.

    Example:
        >>> with open("tfplan.json") as f:
        ...     plan_data = json.load(f)
        >>> plan = parse_plan_json(plan_data)
        >>> print(f"Found {len(plan.resource_changes)} resource changes")
    """
    resource_changes: list[ResourceChange] = []

    # Extract format version and terraform version
    format_version = plan_json.get("format_version", "1.0")
    terraform_version = plan_json.get("terraform_version")

    # Extract provider configurations for default region detection
    provider_configs = _extract_provider_configs(plan_json)

    # Parse resource changes from the plan
    raw_changes = plan_json.get("resource_changes", [])

    for raw_change in raw_changes:
        try:
            change = _parse_resource_change(raw_change)
            if change and change.resource_type in SUPPORTED_RESOURCE_TYPES:
                resource_changes.append(change)
            elif change:
                logger.debug(
                    "Skipping unsupported resource type: %s", change.resource_type
                )
        except Exception as e:
            logger.warning(
                "Failed to parse resource change: %s — %s",
                raw_change.get("address", "unknown"),
                e,
            )

    plan = TerraformPlan(
        format_version=format_version,
        terraform_version=terraform_version,
        resource_changes=resource_changes,
        provider_configs=provider_configs,
    )

    logger.info(
        "Parsed Terraform plan: %d resource changes (%d creates, %d updates, %d deletes)",
        len(plan.resource_changes),
        len(plan.creates),
        len(plan.updates),
        len(plan.deletes),
    )

    return plan


def _parse_resource_change(raw: dict[str, Any]) -> Optional[ResourceChange]:
    """Parse a single resource change from the plan JSON.

    Args:
        raw: Raw resource_change entry from the plan JSON.

    Returns:
        A ResourceChange, or None if the change should be skipped.
    """
    address = raw.get("address", "")
    resource_type = raw.get("type", "")
    name = raw.get("name", "")
    provider_name = raw.get("provider_name", "")

    # Extract the change block
    change = raw.get("change", {})
    actions = change.get("actions", [])

    # Determine the action
    action = _determine_action(actions)
    if action is None or action == ResourceAction.NO_OP or action == ResourceAction.READ:
        return None  # Skip no-op and read actions

    # Extract before/after configurations
    before = change.get("before")
    after = change.get("after")

    # Determine the provider from the resource type prefix
    provider = _extract_provider(resource_type, provider_name)

    # Check for module address
    module_address = raw.get("module_address")

    return ResourceChange(
        address=address,
        resource_type=resource_type,
        resource_name=name,
        provider=provider,
        action=action,
        before=before,
        after=after,
        module_address=module_address,
    )


def _determine_action(actions: list[str]) -> Optional[ResourceAction]:
    """Map Terraform plan actions to our ResourceAction enum.

    Terraform uses a list of actions:
    - ["create"] → CREATE
    - ["update"] → UPDATE
    - ["delete"] → DELETE
    - ["delete", "create"] or ["create", "delete"] → REPLACE
    - ["read"] → READ
    - ["no-op"] → NO_OP
    """
    if not actions:
        return None

    actions_set = set(actions)

    if actions_set == {"create"}:
        return ResourceAction.CREATE
    elif actions_set == {"update"}:
        return ResourceAction.UPDATE
    elif actions_set == {"delete"}:
        return ResourceAction.DELETE
    elif "delete" in actions_set and "create" in actions_set:
        return ResourceAction.REPLACE
    elif actions_set == {"read"}:
        return ResourceAction.READ
    elif actions_set == {"no-op"}:
        return ResourceAction.NO_OP
    else:
        logger.warning("Unknown action set: %s", actions)
        return None


def _extract_provider(resource_type: str, provider_name: str) -> str:
    """Extract the cloud provider name from resource type or provider field.

    Args:
        resource_type: The Terraform resource type (e.g., "aws_instance").
        provider_name: The provider name from the plan (e.g., "registry.terraform.io/hashicorp/aws").

    Returns:
        The provider name (e.g., "aws", "google").
    """
    # Try to get from provider_name first (more reliable)
    if provider_name:
        # Format: registry.terraform.io/hashicorp/aws
        parts = provider_name.split("/")
        if parts:
            return parts[-1]

    # Fall back to resource type prefix
    prefix = resource_type.split("_")[0]
    return prefix


def _extract_provider_configs(plan_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract provider configurations from the plan JSON.

    This is used to detect default regions when resources don't specify one.
    """
    configs: dict[str, dict[str, Any]] = {}

    # Check the configuration block
    configuration = plan_json.get("configuration", {})
    provider_config = configuration.get("provider_config", {})

    for provider_key, config in provider_config.items():
        expressions = config.get("expressions", {})
        provider_settings: dict[str, Any] = {}

        # Extract region
        if "region" in expressions:
            region_expr = expressions["region"]
            if isinstance(region_expr, dict) and "constant_value" in region_expr:
                provider_settings["region"] = region_expr["constant_value"]

        configs[provider_key] = provider_settings

    return configs


def parse_tf_file_content(content: str) -> list[ParsedResourceConfig]:
    """Parse a raw .tf file to extract resource definitions.

    This is a simplified HCL parser that extracts resource blocks and their
    configurations. It doesn't handle all HCL features (like complex expressions,
    locals, or data sources), but it covers the most common patterns.

    This is used as a fallback when a full Terraform plan isn't available.

    Args:
        content: The raw .tf file content.

    Returns:
        A list of ParsedResourceConfig objects.
    """
    resources: list[ParsedResourceConfig] = []

    # Match resource blocks: resource "type" "name" { ... }
    # This regex handles nested blocks by counting braces
    resource_pattern = re.compile(
        r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{',
        re.MULTILINE,
    )

    for match in resource_pattern.finditer(content):
        resource_type = match.group(1)
        resource_name = match.group(2)

        # Extract the block content by counting braces
        start = match.end()
        config_str = _extract_block(content, start)

        # Parse the block content into key-value pairs
        config = _parse_hcl_block(config_str)

        # Detect count and for_each
        count = None
        for_each = None
        if "count" in config:
            try:
                count = int(config.pop("count"))
            except (ValueError, TypeError):
                count = 1  # If count is a variable, assume 1

        if "for_each" in config:
            config.pop("for_each")
            for_each = ["instance"]  # Placeholder — can't resolve variables

        resources.append(
            ParsedResourceConfig(
                resource_type=resource_type,
                resource_name=resource_name,
                config=config,
                count=count,
                for_each=for_each,
            )
        )

    logger.debug("Parsed %d resources from .tf file", len(resources))
    return resources


def _extract_block(content: str, start: int) -> str:
    """Extract a brace-delimited block from content, handling nesting.

    Args:
        content: The full file content.
        start: The position right after the opening brace.

    Returns:
        The block content (excluding outer braces).
    """
    depth = 1
    pos = start
    while pos < len(content) and depth > 0:
        char = content[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        pos += 1
    return content[start : pos - 1]


def _parse_hcl_block(block: str) -> dict[str, Any]:
    """Parse a simplified HCL block into key-value pairs.

    Handles:
    - Simple key = "value" assignments
    - Simple key = number assignments
    - Simple key = true/false assignments
    - Nested blocks (as nested dicts)

    Does NOT handle:
    - Complex expressions, interpolations, or function calls
    - Lists with mixed types
    - Heredoc strings
    """
    config: dict[str, Any] = {}

    # Match simple assignments: key = "value" or key = 123 or key = true
    assignment_pattern = re.compile(
        r'^\s*(\w+)\s*=\s*"([^"]*)"',
        re.MULTILINE,
    )
    for match in assignment_pattern.finditer(block):
        config[match.group(1)] = match.group(2)

    # Match number assignments: key = 123
    number_pattern = re.compile(
        r"^\s*(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*$",
        re.MULTILINE,
    )
    for match in number_pattern.finditer(block):
        key = match.group(1)
        if key not in config:  # Don't overwrite string values
            value = match.group(2)
            config[key] = float(value) if "." in value else int(value)

    # Match boolean assignments: key = true/false
    bool_pattern = re.compile(
        r"^\s*(\w+)\s*=\s*(true|false)\s*$",
        re.MULTILINE,
    )
    for match in bool_pattern.finditer(block):
        key = match.group(1)
        if key not in config:
            config[key] = match.group(2) == "true"

    return config


def get_default_region(
    provider: str,
    provider_configs: dict[str, dict[str, Any]],
) -> str:
    """Get the default region for a provider from the plan's provider configs.

    Falls back to well-known defaults if no configuration is found.
    """
    # Check provider configs from the plan
    for key, config in provider_configs.items():
        if provider in key and "region" in config:
            return config["region"]

    # Default regions by provider
    defaults = {
        "aws": "us-east-1",
        "google": "us-central1",
        "azurerm": "eastus",
    }
    return defaults.get(provider, "us-east-1")


def filter_costable_changes(plan: TerraformPlan) -> list[ResourceChange]:
    """Filter resource changes to only those that have cost implications.

    Removes no-op, read, and unsupported resource types.
    """
    return [
        change
        for change in plan.resource_changes
        if change.action in {
            ResourceAction.CREATE,
            ResourceAction.UPDATE,
            ResourceAction.DELETE,
            ResourceAction.REPLACE,
        }
        and change.resource_type in SUPPORTED_RESOURCE_TYPES
    ]
