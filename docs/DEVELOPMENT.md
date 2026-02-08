# Development Guide

This guide covers everything you need to set up a local development environment for InfraCents.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Repository Setup](#repository-setup)
3. [Backend Development](#backend-development)
4. [Frontend Development](#frontend-development)
5. [Database](#database)
6. [Environment Variables](#environment-variables)
7. [Testing](#testing)
8. [Debugging](#debugging)
9. [Common Tasks](#common-tasks)

---

## Prerequisites

### Required Software

| Software | Version | Installation |
|----------|---------|-------------|
| Python | 3.11+ | [python.org](https://python.org) or `pyenv` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) or `nvm` |
| Docker | 20+ | [docker.com](https://docker.com) |
| Docker Compose | v2+ | Included with Docker Desktop |
| Git | 2.30+ | [git-scm.com](https://git-scm.com) |
| Make | Any | Usually pre-installed (Linux/Mac), use `choco install make` on Windows |

### Optional (Recommended)

| Software | Purpose |
|----------|---------|
| `ngrok` | Expose local server for GitHub webhooks |
| `httpie` | Better HTTP client for testing APIs |
| `jq` | JSON processor for command line |
| VS Code | Recommended editor with Python and TypeScript extensions |

---

## Repository Setup

```bash
# Clone the repository
git clone https://github.com/your-org/infracents.git
cd infracents

# Copy environment template
cp .env.example .env

# Edit .env with your local configuration
# (See "Environment Variables" section below)
```

---

## Backend Development

### Initial Setup

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate it
# Linux/Mac:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis via Docker
docker-compose up -d

# Run database migrations
psql postgresql://infracents:infracents@localhost:5432/infracents \
  -f ../database/migrations/001_initial.sql

# Optionally seed the database
psql postgresql://infracents:infracents@localhost:5432/infracents \
  -f ../database/seed.sql
```

### Running the Backend

```bash
# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# The API is now available at http://localhost:8000
# API docs at http://localhost:8000/docs (Swagger UI)
# Alternative docs at http://localhost:8000/redoc
```

### Exposing Webhooks Locally

To receive GitHub webhooks on your local machine:

```bash
# Install ngrok
brew install ngrok  # or download from ngrok.com

# Start ngrok tunnel
ngrok http 8000

# Note the https URL, e.g., https://abc123.ngrok.io
# Update your GitHub App webhook URL to:
# https://abc123.ngrok.io/webhooks/github
```

### Backend Project Structure

```
backend/
├── main.py                 # FastAPI app entry point, middleware, startup/shutdown
├── config.py               # Configuration from environment variables
├── api/                    # Route handlers (thin layer, delegates to services)
│   ├── __init__.py
│   ├── webhooks.py         # POST /webhooks/github, POST /webhooks/stripe
│   ├── dashboard.py        # GET /api/dashboard/* endpoints
│   ├── billing.py          # GET/POST /api/billing/* endpoints
│   └── health.py           # GET /health, GET /health/ready
├── models/                 # Pydantic models (data validation & serialization)
│   ├── __init__.py
│   ├── terraform.py        # TerraformPlan, TerraformResource, ResourceChange
│   ├── pricing.py          # PricingResult, ResourceCost, PricingDimension
│   ├── github.py           # WebhookEvent, PullRequest, Installation
│   └── billing.py          # Subscription, CheckoutSession, Plan
├── services/               # Business logic (the "brain")
│   ├── __init__.py
│   ├── terraform_parser.py # Parse TF plan JSON → resource list
│   ├── pricing_engine.py   # Look up prices for resources
│   ├── cost_calculator.py  # Calculate cost deltas
│   ├── github_service.py   # GitHub API interactions
│   ├── billing_service.py  # Stripe subscription management
│   └── cache_service.py    # Redis caching abstraction
├── pricing_data/           # Cloud pricing data and fetchers
│   ├── __init__.py
│   ├── aws_pricing.py      # AWS Price List API client
│   ├── gcp_pricing.py      # GCP Billing Catalog client
│   └── resource_mappings.py # TF resource → pricing dimension mapping
├── utils/                  # Utility functions
│   ├── __init__.py
│   ├── formatting.py       # PR comment Markdown formatting
│   ├── security.py         # HMAC verification, JWT validation
│   └── rate_limiter.py     # Rate limiting implementation
├── requirements.txt        # Python dependencies (pinned versions)
├── Dockerfile              # Production Docker image
└── docker-compose.yml      # Local dev services (PostgreSQL + Redis)
```

---

## Frontend Development

### Initial Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev

# The frontend is now available at http://localhost:3000
```

### Frontend Project Structure

```
frontend/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── layout.tsx            # Root layout (Clerk, global styles)
│   │   ├── page.tsx              # Landing page (/)
│   │   ├── dashboard/
│   │   │   ├── page.tsx          # Dashboard overview (/dashboard)
│   │   │   ├── [repo]/
│   │   │   │   └── page.tsx      # Repo detail (/dashboard/:repo)
│   │   │   └── settings/
│   │   │       └── page.tsx      # Settings (/dashboard/settings)
│   │   └── api/                  # API routes (proxy to backend)
│   ├── components/               # Reusable React components
│   │   ├── Navbar.tsx
│   │   ├── Footer.tsx
│   │   ├── CostChart.tsx
│   │   ├── PRCostTable.tsx
│   │   └── PricingCard.tsx
│   └── lib/                      # Utility libraries
│       ├── api.ts                # Backend API client
│       ├── stripe.ts             # Stripe client
│       └── utils.ts              # Helper functions
├── public/                       # Static assets
├── package.json
├── next.config.js
├── tailwind.config.js
└── tsconfig.json
```

---

## Database

### Schema

The database schema is defined in `database/schema.sql`. Key tables:

| Table | Purpose |
|-------|---------|
| `organizations` | GitHub organizations that have installed InfraCents |
| `users` | Users within organizations (linked to Clerk) |
| `repositories` | Repositories being tracked |
| `scans` | Individual cost analysis runs |
| `cost_line_items` | Per-resource cost breakdown within a scan |
| `subscriptions` | Stripe subscription data |

### Migrations

```bash
# Run initial migration
psql $DATABASE_URL -f database/migrations/001_initial.sql

# Seed with development data
psql $DATABASE_URL -f database/seed.sql
```

### Connecting to Local Database

```bash
# Connect via psql
psql postgresql://infracents:infracents@localhost:5432/infracents

# Or use a GUI like pgAdmin, DBeaver, or TablePlus
```

---

## Environment Variables

### Complete Reference

Create a `.env` file in the project root (see `.env.example`):

```bash
# =============================================================================
# APPLICATION
# =============================================================================
ENVIRONMENT=development          # development | staging | production
APP_VERSION=0.1.0
LOG_LEVEL=debug                  # debug | info | warning | error
CORS_ORIGINS=http://localhost:3000  # Comma-separated allowed origins

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL=postgresql://infracents:infracents@localhost:5432/infracents
DB_POOL_SIZE=5                   # Connection pool size
DB_MAX_OVERFLOW=10               # Max overflow connections

# =============================================================================
# REDIS
# =============================================================================
REDIS_URL=redis://localhost:6379/0
REDIS_PRICE_CACHE_TTL=3600       # Price cache TTL in seconds (1 hour)

# =============================================================================
# GITHUB
# =============================================================================
GITHUB_APP_ID=123456
GITHUB_APP_CLIENT_ID=Iv1.xxxxxxxx
GITHUB_APP_CLIENT_SECRET=xxxxxxxx
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"

# =============================================================================
# STRIPE
# =============================================================================
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_BUSINESS=price_xxxxx
STRIPE_PRICE_ENTERPRISE=price_xxxxx

# =============================================================================
# CLERK
# =============================================================================
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx
CLERK_JWT_ISSUER=https://clerk.xxxxx.dev

# =============================================================================
# MONITORING (Optional for development)
# =============================================================================
SENTRY_DSN=
GRAFANA_API_KEY=
```

### Which Variables Are Required?

| Variable | Backend | Frontend | Required for Dev? |
|----------|---------|----------|-------------------|
| `DATABASE_URL` | ✅ | ❌ | Yes |
| `REDIS_URL` | ✅ | ❌ | Yes |
| `GITHUB_APP_ID` | ✅ | ❌ | For webhook testing |
| `GITHUB_WEBHOOK_SECRET` | ✅ | ❌ | For webhook testing |
| `GITHUB_PRIVATE_KEY` | ✅ | ❌ | For posting comments |
| `STRIPE_SECRET_KEY` | ✅ | ❌ | For billing testing |
| `CLERK_*` | ❌ | ✅ | For auth testing |
| `SENTRY_DSN` | ✅ | ❌ | No |

---

## Testing

### Running Tests

```bash
# Run all tests
cd backend
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_terraform_parser.py

# Run a specific test
pytest tests/test_terraform_parser.py::test_parse_aws_instance

# Run with coverage
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Run with parallel execution
pytest -n auto  # requires pytest-xdist
```

### Test Structure

```
tests/
├── conftest.py                 # Shared fixtures (db, redis, clients)
├── test_terraform_parser.py    # Terraform plan parsing (20+ resources)
├── test_pricing_engine.py      # Price lookup and calculation
├── test_cost_calculator.py     # Cost delta computation
├── test_webhooks.py            # Webhook handling integration tests
└── test_formatting.py          # PR comment formatting
```

### Writing Tests

Follow these conventions:
- Use `pytest` fixtures for shared setup
- Use `@pytest.mark.asyncio` for async tests
- Name test files `test_<module>.py`
- Name test functions `test_<behavior>`
- Use descriptive names: `test_parse_aws_instance_with_ebs_volumes`

---

## Debugging

### Backend Debugging

**VS Code Launch Configuration** (`.vscode/launch.json`):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

**Useful Debug Endpoints**:
- `GET /health` — Verify service is running and dependencies are connected
- `GET /docs` — Swagger UI for interactive API testing
- `GET /redoc` — ReDoc for API documentation

**Logging**:
```python
# The backend uses structured logging via Python's logging module
# Set LOG_LEVEL=debug in .env for verbose output
import logging
logger = logging.getLogger(__name__)
logger.debug("Processing webhook", extra={"pr_number": 42})
```

### Frontend Debugging

- Use React DevTools browser extension
- Use Next.js built-in error overlay
- Check browser console for API errors
- Use `console.log` or React DevTools profiler

### Database Debugging

```bash
# View recent scans
psql $DATABASE_URL -c "SELECT id, pr_number, cost_delta, status FROM scans ORDER BY created_at DESC LIMIT 10;"

# Check subscription status
psql $DATABASE_URL -c "SELECT o.name, s.plan, s.status, s.scans_used_this_period FROM subscriptions s JOIN organizations o ON o.id = s.org_id;"
```

---

## Common Tasks

### Using the Makefile

```bash
# Start all services
make dev

# Run tests
make test

# Lint code
make lint

# Format code
make format

# Build Docker image
make build

# Run database migrations
make migrate

# Seed database
make seed

# Clean up
make clean
```

### Adding a New Terraform Resource Type

1. Add the resource mapping in `backend/pricing_data/resource_mappings.py`
2. Add the pricing lookup logic in the appropriate provider file (`aws_pricing.py` or `gcp_pricing.py`)
3. Add unit tests in `tests/test_terraform_parser.py` and `tests/test_pricing_engine.py`
4. Update `docs/PRICING-ENGINE.md` with the new resource

### Adding a New API Endpoint

1. Create the route handler in the appropriate file under `backend/api/`
2. Create Pydantic models for request/response in `backend/models/`
3. Implement business logic in the appropriate service under `backend/services/`
4. Add tests
5. Update `docs/API.md`

### Updating Pricing Data

```bash
# Manually trigger a pricing data refresh
python -c "from pricing_data.aws_pricing import update_pricing_cache; import asyncio; asyncio.run(update_pricing_cache())"
```

---

## IDE Setup

### VS Code Extensions

| Extension | Purpose |
|-----------|---------|
| Python (ms-python) | Python language support |
| Pylance | Type checking |
| Black Formatter | Auto-formatting |
| ESLint | TypeScript linting |
| Tailwind CSS IntelliSense | Tailwind class suggestions |
| Prisma (if using Prisma) | DB schema support |
| Docker | Docker file support |

### VS Code Settings

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```
