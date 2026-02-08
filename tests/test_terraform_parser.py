"""
Tests for Terraform Plan Parser

Tests parsing of:
- Standard Terraform plan JSON format
- Resource action detection (create, update, delete, replace)
- Provider extraction
- Raw .tf file parsing
- All 25 supported resource types
"""

from __future__ import annotations

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from services.terraform_parser import (
    parse_plan_json,
    parse_tf_file_content,
    filter_costable_changes,
    get_default_region,
    SUPPORTED_RESOURCE_TYPES,
    _determine_action,
    _extract_provider,
)
from models.terraform import ResourceAction, TerraformPlan


class TestParsePlanJson:
    """Tests for parsing Terraform plan JSON output."""

    def test_parse_basic_plan(self, sample_plan_json):
        """Test parsing a basic plan with create and delete actions."""
        plan = parse_plan_json(sample_plan_json)

        assert isinstance(plan, TerraformPlan)
        assert plan.has_changes
        assert len(plan.resource_changes) == 3
        assert plan.terraform_version == "1.6.0"

    def test_parse_creates(self, sample_plan_json):
        """Test that creates are correctly identified."""
        plan = parse_plan_json(sample_plan_json)

        creates = plan.creates
        assert len(creates) == 2
        assert creates[0].resource_type == "aws_instance"
        assert creates[1].resource_type == "aws_db_instance"

    def test_parse_deletes(self, sample_plan_json):
        """Test that deletes are correctly identified."""
        plan = parse_plan_json(sample_plan_json)

        deletes = plan.deletes
        assert len(deletes) == 1
        assert deletes[0].resource_type == "aws_s3_bucket"

    def test_parse_resource_config(self, sample_plan_json):
        """Test that resource configuration is correctly extracted."""
        plan = parse_plan_json(sample_plan_json)

        ec2 = plan.creates[0]
        assert ec2.config["instance_type"] == "t3.large"
        assert ec2.config["ami"] == "ami-0c55b159cbfafe1f0"

    def test_parse_provider_detection(self, sample_plan_json):
        """Test that the provider is correctly detected."""
        plan = parse_plan_json(sample_plan_json)

        assert plan.creates[0].provider == "aws"

    def test_parse_provider_configs(self, sample_plan_json):
        """Test extraction of provider configurations (default region)."""
        plan = parse_plan_json(sample_plan_json)

        assert "aws" in plan.provider_configs
        assert plan.provider_configs["aws"]["region"] == "us-east-1"

    def test_parse_empty_plan(self):
        """Test parsing a plan with no resource changes."""
        plan = parse_plan_json({"resource_changes": []})

        assert not plan.has_changes
        assert len(plan.resource_changes) == 0

    def test_parse_unsupported_resource_skipped(self):
        """Test that unsupported resource types are skipped."""
        plan_json = {
            "resource_changes": [
                {
                    "address": "aws_iam_role.test",
                    "type": "aws_iam_role",
                    "name": "test",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "change": {"actions": ["create"], "before": None, "after": {}},
                },
            ],
        }
        plan = parse_plan_json(plan_json)
        assert len(plan.resource_changes) == 0  # IAM role is not in supported types

    def test_parse_no_op_skipped(self):
        """Test that no-op actions are skipped."""
        plan_json = {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "change": {"actions": ["no-op"], "before": {}, "after": {}},
                },
            ],
        }
        plan = parse_plan_json(plan_json)
        assert len(plan.resource_changes) == 0

    def test_parse_update_action(self):
        """Test parsing an update action."""
        plan_json = {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "change": {
                        "actions": ["update"],
                        "before": {"instance_type": "t3.small"},
                        "after": {"instance_type": "t3.large"},
                    },
                },
            ],
        }
        plan = parse_plan_json(plan_json)
        assert len(plan.updates) == 1
        assert plan.updates[0].previous_config["instance_type"] == "t3.small"
        assert plan.updates[0].config["instance_type"] == "t3.large"

    def test_parse_replace_action(self):
        """Test parsing a replace (delete + create) action."""
        plan_json = {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "change": {
                        "actions": ["delete", "create"],
                        "before": {"instance_type": "t3.small"},
                        "after": {"instance_type": "m5.large"},
                    },
                },
            ],
        }
        plan = parse_plan_json(plan_json)
        assert len(plan.replaces) == 1

    def test_resource_types_property(self, sample_plan_json):
        """Test the resource_types property."""
        plan = parse_plan_json(sample_plan_json)
        types = plan.resource_types
        assert "aws_instance" in types
        assert "aws_db_instance" in types
        assert "aws_s3_bucket" in types


class TestDetermineAction:
    """Tests for the action determination logic."""

    def test_create(self):
        assert _determine_action(["create"]) == ResourceAction.CREATE

    def test_update(self):
        assert _determine_action(["update"]) == ResourceAction.UPDATE

    def test_delete(self):
        assert _determine_action(["delete"]) == ResourceAction.DELETE

    def test_replace_delete_create(self):
        assert _determine_action(["delete", "create"]) == ResourceAction.REPLACE

    def test_replace_create_delete(self):
        assert _determine_action(["create", "delete"]) == ResourceAction.REPLACE

    def test_no_op(self):
        assert _determine_action(["no-op"]) == ResourceAction.NO_OP

    def test_read(self):
        assert _determine_action(["read"]) == ResourceAction.READ

    def test_empty(self):
        assert _determine_action([]) is None


class TestExtractProvider:
    """Tests for provider extraction."""

    def test_from_provider_name(self):
        assert _extract_provider("aws_instance", "registry.terraform.io/hashicorp/aws") == "aws"

    def test_from_resource_type(self):
        assert _extract_provider("google_compute_instance", "") == "google"

    def test_aws_prefix(self):
        assert _extract_provider("aws_s3_bucket", "") == "aws"


