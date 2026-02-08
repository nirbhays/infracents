"""
Dashboard API Endpoints

Provides data for the InfraCents web dashboard:
- Organization overview (cost summary, top repos, recent scans)
- Repository detail (cost history, PR scan list)
- Scan detail (full resource breakdown)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from utils.security import extract_bearer_token, validate_clerk_jwt

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    """Dependency: Extract and validate the current user from the JWT.

    Returns the decoded JWT claims containing user_id and org_id.
    """
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    claims = await validate_clerk_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return claims


@router.get("/overview")
async def get_overview(
    period: str = Query(default="30d", regex="^(7d|30d|90d|1y)$"),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the organization-level cost overview.

    Returns summary metrics, cost-over-time data, top repos, and recent scans.
    This is the main dashboard view.
    """
    org_id = user.get("org_id", "org_dev")

    # Calculate the date range based on the period
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[period]
    start_date = datetime.utcnow() - timedelta(days=days)

    # In a real implementation, this would query PostgreSQL.
    # Returning structured mock data that matches the API schema.
    return {
        "org": {
            "id": org_id,
            "name": "Demo Organization",
            "slug": "demo-org",
        },
        "summary": {
            "total_scans": 127,
            "total_cost_delta": 1542.30,
            "avg_cost_per_pr": 12.15,
            "repos_active": 8,
            "cost_trend": "increasing",
        },
        "cost_by_day": _generate_sample_cost_data(days),
        "top_repos": [
            {
                "repo_id": "repo-001",
                "full_name": "demo-org/infrastructure",
                "total_delta": 890.00,
                "scan_count": 42,
                "last_scan": datetime.utcnow().isoformat(),
            },
            {
                "repo_id": "repo-002",
                "full_name": "demo-org/platform",
                "total_delta": 420.50,
                "scan_count": 38,
                "last_scan": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
            },
            {
                "repo_id": "repo-003",
                "full_name": "demo-org/services",
                "total_delta": 231.80,
                "scan_count": 47,
                "last_scan": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
            },
        ],
        "recent_scans": [
            {
                "scan_id": "scan-001",
                "repo_name": "demo-org/infrastructure",
                "pr_number": 142,
                "pr_title": "Add new RDS instance for analytics",
                "cost_delta": 142.50,
                "cost_delta_percent": 12.3,
                "status": "completed",
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "scan_id": "scan-002",
                "repo_name": "demo-org/platform",
                "pr_number": 89,
                "pr_title": "Scale up ECS service to 4 tasks",
                "cost_delta": 87.20,
                "cost_delta_percent": 8.5,
                "status": "completed",
                "created_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
            },
            {
                "scan_id": "scan-003",
                "repo_name": "demo-org/services",
                "pr_number": 256,
                "pr_title": "Remove unused ElastiCache cluster",
                "cost_delta": -65.00,
                "cost_delta_percent": -15.2,
                "status": "completed",
                "created_at": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
            },
        ],
    }


@router.get("/repos")
async def list_repos(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="last_scan"),
    order: str = Query(default="desc"),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """List all repositories for the authenticated organization."""
    org_id = user.get("org_id", "org_dev")

    # Mock data — in production, query PostgreSQL
    repos = [
        {
            "id": f"repo-{i:03d}",
            "full_name": f"demo-org/repo-{i}",
            "active": True,
            "total_scans": 42 - i * 3,
            "total_cost_delta": 890.00 - i * 120,
            "last_scan_at": (datetime.utcnow() - timedelta(hours=i * 2)).isoformat(),
            "last_cost_delta": 142.50 - i * 20,
        }
        for i in range(min(per_page, 8))
    ]

    return {
        "repos": repos,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": 8,
            "total_pages": 1,
        },
    }


@router.get("/repos/{repo_id}")
async def get_repo_detail(
    repo_id: str,
    period: str = Query(default="30d", regex="^(7d|30d|90d|1y)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed view for a specific repository."""
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[period]

    return {
        "repo": {
            "id": repo_id,
            "full_name": "demo-org/infrastructure",
            "default_branch": "main",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
        },
        "cost_by_day": _generate_sample_cost_data(days),
        "scans": [
            {
                "id": f"scan-{i:03d}",
                "pr_number": 140 + i,
                "pr_title": f"PR #{140 + i} — infrastructure change",
                "commit_sha": f"abc{i:04d}",
                "cost_delta": 142.50 - i * 15,
                "cost_delta_percent": 12.3 - i * 1.5,
                "total_cost_before": 1158.00,
                "total_cost_after": 1158.00 + 142.50 - i * 15,
                "status": "completed",
                "line_items": [
                    {
                        "resource_type": "aws_db_instance",
                        "resource_name": "main_db",
                        "action": "create" if i % 3 == 0 else ("update" if i % 3 == 1 else "delete"),
                        "provider": "aws",
                        "monthly_cost_before": 0.00 if i % 3 == 0 else 100.00,
                        "monthly_cost_after": 142.50 if i % 3 != 2 else 0.00,
                        "cost_delta": 142.50 - i * 15,
                        "confidence": "high",
                    }
                ],
                "created_at": (datetime.utcnow() - timedelta(days=i)).isoformat(),
            }
            for i in range(min(per_page, 10))
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": 42,
            "total_pages": 3,
        },
    }


@router.get("/scans/{scan_id}")
async def get_scan_detail(
    scan_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full details for a specific scan."""
    return {
        "id": scan_id,
        "repo": {
            "id": "repo-001",
            "full_name": "demo-org/infrastructure",
        },
        "pr_number": 142,
        "pr_title": "Add new RDS instance for analytics",
        "commit_sha": "abc123def456",
        "status": "completed",
        "total_cost_before": 1158.00,
        "total_cost_after": 1300.50,
        "cost_delta": 142.50,
        "cost_delta_percent": 12.3,
        "resource_breakdown": {
            "aws": {"cost_before": 1158.00, "cost_after": 1300.50, "delta": 142.50},
            "gcp": {"cost_before": 0.00, "cost_after": 0.00, "delta": 0.00},
        },
        "line_items": [
            {
                "id": "item-001",
                "resource_type": "aws_db_instance",
                "resource_name": "analytics_db",
                "action": "create",
                "provider": "aws",
                "monthly_cost_before": 0.00,
                "monthly_cost_after": 142.50,
                "cost_delta": 142.50,
                "pricing_details": {
                    "instance_class": "db.r5.large",
                    "engine": "postgres",
                    "region": "us-east-1",
                    "hourly_rate": 0.195,
                    "storage_gb": 100,
                    "multi_az": False,
                },
                "confidence": "high",
            }
        ],
        "comment_id": 123456789,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": (datetime.utcnow() + timedelta(seconds=3)).isoformat(),
    }


def _generate_sample_cost_data(days: int) -> list[dict[str, Any]]:
    """Generate sample cost-over-time data for the dashboard."""
    import random

    data = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days - i - 1)).strftime("%Y-%m-%d")
        # Simulate a general upward trend with noise
        base_delta = 20 + i * 0.5
        noise = random.uniform(-15, 25)
        scan_count = random.randint(1, 8)
        data.append({
            "date": date,
            "total_delta": round(max(0, base_delta + noise), 2),
            "scan_count": scan_count,
        })
    return data
