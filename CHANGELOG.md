# Changelog

All notable changes to InfraCents will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-15

### Added
- Initial release of InfraCents
- GitHub App webhook handler for `pull_request` events
- Terraform plan JSON parser supporting 20+ resource types
- AWS pricing engine with Price List API integration
  - EC2 instances (on-demand, all instance families)
  - RDS instances (MySQL, PostgreSQL, Aurora)
  - S3 buckets (Standard, IA, Glacier storage classes)
  - Lambda functions (request + duration pricing)
  - Application Load Balancers
  - NAT Gateways
  - ECS Fargate tasks
  - ElastiCache clusters (Redis, Memcached)
  - DynamoDB tables (on-demand + provisioned)
  - EBS volumes (gp2, gp3, io1, io2)
  - CloudFront distributions
  - Route 53 hosted zones
  - SQS queues
  - SNS topics
  - Secrets Manager secrets
- GCP pricing engine with Cloud Billing Catalog API integration
  - Compute Engine instances
  - Cloud SQL instances
  - Cloud Storage buckets
  - Cloud Functions
  - GKE node pools
  - Cloud NAT gateways
  - Pub/Sub topics
  - Cloud Memorystore (Redis)
- PR comment formatter with beautiful Markdown output
- Cost delta calculation (additions, modifications, deletions)
- Redis caching layer for pricing data (1-hour TTL)
- PostgreSQL schema for historical cost tracking
- Next.js 14 web dashboard
  - Landing page with feature showcase and pricing
  - Organization overview dashboard
  - Per-repository cost history with charts
  - Settings page with billing management
- Stripe Billing integration (Free, Pro, Business, Enterprise tiers)
- Clerk authentication with GitHub OAuth
- Docker Compose local development environment
- Comprehensive test suite (pytest)
- CI/CD pipelines (GitHub Actions)
- Terraform infrastructure-as-code for production deployment
- Complete documentation suite

### Security
- HMAC-SHA256 webhook signature verification
- JWT token validation for API endpoints
- Minimal GitHub App permissions (read-only + PR comments)
- Rate limiting on all public endpoints
- No storage of cloud credentials or secrets
