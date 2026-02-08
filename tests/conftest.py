"""
Shared Test Fixtures

Provides common fixtures for all test modules:
- Sample Terraform plan JSON
- Resource configurations
- Mock services
"""

from __future__ import annotations

import pytest
from typing import Any


@pytest.fixture
def sample_plan_json() -> dict[str, Any]:
    """A complete sample Terraform plan JSON for testing."""
    return {
        "format_version": "1.2",
        "terraform_version": "1.6.0",
        "resource_changes": [
            {
                "address": "aws_instance.web",
                "type": "aws_instance",
                "name": "web",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {
                        "ami": "ami-0c55b159cbfafe1f0",
                        "instance_type": "t3.large",
                        "tenancy": "default",
                        "tags": {"Name": "web-server"},
                    },
                },
            },
            {
                "address": "aws_db_instance.main",
                "type": "aws_db_instance",
                "name": "main",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {
                        "instance_class": "db.r5.large",
                        "engine": "postgres",
                        "allocated_storage": 100,
                        "multi_az": True,
                        "storage_type": "gp2",
                    },
                },
            },
            {
                "address": "aws_s3_bucket.data",
                "type": "aws_s3_bucket",
                "name": "data",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["delete"],
                    "before": {
                        "tags": {"Name": "data-bucket"},
                    },
                    "after": None,
                },
            },
        ],
        "configuration": {
            "provider_config": {
                "aws": {
                    "expressions": {
                        "region": {"constant_value": "us-east-1"},
                    },
                },
            },
        },
    }


@pytest.fixture
def sample_ec2_config() -> dict[str, Any]:
    """Sample EC2 instance configuration."""
    return {
        "instance_type": "t3.large",
        "ami": "ami-0c55b159cbfafe1f0",
        "tenancy": "default",
        "tags": {"Name": "web-server"},
    }


@pytest.fixture
def sample_rds_config() -> dict[str, Any]:
    """Sample RDS instance configuration."""
    return {
        "instance_class": "db.r5.large",
        "engine": "postgres",
        "allocated_storage": 100,
        "multi_az": True,
        "storage_type": "gp2",
    }


@pytest.fixture
def sample_lambda_config() -> dict[str, Any]:
    """Sample Lambda function configuration."""
    return {
        "function_name": "data-processor",
        "runtime": "python3.11",
        "memory_size": 512,
        "timeout": 30,
    }


@pytest.fixture
def sample_gcp_compute_config() -> dict[str, Any]:
    """Sample GCP Compute Engine configuration."""
    return {
        "name": "web-server",
        "machine_type": "e2-standard-4",
        "zone": "us-central1-a",
    }


@pytest.fixture
def sample_tf_file_content() -> str:
    """Sample .tf file content for parsing tests."""
    return '''
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
  }

  tags = {
    Name = "web-server"
  }
}

resource "aws_db_instance" "main" {
  instance_class    = "db.r5.large"
  engine            = "postgres"
  allocated_storage = 100
  multi_az          = true
  storage_type      = "gp2"
}

resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}

resource "google_compute_instance" "api" {
  name         = "api-server"
  machine_type = "e2-standard-2"
  zone         = "us-central1-a"
}
'''


@pytest.fixture
def sample_webhook_payload() -> dict[str, Any]:
    """Sample GitHub pull_request webhook payload."""
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "id": 123456789,
            "number": 42,
            "title": "Add new RDS instance",
            "state": "open",
            "head": {
                "sha": "abc123def456",
                "ref": "feature/add-rds",
            },
            "base": {
                "sha": "789ghi012jkl",
                "ref": "main",
            },
            "user": {
                "id": 12345,
                "login": "developer",
            },
            "draft": False,
        },
        "repository": {
            "id": 987654321,
            "full_name": "myorg/infrastructure",
            "name": "infrastructure",
            "private": True,
            "default_branch": "main",
        },
        "installation": {
            "id": 11111111,
        },
    }
