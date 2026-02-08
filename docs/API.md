# API Reference

## Base URL

- **Production**: `https://api.infracents.dev`
- **Local Development**: `http://localhost:8000`

## Authentication

### Webhook Endpoints
Webhook endpoints are authenticated via **HMAC-SHA256 signature verification**. GitHub signs every webhook payload with the shared secret configured in the GitHub App settings.

```
X-Hub-Signature-256: sha256=<hex-digest>
```

### Dashboard API Endpoints
All dashboard API endpoints require a **Clerk JWT** in the `Authorization` header:

```
Authorization: Bearer <clerk-jwt-token>
```

The JWT is validated against Clerk's JWKS endpoint. The `org_id` claim is extracted to scope data access.

### API Key Authentication (Future)
For CI/CD integrations, an API key authentication method will be available:

```
X-API-Key: ic_live_<key>
```

---

## Endpoints

### Health

#### `GET /health`

Health check endpoint. No authentication required.

**Response** `200 OK`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

**Response** `503 Service Unavailable`
```json
{
  "status": "unhealthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": "error",
    "redis": "ok"
  }
}
```

#### `GET /health/ready`

Readiness probe for Kubernetes/Cloud Run.

**Response** `200 OK`
```json
{
  "ready": true
}
```

---

### Webhooks

#### `POST /webhooks/github`

Receives GitHub webhook events. This is the primary entry point for the cost estimation pipeline.