class TestParseTfFile:
    """Tests for raw .tf file parsing."""

    def test_parse_basic_resources(self, sample_tf_file_content):
        """Test parsing resources from a .tf file."""
        resources = parse_tf_file_content(sample_tf_file_content)

        assert len(resources) == 4
        types = {r.resource_type for r in resources}
        assert "aws_instance" in types
        assert "aws_db_instance" in types
        assert "aws_s3_bucket" in types
        assert "google_compute_instance" in types

    def test_parse_config_values(self, sample_tf_file_content):
        """Test that configuration values are correctly extracted."""
        resources = parse_tf_file_content(sample_tf_file_content)

        ec2 = next(r for r in resources if r.resource_type == "aws_instance")
        assert ec2.config.get("instance_type") == "t3.large"

    def test_parse_inferred_provider(self, sample_tf_file_content):
        """Test that provider is inferred from resource type."""
        resources = parse_tf_file_content(sample_tf_file_content)

        ec2 = next(r for r in resources if r.resource_type == "aws_instance")
        assert ec2.inferred_provider == "aws"

        gcp = next(r for r in resources if r.resource_type == "google_compute_instance")
        assert gcp.inferred_provider == "google"

    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        resources = parse_tf_file_content("")
        assert len(resources) == 0

    def test_parse_count(self):
        """Test parsing a resource with count."""
        content = '''
resource "aws_instance" "workers" {
  count         = 3
  instance_type = "t3.medium"
}
'''
        resources = parse_tf_file_content(content)
        assert len(resources) == 1
        assert resources[0].instance_count == 3

    def test_parse_boolean_value(self):
        """Test parsing boolean values."""
        content = '''
resource "aws_db_instance" "main" {
  multi_az = true
}
'''
        resources = parse_tf_file_content(content)
        assert resources[0].config.get("multi_az") is True


class TestSupportedResourceTypes:
    """Tests for supported resource types."""

    def test_aws_instance_supported(self):
        assert "aws_instance" in SUPPORTED_RESOURCE_TYPES

    def test_aws_db_instance_supported(self):
        assert "aws_db_instance" in SUPPORTED_RESOURCE_TYPES

    def test_aws_s3_bucket_supported(self):
        assert "aws_s3_bucket" in SUPPORTED_RESOURCE_TYPES

    def test_aws_lambda_function_supported(self):
        assert "aws_lambda_function" in SUPPORTED_RESOURCE_TYPES

    def test_aws_lb_supported(self):
        assert "aws_lb" in SUPPORTED_RESOURCE_TYPES

    def test_aws_nat_gateway_supported(self):
        assert "aws_nat_gateway" in SUPPORTED_RESOURCE_TYPES

    def test_aws_ecs_service_supported(self):
        assert "aws_ecs_service" in SUPPORTED_RESOURCE_TYPES

    def test_aws_elasticache_cluster_supported(self):
        assert "aws_elasticache_cluster" in SUPPORTED_RESOURCE_TYPES

    def test_aws_dynamodb_table_supported(self):
        assert "aws_dynamodb_table" in SUPPORTED_RESOURCE_TYPES

    def test_aws_ebs_volume_supported(self):
        assert "aws_ebs_volume" in SUPPORTED_RESOURCE_TYPES

    def test_aws_cloudfront_distribution_supported(self):
        assert "aws_cloudfront_distribution" in SUPPORTED_RESOURCE_TYPES

    def test_aws_route53_zone_supported(self):
        assert "aws_route53_zone" in SUPPORTED_RESOURCE_TYPES

    def test_aws_sqs_queue_supported(self):
        assert "aws_sqs_queue" in SUPPORTED_RESOURCE_TYPES

    def test_aws_sns_topic_supported(self):
        assert "aws_sns_topic" in SUPPORTED_RESOURCE_TYPES

    def test_aws_secretsmanager_secret_supported(self):
        assert "aws_secretsmanager_secret" in SUPPORTED_RESOURCE_TYPES

    def test_google_compute_instance_supported(self):
        assert "google_compute_instance" in SUPPORTED_RESOURCE_TYPES

    def test_google_sql_database_instance_supported(self):
        assert "google_sql_database_instance" in SUPPORTED_RESOURCE_TYPES

    def test_google_storage_bucket_supported(self):
        assert "google_storage_bucket" in SUPPORTED_RESOURCE_TYPES

    def test_google_cloudfunctions_function_supported(self):
        assert "google_cloudfunctions_function" in SUPPORTED_RESOURCE_TYPES

    def test_google_container_node_pool_supported(self):
        assert "google_container_node_pool" in SUPPORTED_RESOURCE_TYPES

    def test_total_supported_types(self):
        """Verify we support at least 25 resource types."""
        assert len(SUPPORTED_RESOURCE_TYPES) >= 25


class TestGetDefaultRegion:
    """Tests for default region resolution."""

    def test_aws_default(self):
        assert get_default_region("aws", {}) == "us-east-1"

    def test_gcp_default(self):
        assert get_default_region("google", {}) == "us-central1"

    def test_from_provider_config(self):
        configs = {"aws": {"region": "eu-west-1"}}
        assert get_default_region("aws", configs) == "eu-west-1"


class TestFilterCostableChanges:
    """Tests for filtering changes to only costable ones."""

    def test_filter_creates_updates_deletes(self, sample_plan_json):
        plan = parse_plan_json(sample_plan_json)
        costable = filter_costable_changes(plan)
        assert len(costable) == 3
