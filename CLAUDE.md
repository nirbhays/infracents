# CLAUDE.md — InfraCents

## What This Project Does

InfraCents is an open-source GitHub App that automatically posts real-time cloud cost estimates on pull requests that contain Terraform changes. When a developer opens or updates a PR with `.tf` files, InfraCents receives a GitHub webhook, fetches the changed files, parses them using a Terraform HCL/JSON parser, queries live pricing data from the AWS Price List API and GCP Cloud Billing Catalog API, calculates the monthly cost delta (added, modified, and removed resources), and posts a formatted Markdown comment directly on the PR showing per-resource costs, a net monthly change, and a confidence rating. No CLI tools to install, no CI pipeline configuration, no Terraform plan uploads required — one-click GitHub App install and every subsequent PR is covered.

---

## Owner Context

**Owner:** Nirbhay Singh — Cloud & AI Architect
**Career goal:** $800K USD total compensation as a Staff+/Principal AI Infrastructure Architect.
InfraCents is a **portfolio project** demonstrating expertise in cloud pricing APIs, GitHub App development, real-time cost estimation, and DevOps tooling. It is intentionally production-quality (real pricing API integration, webhook signature verification, multi-tenant billing, full dashboard) to be credible as a solo-built SaaS product in engineering interviews.

**Related repos in the portfolio (same owner: nirbhays):**
| Repo | What it does |
|---|---|
| `shieldiac` | IaC security scanner — GitHub App, 100+ rules, 9 compliance frameworks |
| `tokenmeter` | LLM cost intelligence — drop-in import replacement, tracks every token |
| `agent-loom` | Multi-agent orchestration framework |
| `airlock` | API gateway with rate limiting and auth for AI services |
| `model-ledger` | Audit trail and lineage tracking for ML models |
| `tune-forge` | Fine-tuning pipeline manager |
| `data-mint` | Synthetic data generation for LLM training |

InfraCents and shieldiac are the closest pair — both are GitHub Apps that post automated feedback on PRs. shieldiac = security; infracents = cost. They share almost identical GitHub App infrastructure patterns (webhook handler, HMAC verification, GitHub API integration via PyGithub or the Octokit API).

---

## Complete File Structure

```
infracents/
├── .env.example                        # All environment variables with comments
├── .github/
│   └── workflows/
│       ├── ci.yml                      # Tests + lint on every PR
│       ├── deploy-backend.yml          # Deploy backend to Cloud Run on push to main
│       ├── deploy-frontend.yml         # Deploy frontend to Vercel on push to main
│       └── pricing-update.yml          # Scheduled workflow: refresh and commit pricing data
├── backend/                            # Python 3.11 / FastAPI backend
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory, router registration, lifespan
│   ├── config.py                       # Pydantic BaseSettings — all config from env vars
│   ├── Dockerfile                      # Multi-stage build for Cloud Run
│   ├── docker-compose.yml              # Local dev: PostgreSQL + Redis
│   ├── requirements.txt                # Production dependencies
│   ├── requirements-dev.txt            # Dev/test: pytest, ruff, coverage, httpx
│   ├── api/                            # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── webhooks.py                 # POST /webhooks/github — main GitHub App webhook endpoint
│   │   ├── dashboard.py                # GET /dashboard — cost trends, org overview, per-repo history
│   │   ├── billing.py                  # POST /billing/webhook — Stripe webhook handler
│   │   └── health.py                   # GET /health — liveness probe
│   ├── models/                         # Pydantic v2 data models
│   │   ├── __init__.py
│   │   ├── terraform.py                # TerraformPlan, ResourceChange, ParsedResourceConfig, ResourceAction
│   │   ├── pricing.py                  # PricingResult, ResourceEstimate, CostDelta, ConfidenceLevel
│   │   ├── github.py                   # WebhookPayload, PullRequestEvent, FileChange
│   │   └── billing.py                  # Subscription, Plan, BillingEvent
│   ├── services/                       # Business logic layer
│   │   ├── __init__.py
│   │   ├── terraform_parser.py         # Parse .tf files into ResourceChange objects (python-hcl2 + json)
│   │   ├── pricing_engine.py           # Orchestrates pricing lookups, calls AWS + GCP clients, aggregates
│   │   ├── cost_calculator.py          # Computes monthly cost delta from resource changes + pricing data
│   │   ├── github_service.py           # GitHub API: fetch PR files, post comments, update check runs
│   │   ├── cache_service.py            # Redis-backed cache for pricing API responses (1h TTL)
│   │   └── billing_service.py          # Stripe: customer creation, subscription management, plan limits
│   ├── pricing_data/                   # Cloud pricing data and resource type mappings
│   │   ├── __init__.py
│   │   ├── aws_pricing.py              # AWS Price List API client (queries pricing.us-east-1.amazonaws.com)
│   │   ├── gcp_pricing.py              # GCP Cloud Billing Catalog API client
│   │   └── resource_mappings.py        # Maps Terraform resource types to pricing API parameters
│   └── utils/                          # Shared utilities
│       ├── __init__.py
│       ├── formatting.py               # Markdown table generation for PR comment output
│       ├── rate_limiter.py             # Redis-backed rate limiting for webhook and API endpoints
│       └── security.py                 # HMAC-SHA256 webhook signature verification
├── frontend/                           # Next.js 14 cost dashboard
│   ├── next.config.js
│   ├── package.json
│   └── src/
│       ├── app/
│       │   ├── dashboard/
│       │   │   ├── page.tsx            # Org-level dashboard: repos, total spend, trend charts
│       │   │   └── [repo]/
│       │   │       └── page.tsx        # Per-repo dashboard: PR history, cost over time, resource breakdown
│       └── components/                 # React components (cost tables, trend charts, PR drill-downs)
├── database/
│   ├── schema.sql                      # Full PostgreSQL schema (tables: estimates, repos, installations, users)
│   ├── migrations/
│   │   └── 001_initial.sql             # Initial schema migration
│   └── seed.sql                        # Sample data for local dev
├── docs/                               # Documentation
│   ├── ARCHITECTURE.md                 # System design and data flow
│   ├── API.md                          # Endpoint documentation
│   ├── BUSINESS.md                     # Business model and pricing tiers
│   ├── CONTRIBUTING.md                 # Contributor guide
│   ├── DEPLOYMENT.md                   # Production deployment walkthrough
│   ├── DEVELOPMENT.md                  # Local setup and dev workflow
│   ├── PRICING-ENGINE.md               # How cost estimation works in detail
│   ├── SECURITY.md                     # Security model and threat analysis
│   └── diagrams/                       # Architecture diagrams (JPG)
│       ├── system-architecture.jpg
│       ├── request-flow.jpg
│       ├── pricing-engine.jpg
│       └── data-model.jpg
├── tests/                              # pytest test suite
├── CHANGELOG.md
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env`. Key variables grouped by component:

