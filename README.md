<p align="center">
  <img src="docs/assets/logo.png" alt="InfraCents Logo" width="100" />
</p>

<h1 align="center">InfraCents</h1>

<p align="center">
  <b>Terraform cost estimates on every pull request. Automatically.</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js 14" />
  <a href="#contributing"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome" /></a>
</p>

<p align="center">
  <a href="#demo">Demo</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="#quick-start">Quick Start</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="#features">Features</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="#architecture">Architecture</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="#supported-resources">Resources</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="#contributing">Contributing</a>
</p>

---

InfraCents is an open-source GitHub App that posts real-time cloud cost estimates directly on your pull requests. It parses your Terraform changes, queries live pricing APIs from AWS and GCP, and tells your team exactly how much a PR will cost -- before it merges.

No CLI tools to install. No CI pipelines to configure. Install the app, open a PR, and get cost visibility in seconds.

## Why InfraCents?

| | Before InfraCents | After InfraCents |
|---|---|---|
| **Cost visibility** | Merge first, discover costs on the monthly bill | Know exactly what every PR will cost before it ships |
| **Review process** | Reviewers guess at infrastructure cost impact | Every reviewer sees a clear cost breakdown inline |
| **Budget control** | Overspend detected weeks after deployment | Cost regressions caught at code review time |
| **Setup effort** | Install CLI tools, configure CI, manage API keys | One-click GitHub App install, zero config |

---

## Demo

When a pull request modifies `.tf` files, InfraCents automatically posts a comment like this:

```
## InfraCents Cost Estimate

### This PR will increase monthly costs by ~$142.50/mo (+12.3%)

| Resource                          | Type         | Change   | Monthly Cost |
|-----------------------------------|--------------|----------|-------------:|
| aws_instance.api_server           | EC2          | + added  |      $62.00  |
| aws_db_instance.primary           | RDS          | ~ modified |    +$45.50  |
| aws_lb.public                     | ALB          | + added  |      $22.00  |
| aws_s3_bucket.logs                | S3           | + added  |       $2.30  |
| aws_elasticache_cluster.sessions  | ElastiCache  | + added  |      $12.50  |
| aws_nat_gateway.main              | NAT Gateway  | - removed |     -$1.80  |

**Summary**
  New resources:      4 (+$98.80/mo)
  Modified resources: 1 (+$45.50/mo)
  Removed resources:  1 (-$1.80/mo)
  Net change:         +$142.50/mo

  AWS: +$142.50 | GCP: $0.00
  Confidence: HIGH for 5/6 resources

> Powered by InfraCents | Docs | Dashboard
```

No CLI. No Terraform plan uploads. It just works.

---

## Quick Start

### Use InfraCents (hosted)

1. **Install the GitHub App** on your repository (one-click setup)
2. **Open a pull request** that adds or modifies `.tf` files
3. **Get cost estimates** posted automatically as a PR comment

That's it. No API keys, no CI changes, no config files.

### Run locally (self-hosted)

```bash
# 1. Clone and configure
git clone https://github.com/your-org/infracents.git
cd infracents
cp .env.example .env          # Edit with your GitHub App credentials

# 2. Start everything with Docker
cd backend
docker-compose up -d          # Starts PostgreSQL, Redis, and the API

# 3. Run database migrations
psql $DATABASE_URL -f ../database/migrations/001_initial.sql

# 4. Start the backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 5. Start the frontend (in a new terminal)
cd frontend
npm install && npm run dev
```

Then follow the [Deployment Guide](docs/DEPLOYMENT.md) to register your GitHub App and configure webhooks.

---

## Features

<table>
<tr>
<td width="50%">

### Automated PR Comments
Every PR with Terraform changes gets an automatic cost breakdown: per-resource costs, total monthly delta, percentage change, and provider split.

</td>
<td width="50%">

### Multi-Cloud Pricing Engine
Real-time pricing from official AWS Price List and GCP Billing Catalog APIs. 25+ resource types across both clouds with hourly cache refresh via Redis.

</td>
</tr>
<tr>
<td width="50%">

### Web Dashboard
Track cost trends over time across all repositories. Organization-level overviews, per-repo history with charts, and PR-level drill-downs with CSV export.

</td>
<td width="50%">

### Security-First Design
Minimal GitHub permissions (read-only repo + PR comments). Webhook signature verification via HMAC-SHA256. No secrets stored -- works with `.tf` files only.

</td>
</tr>
</table>

---

## Architecture

```
                        Pull Request (.tf changes)
                                  |
                                  v
                    +----------------------------+
                    |     GitHub Webhook          |
                    |   (pull_request event)      |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    |    InfraCents API           |
                    |    (FastAPI / Cloud Run)    |
                    +---+--------+----------+----+
                        |        |          |
               +--------+   +---+---+   +--+--------+
               v             v           v
         +-----------+ +-----------+ +-----------+
         | Terraform | | AWS Price | | GCP Price |
         | Parser    | | List API  | | Catalog   |
         +-----------+ +-----------+ +-----------+
               |             |           |
               +--------+----+----+------+
                        |         |
                        v         v
              +----------------+  +----------------+
              | Cost Engine    |  | Redis Cache    |
              | (calc delta)   |  | (pricing data) |
              +-------+--------+  +----------------+
                      |
            +---------+---------+
            v                   v
   +----------------+  +----------------+
   | PR Comment     |  | Dashboard      |
   | (GitHub API)   |  | (Next.js 14)   |
   +----------------+  +-------+--------+
                                |
                                v
                       +----------------+
                       | PostgreSQL     |
                       | (scan history) |
                       +----------------+
```

