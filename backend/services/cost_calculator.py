"""
Cost Calculator Service

Orchestrates the full cost estimation pipeline:
1. Receives a webhook event
2. Fetches changed files
3. Parses Terraform resources
4. Estimates costs via the pricing engine
5. Returns a CostEstimate

This is the "glue" service that ties together the parser, pricing engine,
and GitHub service.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from models.pricing import CostEstimate, ResourceCost, CloudProvider, CostConfidence
from models.terraform import (
    ResourceAction,
    ResourceChange,
    TerraformPlan,
)
from services.terraform_parser import (
    parse_plan_json,
    parse_tf_file_content,
    filter_costable_changes,
    get_default_region,
    SUPPORTED_RESOURCE_TYPES,
)
from services.pricing_engine import PricingEngine
from services.github_service import GitHubService, get_terraform_files
from services.cache_service import CacheService

logger = logging.getLogger(__name__)


class CostCalculator:
    """Orchestrates the cost estimation pipeline.

    This is the main entry point called by the webhook handler.
    It coordinates fetching files, parsing Terraform, and estimating costs.
    """

    def __init__(
        self,
        github_service: GitHubService,
        pricing_engine: PricingEngine,
    ):
        self.github = github_service
        self.pricing = pricing_engine

    async def analyze_pull_request(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        base_sha: str,
    ) -> CostEstimate:
        """Analyze a pull request for cost impact.

        This is the main method called by the webhook handler. It:
        1. Fetches the list of changed files
        2. Filters to .tf files
        3. Fetches the content of changed .tf files (both head and base)
        4. Parses resources from both versions
        5. Calculates the cost delta

        Args:
            installation_id: GitHub App installation ID.
            repo_full_name: Repository name (org/repo).
            pr_number: PR number.
            head_sha: The head (new) commit SHA.
            base_sha: The base (old) commit SHA.

        Returns:
            A CostEstimate with the full cost breakdown.
        """
        logger.info(
            "Analyzing PR #%d in %s (head=%s, base=%s)",
            pr_number, repo_full_name, head_sha[:8], base_sha[:8],
        )

        # Step 1: Get changed files
        all_files = await self.github.get_pr_files(
            installation_id, repo_full_name, pr_number
        )
        tf_files = get_terraform_files(all_files)

        if not tf_files:
            logger.info("No Terraform files changed in PR #%d", pr_number)
            return CostEstimate()

        logger.info("Found %d Terraform files changed", len(tf_files))

        # Step 2: Fetch and parse resources from head (new) and base (old)
        head_resources = await self._collect_resources(
            installation_id, repo_full_name, tf_files, head_sha
        )
        base_resources = await self._collect_resources(
            installation_id, repo_full_name, tf_files, base_sha
        )

        # Step 3: Build a synthetic plan from the diff
        plan = self._build_change_plan(base_resources, head_resources)

        if not plan.has_changes:
            logger.info("No costable resource changes detected in PR #%d", pr_number)
            return CostEstimate()

        # Step 4: Estimate costs
        estimate = await self.pricing.estimate_plan_cost(plan)

        logger.info(
            "PR #%d cost analysis complete: delta=$%.2f/mo (%+.1f%%)",
            pr_number,
            estimate.cost_delta,
            estimate.cost_delta_percent,
        )

        return estimate

    async def analyze_plan_json(self, plan_json: dict[str, Any]) -> CostEstimate:
        """Analyze a Terraform plan JSON directly.

        This method is used when a Terraform plan JSON is provided directly
        (e.g., via CI/CD integration) instead of fetching from GitHub.

        Args:
            plan_json: The parsed Terraform plan JSON.

        Returns:
            A CostEstimate with the full cost breakdown.
        """
        plan = parse_plan_json(plan_json)
        return await self.pricing.estimate_plan_cost(plan)

    async def _collect_resources(
        self,
        installation_id: int,
        repo_full_name: str,
        tf_files: list,
        ref: str,
    ) -> dict[str, dict[str, Any]]:
        """Collect all Terraform resources from a set of files at a given ref.

        Fetches each .tf file from GitHub and parses it to extract resource
        definitions. Returns a dict keyed by resource address.

        Args:
            installation_id: GitHub App installation ID.
            repo_full_name: Repository name.
            tf_files: List of Terraform files to process.
            ref: Git ref (commit SHA) to fetch files at.

        Returns:
            Dict mapping resource address to config.
        """
        resources: dict[str, dict[str, Any]] = {}

        for file_info in tf_files:
            try:
                content = await self.github.get_file_content(
                    installation_id, repo_full_name, file_info.filename, ref
                )
                if content is None:
                    # File doesn't exist at this ref (e.g., newly added file)
                    continue

                parsed = parse_tf_file_content(content)
                for resource in parsed:
                    address = f"{resource.resource_type}.{resource.resource_name}"
                    resources[address] = {
                        "type": resource.resource_type,
                        "name": resource.resource_name,
                        "config": resource.config,
                        "count": resource.instance_count,
                        "provider": resource.inferred_provider,
                    }

            except Exception as e:
                logger.warning(
                    "Failed to parse %s at %s: %s",
                    file_info.filename, ref[:8], e,
                )

        logger.debug("Collected %d resources at ref %s", len(resources), ref[:8])
        return resources

    def _build_change_plan(
        self,
        base_resources: dict[str, dict[str, Any]],
        head_resources: dict[str, dict[str, Any]],
    ) -> TerraformPlan:
        """Build a TerraformPlan by diffing base and head resource sets.

        Compares the resource sets to determine creates, updates, and deletes.

        Args:
            base_resources: Resources in the base (old) version.
            head_resources: Resources in the head (new) version.

        Returns:
            A TerraformPlan with the computed resource changes.
        """
        changes: list[ResourceChange] = []

        all_addresses = set(base_resources.keys()) | set(head_resources.keys())

        for address in all_addresses:
            in_base = address in base_resources
            in_head = address in head_resources

            if in_head and not in_base:
                # New resource → CREATE
                head = head_resources[address]
                if head["type"] in SUPPORTED_RESOURCE_TYPES:
                    changes.append(ResourceChange(
                        address=address,
                        resource_type=head["type"],
                        resource_name=head["name"],
                        provider=head["provider"],
                        action=ResourceAction.CREATE,
                        before=None,
                        after=head["config"],
                    ))

            elif in_base and not in_head:
                # Removed resource → DELETE
                base = base_resources[address]
                if base["type"] in SUPPORTED_RESOURCE_TYPES:
                    changes.append(ResourceChange(
                        address=address,
                        resource_type=base["type"],
                        resource_name=base["name"],
                        provider=base["provider"],
                        action=ResourceAction.DELETE,
                        before=base["config"],
                        after=None,
                    ))

            elif in_base and in_head:
                # Both exist — check if config changed → UPDATE
                base = base_resources[address]
                head = head_resources[address]
                if base["config"] != head["config"] and head["type"] in SUPPORTED_RESOURCE_TYPES:
                    changes.append(ResourceChange(
                        address=address,
                        resource_type=head["type"],
                        resource_name=head["name"],
                        provider=head["provider"],
                        action=ResourceAction.UPDATE,
                        before=base["config"],
                        after=head["config"],
                    ))

        return TerraformPlan(resource_changes=changes)