### GitHub App (required)
| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Numeric App ID from GitHub App settings page |
| `GITHUB_APP_PRIVATE_KEY` | PEM private key (escape `\n` for single-line) |
| `GITHUB_WEBHOOK_SECRET` | HMAC-SHA256 webhook secret (`openssl rand -hex 32`) |
| `GITHUB_APP_CLIENT_ID` | OAuth client ID (for Clerk GitHub OAuth flow) |
| `GITHUB_APP_CLIENT_SECRET` | OAuth client secret |

### Infrastructure (required)
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://...`) |
| `REDIS_URL` | Redis for pricing cache and rate limiting |

### Cloud Pricing (optional — falls back to cached pricing data)
| Variable | Description |
|---|---|
| `AWS_REGION` | Region for AWS Price List API endpoint (default: `us-east-1`) |
| `GCP_PROJECT_ID` | GCP project for authenticated Billing Catalog API calls |

### Auth and Billing (required for production)
| Variable | Description |
|---|---|
| `CLERK_SECRET_KEY` | Clerk JWT secret for dashboard auth |
| `CLERK_JWT_ISSUER` | Clerk issuer URL (e.g., `https://clerk.xxxxx.dev`) |
| `STRIPE_SECRET_KEY` | Stripe API key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_BUSINESS` / `STRIPE_PRICE_ENTERPRISE` | Stripe Price IDs |

### Monitoring (optional)
| Variable | Description |
|---|---|
| `SENTRY_DSN` | Sentry error tracking (production only) |

### Rate Limiting
| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_WEBHOOK` | 100 | Max webhook requests/minute per GitHub App installation |
| `RATE_LIMIT_API` | 60 | Max dashboard API requests/minute per user |

---

## How the GitHub App Works

### GitHub App Registration

InfraCents registers as a GitHub App with these permissions:
- **Repository contents:** Read (to fetch `.tf` files from PRs)
- **Pull requests:** Write (to post cost estimate comments)
- **Checks:** Write (optional, for check run status)

Subscribed to events: `pull_request` (opened, synchronize, reopened)

### Webhook Flow

