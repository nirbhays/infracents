# Deployment Guide

This guide walks you through deploying InfraCents to production using Google Cloud Run (backend), Vercel (frontend), Supabase (database), and Upstash (Redis cache).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Supabase Database Setup](#step-1-supabase-database-setup)
3. [Step 2: Upstash Redis Setup](#step-2-upstash-redis-setup)
4. [Step 3: GitHub App Setup](#step-3-github-app-setup)
5. [Step 4: Stripe Setup](#step-4-stripe-setup)
6. [Step 5: Clerk Authentication Setup](#step-5-clerk-authentication-setup)
7. [Step 6: Deploy Backend to Cloud Run](#step-6-deploy-backend-to-cloud-run)
8. [Step 7: Deploy Frontend to Vercel](#step-7-deploy-frontend-to-vercel)
9. [Step 8: Cloudflare DNS Setup](#step-8-cloudflare-dns-setup)
10. [Step 9: Verify Deployment](#step-9-verify-deployment)
11. [Step 10: Monitoring Setup](#step-10-monitoring-setup)

---

## Prerequisites

Before starting, ensure you have:

- **Google Cloud account** with billing enabled
- **Vercel account** (free tier is sufficient)
- **Supabase account** (free tier for dev, Pro for production)
- **Upstash account** (free tier for dev, Pay-as-you-go for production)
- **GitHub account** (for creating the GitHub App)
- **Stripe account** (for billing)
- **Clerk account** (for authentication)
- **Cloudflare account** (for DNS, free tier)
- **Domain name** (e.g., `infracents.dev`)

Tools required:
```bash
# Google Cloud CLI
gcloud --version  # v400+

# Docker
docker --version  # v20+

# Terraform
terraform --version  # v1.5+

# Node.js & npm
node --version  # v18+
npm --version   # v9+

# Vercel CLI
npx vercel --version
```

---

## Step 1: Supabase Database Setup

### 1.1 Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **"New Project"**
3. Configure:
   - **Name**: `infracents-prod`
   - **Database Password**: Generate a strong password (save this!)
   - **Region**: Choose closest to your users (e.g., `us-east-1`)
   - **Plan**: Free for testing, Pro ($25/mo) for production
4. Click **"Create new project"** and wait for provisioning (~2 minutes)

### 1.2 Run Database Migrations

1. Go to **SQL Editor** in the Supabase dashboard
2. Copy the contents of `database/migrations/001_initial.sql`
3. Paste and click **"Run"**
4. Verify tables were created in **Table Editor**

### 1.3 Note Connection Details

From **Settings > Database**, note:
```
Host:     db.<project-ref>.supabase.co
Port:     5432
Database: postgres
User:     postgres
Password: <your-password>
```

The full connection string:
```
postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

### 1.4 Enable Row Level Security (Optional but Recommended)

```sql
-- Enable RLS on all tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
```

---

## Step 2: Upstash Redis Setup

### 2.1 Create a Redis Database

1. Go to [upstash.com](https://upstash.com) and sign in
2. Click **"Create Database"**
3. Configure:
   - **Name**: `infracents-cache`
   - **Region**: Same region as your Cloud Run service
   - **Type**: Regional (lower latency) or Global (multi-region)
   - **TLS**: Enabled (required)
4. Click **"Create"**

### 2.2 Note Connection Details

From the database dashboard, note:
```
UPSTASH_REDIS_URL=rediss://default:<password>@<endpoint>.upstash.io:6379
```

---

## Step 3: GitHub App Setup

### 3.1 Create a GitHub App

1. Go to **GitHub Settings > Developer Settings > GitHub Apps**
2. Click **"New GitHub App"**
3. Configure:

**Basic Information**:
- **App name**: `InfraCents`
- **Description**: `Terraform cost estimation for pull requests`
- **Homepage URL**: `https://infracents.dev`

**Webhook**:
- **Webhook URL**: `https://api.infracents.dev/webhooks/github` (update after Cloud Run deploy)
- **Webhook secret**: Generate a random string: `openssl rand -hex 32`

**Permissions**:
| Permission | Access | Reason |
|-----------|--------|--------|
| Repository > Contents | Read | Fetch .tf files |
| Repository > Pull requests | Read & Write | Post cost comments |
| Repository > Metadata | Read | List repos |

**Events**:
- [x] Pull request
- [x] Installation

**Where can this GitHub App be installed?**: Any account

4. Click **"Create GitHub App"**

### 3.2 Generate a Private Key

1. Scroll to **Private keys** section
2. Click **"Generate a private key"**
3. Download the `.pem` file — you'll need this for the backend

### 3.3 Note App Details

```
GITHUB_APP_ID=<app-id>
GITHUB_APP_CLIENT_ID=<client-id>
GITHUB_APP_CLIENT_SECRET=<client-secret>
GITHUB_WEBHOOK_SECRET=<webhook-secret>
GITHUB_PRIVATE_KEY=<contents-of-pem-file>
```

---

## Step 4: Stripe Setup

### 4.1 Create Products and Prices

1. Go to [Stripe Dashboard > Products](https://dashboard.stripe.com/products)
2. Create four products:

**Free Plan** (no Stripe product needed — default)

**Pro Plan**:
- Name: `InfraCents Pro`
- Price: $29/month (recurring)
- Note the `price_id`: `price_xxxxx`

**Business Plan**:
- Name: `InfraCents Business`
- Price: $99/month (recurring)
- Note the `price_id`: `price_xxxxx`

**Enterprise Plan**:
- Name: `InfraCents Enterprise`
- Price: $249/month (recurring)
- Note the `price_id`: `price_xxxxx`

### 4.2 Configure Stripe Webhook

1. Go to **Developers > Webhooks**
2. Click **"Add endpoint"**
3. URL: `https://api.infracents.dev/webhooks/stripe`
4. Events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Note the **Signing secret**: `whsec_xxxxx`

### 4.3 Note Stripe Details

```
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_BUSINESS=price_xxxxx
STRIPE_PRICE_ENTERPRISE=price_xxxxx
```

---

## Step 5: Clerk Authentication Setup

### 5.1 Create a Clerk Application

1. Go to [clerk.com](https://clerk.com) and sign in
2. Create a new application
3. Enable **GitHub** as a social connection
4. Configure redirect URLs:
   - `https://infracents.dev/dashboard`
   - `https://infracents.dev/sign-in`
   - `https://infracents.dev/sign-up`

### 5.2 Note Clerk Details

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx
CLERK_SECRET_KEY=sk_live_xxxxx
CLERK_WEBHOOK_SECRET=whsec_xxxxx  (if using Clerk webhooks)
```

---

## Step 6: Deploy Backend to Cloud Run

### 6.1 Set Up Google Cloud Project

```bash
# Create project
gcloud projects create infracents-prod --name="InfraCents"

# Set as active project
gcloud config set project infracents-prod

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

### 6.2 Store Secrets

```bash
# Store each secret in Secret Manager
echo -n "$DATABASE_URL" | gcloud secrets create DATABASE_URL --data-file=-
echo -n "$REDIS_URL" | gcloud secrets create REDIS_URL --data-file=-
echo -n "$GITHUB_WEBHOOK_SECRET" | gcloud secrets create GITHUB_WEBHOOK_SECRET --data-file=-
echo -n "$GITHUB_PRIVATE_KEY" | gcloud secrets create GITHUB_PRIVATE_KEY --data-file=-
echo -n "$STRIPE_SECRET_KEY" | gcloud secrets create STRIPE_SECRET_KEY --data-file=-
echo -n "$STRIPE_WEBHOOK_SECRET" | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
```

### 6.3 Build and Push Docker Image

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create infracents \
  --repository-format=docker \
  --location=us-central1

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push
cd backend
docker build -t us-central1-docker.pkg.dev/infracents-prod/infracents/api:latest .
docker push us-central1-docker.pkg.dev/infracents-prod/infracents/api:latest
```

### 6.4 Deploy to Cloud Run

```bash
gcloud run deploy infracents-api \
  --image=us-central1-docker.pkg.dev/infracents-prod/infracents/api:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=100 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60 \
  --concurrency=80 \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,GITHUB_WEBHOOK_SECRET=GITHUB_WEBHOOK_SECRET:latest,GITHUB_PRIVATE_KEY=GITHUB_PRIVATE_KEY:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest" \
  --set-env-vars="ENVIRONMENT=production,GITHUB_APP_ID=xxxxx"
```

### 6.5 Note the Cloud Run URL

```
Service URL: https://infracents-api-xxxxx-uc.a.run.app
```

Update your GitHub App webhook URL to point to:
```
https://infracents-api-xxxxx-uc.a.run.app/webhooks/github
```

(Or use a custom domain — see Step 8)

---

## Step 7: Deploy Frontend to Vercel

### 7.1 Deploy via Vercel CLI

```bash
cd frontend
npx vercel --prod
```

### 7.2 Configure Environment Variables in Vercel

Go to **Vercel Dashboard > Project Settings > Environment Variables** and add:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx
CLERK_SECRET_KEY=sk_live_xxxxx
NEXT_PUBLIC_API_URL=https://api.infracents.dev
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
```

### 7.3 Configure Custom Domain

1. In Vercel, go to **Domains**
2. Add `infracents.dev`
3. Follow the DNS configuration instructions

---

## Step 8: Cloudflare DNS Setup

### 8.1 Add Domain to Cloudflare

1. Add `infracents.dev` to Cloudflare
2. Update nameservers at your domain registrar

### 8.2 Configure DNS Records

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| CNAME | `@` | `cname.vercel-dns.com` | DNS only |
| CNAME | `api` | `infracents-api-xxxxx-uc.a.run.app` | Proxied |
| TXT | `@` | `v=spf1 include:_spf.google.com ~all` | - |

### 8.3 Configure SSL

- SSL/TLS mode: **Full (strict)**
- Always Use HTTPS: **On**
- Minimum TLS Version: **1.2**

---

## Step 9: Verify Deployment

### 9.1 Health Check

```bash
curl https://api.infracents.dev/health
# Should return: {"status": "healthy", ...}
```

### 9.2 Test Webhook

```bash
# Use GitHub's webhook delivery page to redeliver a test event
# Or create a test PR with .tf changes
```

### 9.3 Test Frontend

1. Navigate to `https://infracents.dev`
2. Sign in with GitHub via Clerk
3. Verify dashboard loads

---

## Step 10: Monitoring Setup

### 10.1 Sentry

1. Create a Sentry project for Python
2. Add `SENTRY_DSN` to Cloud Run environment variables
3. The backend automatically initializes Sentry via the `sentry-sdk` package

### 10.2 Grafana Cloud

1. Create a Grafana Cloud account
2. Set up a Prometheus data source pointing to Cloud Run metrics
3. Import the InfraCents dashboard template (coming soon)

### 10.3 Cloud Run Monitoring

Google Cloud Run provides built-in monitoring:
- Request count and latency (Cloud Monitoring)
- Error rate and logs (Cloud Logging)
- Instance count and CPU/memory usage

---

## Using Terraform for Deployment

Instead of manual steps, you can use the Terraform configurations in `infra/terraform/`:

```bash
cd infra/terraform

# Initialize
terraform init

# Plan
terraform plan -var-file=prod.tfvars

# Apply
terraform apply -var-file=prod.tfvars
```

See `infra/terraform/variables.tf` for required variables.

---

## Troubleshooting

### Backend not receiving webhooks
1. Check the GitHub App webhook URL is correct
2. Verify the webhook secret matches
3. Check Cloud Run logs: `gcloud run services logs read infracents-api`

### Database connection errors
1. Verify the `DATABASE_URL` secret is correct
2. Check Supabase is running and accessible
3. Ensure Cloud Run can reach Supabase (no IP restrictions)

### Redis connection errors
1. Verify the `REDIS_URL` secret is correct
2. Check Upstash is running
3. Ensure TLS is enabled in the connection string (`rediss://`)

### Frontend authentication issues
1. Verify Clerk keys are set in Vercel
2. Check redirect URLs match your domain
3. Clear browser cookies and retry

### Stripe webhook failures
1. Check the webhook signing secret matches
2. Verify the endpoint URL is correct
3. Check Stripe webhook logs for error details