**Headers**
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-Hub-Signature-256` | string | Yes | HMAC-SHA256 signature of the payload |
| `X-GitHub-Event` | string | Yes | Event type (e.g., `pull_request`) |
| `X-GitHub-Delivery` | string | Yes | Unique delivery ID |
| `Content-Type` | string | Yes | Must be `application/json` |

**Supported Events**

| Event | Action | Behavior |
|-------|--------|----------|
| `pull_request` | `opened` | Full cost analysis |
| `pull_request` | `synchronize` | Re-analyze with updated files |
| `pull_request` | `reopened` | Full cost analysis |
| `installation` | `created` | Register new organization |
| `installation` | `deleted` | Deactivate organization |

**Request Body** (pull_request event)
```json
{
  "action": "opened",
  "number": 42,
  "pull_request": {
    "id": 123456789,
    "number": 42,
    "title": "Add new RDS instance",
    "head": {
      "sha": "abc123def456",
      "ref": "feature/add-rds"
    },
    "base": {
      "sha": "789ghi012jkl",
      "ref": "main"
    },
    "user": {
      "login": "developer",
      "id": 12345
    }
  },
  "repository": {
    "id": 987654321,
    "full_name": "myorg/infrastructure",
    "private": true
  },
  "installation": {
    "id": 11111111
  }
}
```

**Response** `200 OK`
```json
{
  "status": "processed",
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "cost_delta": 142.50,
  "resources_analyzed": 5
}
```

**Response** `200 OK` (no .tf changes)
```json
{
  "status": "skipped",
  "reason": "no_terraform_changes"
}
```

**Response** `400 Bad Request`
```json
{
  "detail": "Invalid webhook signature"
}
```

**Response** `429 Too Many Requests`
```json
{
  "detail": "Scan limit exceeded for current billing period",
  "current_usage": 500,
  "limit": 500,
  "plan": "pro",
  "upgrade_url": "https://infracents.dev/dashboard/settings"
}
```

---

### Dashboard API

All dashboard endpoints require Clerk JWT authentication.

#### `GET /api/dashboard/overview`

Returns the organization-level cost overview.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period (`7d`, `30d`, `90d`, `1y`) |

**Response** `200 OK`
```json
{
  "org": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Organization",
    "slug": "my-org"
  },
  "summary": {
    "total_scans": 127,
    "total_cost_delta": 1542.30,
    "avg_cost_per_pr": 12.15,
    "repos_active": 8,
    "cost_trend": "increasing"
  },
  "cost_by_day": [
    {
      "date": "2024-01-01",
      "total_delta": 45.20,
      "scan_count": 3
    }
  ],
  "top_repos": [
    {
      "repo_id": "uuid",
      "full_name": "myorg/infrastructure",
      "total_delta": 890.00,
      "scan_count": 42,
      "last_scan": "2024-01-15T10:30:00Z"
    }
  ],
  "recent_scans": [
    {
      "scan_id": "uuid",
      "repo_name": "myorg/infrastructure",
      "pr_number": 42,
      "pr_title": "Add new RDS instance",
      "cost_delta": 142.50,
      "cost_delta_percent": 12.3,
      "status": "completed",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### `GET /api/dashboard/repos`

List all repositories for the organization.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | `1` | Page number |
| `per_page` | int | `20` | Results per page (max 100) |
| `sort` | string | `last_scan` | Sort field (`name`, `last_scan`, `total_delta`) |
| `order` | string | `desc` | Sort order (`asc`, `desc`) |

**Response** `200 OK`
```json
{
  "repos": [
    {
      "id": "uuid",
      "full_name": "myorg/infrastructure",
      "active": true,
      "total_scans": 42,
      "total_cost_delta": 890.00,
      "last_scan_at": "2024-01-15T10:30:00Z",
      "last_cost_delta": 142.50
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 8,
    "total_pages": 1
  }
}
```

#### `GET /api/dashboard/repos/{repo_id}`

Detailed view for a specific repository.

**Path Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| `repo_id` | uuid | Repository ID |

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period |
| `page` | int | `1` | Page for scan list |
| `per_page` | int | `20` | Scans per page |

**Response** `200 OK`
```json
{
  "repo": {
    "id": "uuid",
    "full_name": "myorg/infrastructure",
    "default_branch": "main",
    "active": true,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "cost_by_day": [
    {
      "date": "2024-01-01",
      "total_delta": 45.20,
      "scan_count": 3
    }
  ],
  "scans": [
    {
      "id": "uuid",
      "pr_number": 42,
      "pr_title": "Add new RDS instance",
      "commit_sha": "abc123",
      "cost_delta": 142.50,
      "cost_delta_percent": 12.3,
      "total_cost_before": 1158.00,
      "total_cost_after": 1300.50,
      "status": "completed",
      "line_items": [
        {
          "resource_type": "aws_db_instance",
          "resource_name": "main_db",
          "action": "create",
          "provider": "aws",
          "monthly_cost_before": 0.00,
          "monthly_cost_after": 142.50,
          "cost_delta": 142.50,
          "confidence": "high"
        }
      ],
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3
  }
}
```

#### `GET /api/dashboard/scans/{scan_id}`

Full details for a specific scan.

**Response** `200 OK`
```json
{
  "id": "uuid",
  "repo": {
    "id": "uuid",
    "full_name": "myorg/infrastructure"
  },
  "pr_number": 42,
  "pr_title": "Add new RDS instance",
  "commit_sha": "abc123def456",
  "status": "completed",
  "total_cost_before": 1158.00,
  "total_cost_after": 1300.50,
  "cost_delta": 142.50,
  "cost_delta_percent": 12.3,
  "resource_breakdown": {
    "aws": {
      "cost_before": 1158.00,
      "cost_after": 1300.50,
      "delta": 142.50
    },
    "gcp": {
      "cost_before": 0.00,
      "cost_after": 0.00,
      "delta": 0.00
    }
  },
  "line_items": [
    {
      "id": "uuid",
      "resource_type": "aws_db_instance",
      "resource_name": "main_db",
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
        "storage_rate_per_gb": 0.115,
        "multi_az": false
      },
      "confidence": "high"
    }
  ],
  "comment_id": 123456789,
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:03Z"
}
```

---

### Billing

#### `GET /api/billing/subscription`

Get the current subscription status.

**Response** `200 OK`
```json
{
  "plan": "pro",
  "status": "active",
  "scan_limit": 500,
  "repo_limit": 15,
  "scans_used": 127,
  "scans_remaining": 373,
  "current_period_start": "2024-01-01T00:00:00Z",
  "current_period_end": "2024-02-01T00:00:00Z",
  "stripe_customer_id": "cus_xxxxx",
  "cancel_at_period_end": false
}
```

#### `POST /api/billing/checkout`

Create a Stripe Checkout session for upgrading.

**Request Body**
```json
{
  "plan": "business",
  "success_url": "https://infracents.dev/dashboard/settings?success=true",
  "cancel_url": "https://infracents.dev/dashboard/settings?canceled=true"
}
```

**Response** `200 OK`
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_xxxxx",
  "session_id": "cs_xxxxx"
}
```

#### `POST /api/billing/portal`

Create a Stripe Customer Portal session for managing billing.

**Response** `200 OK`
```json
{
  "portal_url": "https://billing.stripe.com/p/session/xxxxx"
}
```

#### `POST /webhooks/stripe`

Receives Stripe webhook events for subscription lifecycle management.

**Headers**
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Stripe-Signature` | string | Yes | Stripe webhook signature |

**Handled Events**
| Event | Behavior |
|-------|----------|
| `checkout.session.completed` | Activate subscription |
| `customer.subscription.updated` | Update plan/status |
| `customer.subscription.deleted` | Deactivate subscription |
| `invoice.payment_failed` | Mark subscription as past_due |

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "status_code": 400
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|------------|-------------|
| `INVALID_SIGNATURE` | 400 | Webhook signature verification failed |
| `UNSUPPORTED_EVENT` | 400 | Received an unsupported webhook event |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `SCAN_LIMIT_EXCEEDED` | 429 | Organization has exceeded scan limit |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `PRICING_API_ERROR` | 502 | Cloud pricing API unavailable |

---

## Rate Limiting

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Webhooks | 100 req/min per installation | 1 minute |
| Dashboard API | 60 req/min per user | 1 minute |
| Billing API | 10 req/min per user | 1 minute |
| Health checks | Unlimited | - |

Rate limit headers are included in all responses:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1705312200
```

---

## Pagination

List endpoints use cursor-based pagination:

```
GET /api/dashboard/repos?page=2&per_page=20
```

Response includes pagination metadata:
```json
{
  "pagination": {
    "page": 2,
    "per_page": 20,
    "total": 85,
    "total_pages": 5
  }
}
```

---

## Webhooks (Outgoing)

InfraCents can send outgoing webhooks to your systems (Business and Enterprise plans).

### Supported Events

| Event | Trigger |
|-------|---------|
| `scan.completed` | Cost analysis finished |
| `scan.failed` | Cost analysis encountered an error |
| `threshold.exceeded` | Cost delta exceeds configured threshold |

### Payload Format

```json
{
  "event": "scan.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "scan_id": "uuid",
    "repo": "myorg/infrastructure",
    "pr_number": 42,
    "cost_delta": 142.50,
    "cost_delta_percent": 12.3
  }
}
```