```
Developer opens/updates a PR with .tf changes
      |
      v
GitHub sends POST to /webhooks/github
      |
      |- backend/utils/security.py: verify HMAC-SHA256 signature
      |   X-Hub-Signature-256 header vs computed HMAC of body
      |   If invalid -> 401, stop processing
      |
      |- Parse event type (X-GitHub-Event header)
      |   Only process: pull_request events
      |   Only process actions: opened, synchronize, reopened
      |
      |- Extract: repo name, PR number, installation ID, changed files
      |
      v
github_service.py::get_pr_terraform_files(repo, pr_number)
      |
      |- Authenticate as GitHub App installation
      |   (JWT signed with GITHUB_APP_PRIVATE_KEY -> exchange for installation token)
      |- Fetch list of files changed in the PR
      |- Filter to .tf files only
      |- Fetch file contents for changed .tf files
      |
      v
terraform_parser.py::parse_plan_json() or parse_tf_files()
      |
      |- Parse HCL using python-hcl2 (or JSON for .tf.json)
      |- Extract resource blocks with their type, name, and config
      |- Determine resource action: created | modified | deleted
      |- Return list of ResourceChange objects
      |
      v
pricing_engine.py::get_estimates(resource_changes)
      |
      |- For each ResourceChange:
      |   |- Look up Terraform resource type in resource_mappings.py
      |   |- Check Redis cache (key: f"price:{provider}:{resource_type}:{config_hash}")
      |   |- If cache miss: call AWS Price List API or GCP Billing Catalog API
      |   |- Store in Redis with 1h TTL
      |   |- Calculate monthly cost from pricing data + resource config
      |   |- Assign confidence level (HIGH/MEDIUM/LOW) based on data quality
      |
      v
cost_calculator.py::compute_delta(before_estimates, after_estimates)
      |
      |- Sum costs for added resources (net new monthly cost)
      |- Compute diff for modified resources (cost change only)
      |- Sum costs for removed resources (savings)
      |- Compute total net monthly delta
      |
      v
formatting.py::format_pr_comment(delta, estimates)
      |
      |- Generate Markdown table (resource, type, change, monthly cost)
      |- Add summary section (new/modified/removed totals, net change)
      |- Add confidence notice if any LOW confidence estimates
      |
      v
github_service.py::post_pr_comment(repo, pr_number, comment_body)
      |
      |- POST to GitHub API: /repos/{owner}/{repo}/issues/{pr_number}/comments
      |- If a previous InfraCents comment exists on this PR, update it (don't duplicate)
      |
      v
Store estimate record in PostgreSQL (for dashboard)
```

---

## How to Set Up Locally for Development

### Prerequisites
- Docker (for PostgreSQL + Redis)
- Python 3.11+
- Node.js 18+ (for dashboard)
- A GitHub account to create a test GitHub App

### Step 1: Clone and configure

```bash
git clone https://github.com/nirbhays/infracents.git
cd infracents
cp .env.example .env
```

Edit `.env` with at minimum:
- `DATABASE_URL=postgresql://infracents:infracents@localhost:5432/infracents`
- `REDIS_URL=redis://localhost:6379/0`
- Your GitHub App credentials (see Step 3)

### Step 2: Start infrastructure

```bash
cd backend
docker-compose up -d   # Starts PostgreSQL on :5432, Redis on :6379
```

Wait ~10 seconds for PostgreSQL to initialize, then:

```bash
psql $DATABASE_URL -f ../database/migrations/001_initial.sql
psql $DATABASE_URL -f ../database/seed.sql  # Optional: sample data
```

### Step 3: Create a test GitHub App

1. Go to https://github.com/settings/apps/new
2. Set name: `InfraCents-Dev-YourName`
3. Set homepage URL: `http://localhost:8000`
4. Set webhook URL: your ngrok URL (see below) + `/webhooks/github`
5. Generate a random webhook secret: `openssl rand -hex 32`
6. Permissions: Repository contents (read), Pull requests (write)
7. Subscribe to: Pull request events
8. Create the app, note the App ID
9. Generate a private key (downloads as `.pem` file)

### Step 4: Expose webhook endpoint

```bash
ngrok http 8000
# Copy the https:// URL and set it as the webhook URL in your GitHub App settings
```

