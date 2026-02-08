"""
Terraform Plan Data Models

Pydantic models for parsing and representing Terraform plan JSON output.
Supports both `terraform show -json` format and the HCL-parsed resource
configuration format.

Reference: https://developer.hashicorp.com/terraform/internals/json-format
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResourceAction(str, Enum):
    """Possible actions for a resource in a Terraform plan."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"  # delete + create
    READ = "read"
    NO_OP = "no-op"


class ResourceChange(BaseModel):
    """Represents a single resource change from a Terraform plan.

    This is the core unit of work for the pricing engine — each ResourceChange
    maps to a cloud resource that has a cost associated with it.
    """
    # Resource identification
    address: str = Field(
        ...,
        description="Full resource address (e.g., 'aws_instance.web')",
    )
    resource_type: str = Field(
        ...,
        description="Terraform resource type (e.g., 'aws_instance')",
    )
    resource_name: str = Field(
        ...,
        description="Resource name within the Terraform config (e.g., 'web')",
    )
    provider: str = Field(
        ...,
        description="Provider name (e.g., 'aws', 'google')",
    )

    # Change details
    action: ResourceAction = Field(
        ...,
        description="What action is being taken (create, update, delete, etc.)",
    )
    before: Optional[dict[str, Any]] = Field(
        default=None,
        description="Resource configuration before the change (None for creates)",
    )
    after: Optional[dict[str, Any]] = Field(
        default=None,
        description="Resource configuration after the change (None for deletes)",
    )

    # Module path (for resources inside modules)
    module_address: Optional[str] = Field(
        default=None,
        description="Module address if the resource is inside a module",
    )

    @property
    def config(self) -> dict[str, Any]:
        """Get the effective configuration for pricing.

        For creates and updates, use the 'after' configuration.
        For deletes, use the 'before' configuration.
        """
        if self.action == ResourceAction.DELETE:
            return self.before or {}
        return self.after or {}

    @property
    def previous_config(self) -> dict[str, Any]:
        """Get the previous configuration (for calculating deltas on updates)."""
        return self.before or {}


class TerraformPlan(BaseModel):
    """Represents a parsed Terraform plan with resource changes.

    This is the top-level model that the Terraform parser produces.
    It contains all the information needed to calculate cost deltas.
    """
    # Plan metadata
    format_version: str = Field(
        default="1.0",
        description="Terraform plan JSON format version",
    )
    terraform_version: Optional[str] = Field(
        default=None,
        description="Terraform version that generated the plan",
    )

    # Resource changes
    resource_changes: list[ResourceChange] = Field(
        default_factory=list,
        description="List of all resource changes in the plan",
    )

    # Provider configuration (for extracting default regions, etc.)
    provider_configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider configurations (e.g., default region)",
    )

    @property
    def creates(self) -> list[ResourceChange]:
        """Resources being created."""
        return [r for r in self.resource_changes if r.action == ResourceAction.CREATE]

    @property
    def updates(self) -> list[ResourceChange]:
        """Resources being updated."""
        return [r for r in self.resource_changes if r.action == ResourceAction.UPDATE]

    @property
    def deletes(self) -> list[ResourceChange]:
        """Resources being deleted."""
        return [r for r in self.resource_changes if r.action == ResourceAction.DELETE]

    @property
    def replaces(self) -> list[ResourceChange]:
        """Resources being replaced (delete + create)."""
        return [r for r in self.resource_changes if r.action == ResourceAction.REPLACE]

    @property
    def has_changes(self) -> bool:
        """Check if the plan has any resource changes."""
        return len(self.resource_changes) > 0

    @property
    def resource_types(self) -> set[str]:
        """Get unique resource types in the plan."""
        return {r.resource_type for r in self.resource_changes}


class TerraformFileChange(BaseModel):
    """Represents a changed .tf file in a pull request.

    Used by the GitHub service to communicate which files changed.
    """
    filename: str = Field(..., description="File path relative to repo root")
    status: str = Field(
        ...,
        description="File change status (added, modified, removed, renamed)",
    )
    patch: Optional[str] = Field(
        default=None,
        description="Unified diff patch content",
    )
    contents: Optional[str] = Field(
        default=None,
        description="Full file contents (fetched separately)",
    )

    @property
    def is_terraform(self) -> bool:
        """Check if this is a Terraform file."""
        return self.filename.endswith(".tf") or self.filename.endswith(".tf.json")


class ParsedResourceConfig(BaseModel):
    """A resource configuration parsed directly from HCL/JSON .tf files.

    This is used when we parse .tf files directly (without a Terraform plan)
    to extract resource definitions.
    """
    resource_type: str = Field(..., description="Terraform resource type")
    resource_name: str = Field(..., description="Resource name in config")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Resource configuration key-value pairs",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Explicit provider alias",
    )
    count: Optional[int] = Field(
        default=None,
        description="Count meta-argument value",
    )
    for_each: Optional[list[str]] = Field(
        default=None,
        description="for_each keys (if determinable)",
    )

    @property
    def instance_count(self) -> int:
        """Get the number of instances this resource creates."""
        if self.count is not None:
            return max(self.count, 0)
        if self.for_each is not None:
            return len(self.for_each)
        return 1

    @property
    def inferred_provider(self) -> str:
        """Infer the provider from the resource type prefix."""
        if self.provider:
            return self.provider
        prefix = self.resource_type.split("_")[0]
        provider_map = {
            "aws": "aws",
            "google": "google",
            "azurerm": "azure",
            "digitalocean": "digitalocean",
        }
        return provider_map.get(prefix, prefix)