**Tech stack:** Python 3.11 / FastAPI on Cloud Run, Next.js 14 on Vercel, PostgreSQL via Supabase, Redis via Upstash, Auth via Clerk, Payments via Stripe.

For the full deep-dive, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Supported Resources

### AWS (15 resource types)

| Resource | Terraform Type | Confidence |
|----------|---------------|:----------:|
| EC2 Instance | `aws_instance` | High |
| RDS Database | `aws_db_instance` | High |
| S3 Bucket | `aws_s3_bucket` | Medium |
| Lambda Function | `aws_lambda_function` | Medium |
| Load Balancer (ALB/NLB) | `aws_lb` | High |
| NAT Gateway | `aws_nat_gateway` | Medium |
| ECS Fargate Service | `aws_ecs_service` | High |
| ElastiCache Cluster | `aws_elasticache_cluster` | High |
| DynamoDB Table | `aws_dynamodb_table` | Medium |
| EBS Volume | `aws_ebs_volume` | High |
| CloudFront Distribution | `aws_cloudfront_distribution` | Low |
| Route 53 Hosted Zone | `aws_route53_zone` | High |
| SQS Queue | `aws_sqs_queue` | Low |
| SNS Topic | `aws_sns_topic` | Low |
| Secrets Manager | `aws_secretsmanager_secret` | High |

### GCP (10 resource types)

| Resource | Terraform Type | Confidence |
|----------|---------------|:----------:|
| Compute Engine VM | `google_compute_instance` | High |
| Cloud SQL Instance | `google_sql_database_instance` | High |
| Cloud Storage Bucket | `google_storage_bucket` | Medium |
| Cloud Function | `google_cloudfunctions_function` | Medium |
| GKE Node Pool | `google_container_node_pool` | High |
| Cloud NAT Gateway | `google_compute_router_nat` | Medium |
| Pub/Sub Topic | `google_pubsub_topic` | Low |
| Memorystore Redis | `google_redis_instance` | High |
| Persistent Disk | `google_compute_disk` | High |
| Static IP Address | `google_compute_address` | High |

> **Confidence levels:** *High* = exact API pricing match. *Medium* = pricing with usage estimates. *Low* = best-effort estimate based on typical usage patterns.

---

## Comparison with Alternatives

| | **InfraCents** | **Infracost** | **env0** | **Spacelift** |
|---|:---:|:---:|:---:|:---:|
| **Open source** | Yes (MIT) | Yes (Apache 2.0) | No | No |
| **Setup time** | < 2 min | ~15 min | ~30 min | ~30 min |
| **GitHub App (one-click)** | Yes | No (CI required) | Yes | Yes |
| **No CLI required** | Yes | No | Yes | Yes |
| **PR cost comments** | Yes | Yes | Yes | Yes |
| **Web dashboard** | Yes | Paid tier | Yes | Yes |
| **AWS support** | 15 resources | 100+ resources | Full | Full |
| **GCP support** | 10 resources | 70+ resources | Full | Full |
| **Azure support** | Roadmap | Yes | Yes | Yes |
| **Self-hostable** | Yes | Yes | No | No |
| **Free tier** | Generous | Community edition | Limited trial | Limited trial |
| **Pricing** | Free / $29 / $99 | Free / $50+ | Custom | Custom |

**When to choose InfraCents:** You want a lightweight, self-hostable solution with zero-config GitHub App setup and you primarily use AWS/GCP. If you need 100+ resource types or Azure support today, Infracost is the more mature choice.

---

## Project Structure

```
infracents/
  backend/                     Python/FastAPI backend
    api/                       Route handlers
    models/                    Pydantic data models
    services/                  Business logic (parser, pricing, GitHub)
    pricing_data/              Cloud pricing data & resource mappings
    main.py                    Application entry point
    Dockerfile                 Production container
    docker-compose.yml         Local dev (Postgres + Redis)
  frontend/                    Next.js 14 frontend
    src/app/                   App Router pages
    src/components/            React components
    src/lib/                   Utility libraries
  database/                    SQL schemas & migrations
  infra/                       Terraform IaC for deployment
  tests/                       Python test suite
  docs/                        Documentation
  .github/workflows/           CI/CD pipelines
```

---

## Contributing

Contributions are welcome and appreciated. Whether it is a bug fix, new resource type support, documentation improvement, or feature idea -- we would love your help.

**Getting started:**

1. Fork the repository and create your branch from `main`
2. Follow the [Development Guide](docs/DEVELOPMENT.md) for local setup
3. Make your changes and add tests
4. Submit a pull request

**Good first contributions:**

- Add support for a new AWS or GCP resource type (see `backend/pricing_data/resource_mappings.py`)
- Improve cost estimate accuracy for existing resources
- Add unit tests for the pricing engine
- Improve documentation

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full contributor guide, code style, and PR process.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design and data flow |
| [API Reference](docs/API.md) | Endpoint documentation |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment walkthrough |
| [Development Guide](docs/DEVELOPMENT.md) | Local setup and dev workflow |
| [Pricing Engine](docs/PRICING-ENGINE.md) | How cost estimation works |
| [Security](docs/SECURITY.md) | Security model and threat analysis |
| [Contributing](docs/CONTRIBUTING.md) | Contributor guide |

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <a href="docs/ARCHITECTURE.md">Architecture</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="docs/API.md">API Reference</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="docs/DEPLOYMENT.md">Deployment</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;
  <a href="docs/CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <sub>Built for DevOps teams tired of surprise cloud bills.</sub>
</p>