Or use [smee.io](https://smee.io/) for a persistent URL during development.

### Step 5: Start the backend

```bash
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload --port 8000
```

API available at: http://localhost:8000
Swagger docs: http://localhost:8000/docs

### Step 6: Install the GitHub App on a test repo

1. Go to your GitHub App settings -> Install App
2. Install on a personal test repository
3. Create a PR in that repo with a `.tf` file
4. Watch the InfraCents comment appear on the PR

### Step 7: (Optional) Start the dashboard

```bash
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:3000
```

---

## How to Run Tests

```bash
# Install dev dependencies
pip install -r backend/requirements-dev.txt

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=backend --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_terraform_parser.py -v

# Run a specific test
python -m pytest tests/test_pricing_engine.py::test_aws_ec2_pricing -v
```

GitHub API calls and cloud pricing API calls are mocked in tests — no real credentials or API access needed.

---

## How to Add a New Supported Resource Type

The most common contribution is adding support for a new AWS or GCP Terraform resource type.

### Step 1: Add the resource mapping

```python
# backend/pricing_data/resource_mappings.py

RESOURCE_MAPPINGS = {
    # ... existing mappings ...

    # New resource: AWS ElastiCache Replication Group
    "aws_elasticache_replication_group": {
        "provider": "aws",
        "pricing_service": "AmazonElastiCache",
        "config_fields": {
            "node_type": "node_type",          # e.g., "cache.r6g.large"
            "num_cache_clusters": "num_cache_clusters",
            "engine": "engine",                # redis or memcached
        },
        "confidence": "HIGH",
    },
}
```

### Step 2: Implement pricing lookup in the provider client

```python
# backend/pricing_data/aws_pricing.py

async def get_elasticache_replication_group_price(
    self, config: dict
) -> PricingResult:
    """
    Query the AWS Price List API for ElastiCache replication group pricing.

    Args:
        config: Parsed Terraform resource config with node_type, engine, etc.
    Returns:
        PricingResult with hourly_cost and monthly_cost
    """
    node_type = config.get("node_type", "cache.t3.micro")
    engine = config.get("engine", "redis")
    num_nodes = config.get("num_cache_clusters", 1)

    # Query AWS Price List API
    filters = [
        {"Type": "TERM_MATCH", "Field": "cacheNodeType", "Value": node_type},
        {"Type": "TERM_MATCH", "Field": "cacheEngine", "Value": engine.capitalize()},
    ]
    price_data = await self._query_price_list("AmazonElastiCache", filters)
    hourly_price = self._extract_on_demand_price(price_data)

    return PricingResult(
        resource_type="aws_elasticache_replication_group",
        hourly_cost=hourly_price * num_nodes,
        monthly_cost=hourly_price * num_nodes * 730,
        confidence=ConfidenceLevel.HIGH,
        pricing_source="aws_price_list_api",
    )
```

### Step 3: Wire up in the pricing engine

```python
# backend/services/pricing_engine.py

# In the get_resource_estimate() method, add a case:
elif resource_type == "aws_elasticache_replication_group":
    result = await self.aws_client.get_elasticache_replication_group_price(config)
```

### Step 4: Add to the supported resources list in the README

Update the `## Supported Resources` table in `README.md`.

### Step 5: Add a test

```python
# tests/test_pricing_engine.py

async def test_elasticache_replication_group_pricing(pricing_engine, mock_aws_pricing):
    mock_aws_pricing.return_value = {"hourly_cost": 0.085}  # cache.r6g.large

    resource = ResourceChange(
        type="aws_elasticache_replication_group",
        name="sessions",
        action=ResourceAction.CREATE,
        config={"node_type": "cache.r6g.large", "num_cache_clusters": 2, "engine": "redis"},
    )

    estimate = await pricing_engine.get_estimates([resource])
    assert len(estimate) == 1
    assert estimate[0].monthly_cost == pytest.approx(0.085 * 2 * 730, rel=0.01)
    assert estimate[0].confidence == ConfidenceLevel.HIGH
```

---

## Key Coding Patterns

1. **HMAC verification is always first** — `backend/utils/security.py::verify_github_signature()` is called at the top of the webhook handler before any processing. It compares `X-Hub-Signature-256` against a locally computed HMAC-SHA256 of the raw request body. If it fails, return 401 immediately.

2. **GitHub authentication uses JWT + installation tokens** — The GitHub App authenticates with a short-lived JWT signed using `GITHUB_APP_PRIVATE_KEY`. That JWT is exchanged for an installation-specific access token (valid 1 hour) used for all API calls within a webhook handler lifecycle. `github_service.py` handles this rotation transparently.

3. **Pricing data is always cached** — `cache_service.py` wraps all pricing API calls with Redis caching using a 1h TTL (`REDIS_PRICE_CACHE_TTL`). Cache keys encode the resource type and config hash. Never call pricing APIs on every webhook — they rate-limit aggressively.

4. **PR comments are idempotent** — Before posting a new PR comment, `github_service.py` checks for an existing comment by InfraCents (identified by a marker string in the comment body). If found, it updates the existing comment via PATCH. This prevents comment spam on PRs with many commits.

5. **Resource confidence levels communicate uncertainty** — `ConfidenceLevel.HIGH` means an exact pricing match. `MEDIUM` means pricing with usage assumptions (e.g., S3 assumes 50GB/month). `LOW` means best-effort estimate. The PR comment always displays confidence levels so reviewers know how much to trust each estimate.

6. **Terraform parser handles both HCL and JSON** — `terraform_parser.py` detects `.tf.json` files and parses them as JSON, while `.tf` files use `python-hcl2`. The output is always normalized `ResourceChange` objects regardless of input format.

7. **The parser does not require a `terraform plan`** — InfraCents parses raw `.tf` source files directly from the PR diff. It does not need Terraform state, provider credentials, or a `terraform init`. This is the key design decision that enables zero-config setup.

8. **Async throughout** — FastAPI with async handlers, `asyncpg` for PostgreSQL, `aioredis` for Redis, `httpx.AsyncClient` for GitHub and pricing API calls.

9. **Pydantic v2 models everywhere** — All request/response shapes, database entity types, and service-layer data structures use Pydantic v2. Use `model_validate()` not `parse_obj()`.

10. **Linting: ruff** — configured in `pyproject.toml`. Run `ruff check backend/` and `ruff format backend/` before committing.

---

## Pricing Tiers

| Plan | Price | Repos | Estimates/mo | Key Features |
|---|---|---|---|---|
| **Free** | $0 | 3 | 100 | PR comments, AWS + GCP |
| **Pro** | $29/mo | 10 | Unlimited | Dashboard, Slack alerts, CSV export |
| **Business** | $99/mo | Unlimited | Unlimited | Custom resource mappings, team RBAC, PDF reports |
| **Enterprise** | Custom | Unlimited | Unlimited | SSO, self-hosted, SLA, audit logs |

Plan enforcement is in `billing_service.py` — it checks the current installation's plan before processing a webhook. If the free tier limit is exceeded, the comment is posted with a notice to upgrade instead of a cost estimate.

---

## Common Development Tasks

### Simulate a GitHub webhook locally

```bash
# Compute the HMAC signature
SECRET="your-webhook-secret"
BODY=$(cat tests/fixtures/pr_event.json)
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/.* //')

curl -X POST http://localhost:8000/webhooks/github \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/pr_event.json
```

### Check current pricing cache

```bash
redis-cli -u $REDIS_URL KEYS "price:*" | head -20
redis-cli -u $REDIS_URL TTL "price:aws:aws_instance:..."
```

### Force a pricing cache refresh

```bash
redis-cli -u $REDIS_URL FLUSHDB  # Clears all cache — pricing will re-fetch on next request
# Or clear just one resource type:
redis-cli -u $REDIS_URL DEL "price:aws:aws_instance:..."
```

### Test Terraform parsing locally

```python
# From the backend directory:
from services.terraform_parser import TerraformParser
import json

parser = TerraformParser()
resources = parser.parse_file("path/to/your.tf")
for r in resources:
    print(f"{r.action.value}: {r.type}.{r.name}")
    print(json.dumps(r.config, indent=2))
```

### Add a test fixture for a new resource type

Create a minimal `.tf` file in `tests/fixtures/terraform/` and a corresponding JSON fixture representing the expected pricing API response in `tests/fixtures/pricing/`. Both are referenced by tests in `tests/test_pricing_engine.py`.

---

## Architecture Summary

```
PR with .tf changes
      |
      v
POST /webhooks/github  (backend/api/webhooks.py)
      |
      |- verify HMAC-SHA256 (utils/security.py)
      |- filter: pull_request events only
      |
      v
github_service.py
      |
      |- authenticate as GitHub App installation (JWT -> installation token)
      |- fetch changed .tf files from PR
      |
      v
terraform_parser.py
      |
      |- parse HCL (python-hcl2) or JSON (.tf.json)
      |- extract ResourceChange objects (type, name, action, config)
      |
      v
pricing_engine.py
      |
      |- for each resource: check Redis cache
      |- cache miss -> aws_pricing.py or gcp_pricing.py -> pricing API
      |- store in Redis (1h TTL)
      |- return ResourceEstimate with monthly_cost + confidence
      |
      v
cost_calculator.py
      |
      |- compute net monthly delta
      |- separate added / modified / removed costs
      |
      v
formatting.py
      |
      |- render Markdown table + summary
      |
      v
github_service.py
      |
      |- post (or update) PR comment
      |- store estimate in PostgreSQL

Infrastructure:
  Cloud Run (backend) + Vercel (frontend)
  Supabase PostgreSQL + Upstash Redis
  Clerk (auth) + Stripe (billing) + Sentry (monitoring)
```
