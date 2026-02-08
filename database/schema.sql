-- =============================================================================
-- InfraCents Database Schema
-- =============================================================================
-- Complete PostgreSQL schema for the InfraCents cost estimation platform.
-- Compatible with Supabase (PostgreSQL 15+).
--
-- Tables:
--   organizations  — GitHub orgs that installed the app
--   users          — Users within organizations
--   repositories   — Tracked repositories
--   scans          — Individual cost analysis runs
--   cost_line_items — Per-resource cost breakdown
--   subscriptions  — Stripe billing subscriptions

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Organizations
-- =============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_org_id     TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    slug              TEXT NOT NULL UNIQUE,
    avatar_url        TEXT,
    installation_id   INTEGER UNIQUE,          -- GitHub App installation ID
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    settings          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_organizations_installation ON organizations(installation_id);
CREATE INDEX idx_organizations_slug ON organizations(slug);

-- =============================================================================
-- Users
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id     TEXT NOT NULL UNIQUE,     -- Clerk user ID
    github_username   TEXT NOT NULL,
    email             TEXT,
    avatar_url        TEXT,
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role              TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_users_clerk ON users(clerk_user_id);
CREATE INDEX idx_users_github ON users(github_username);

-- =============================================================================
-- Repositories
-- =============================================================================
CREATE TABLE IF NOT EXISTS repositories (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    github_repo_id    TEXT NOT NULL,
    full_name         TEXT NOT NULL,            -- e.g., "myorg/infrastructure"
    name              TEXT NOT NULL,            -- e.g., "infrastructure"
    default_branch    TEXT NOT NULL DEFAULT 'main',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    settings          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(org_id, github_repo_id)
);

CREATE INDEX idx_repos_org ON repositories(org_id);
CREATE INDEX idx_repos_full_name ON repositories(full_name);

-- =============================================================================
-- Scans
-- =============================================================================
-- Each scan represents one cost analysis of a pull request.
CREATE TABLE IF NOT EXISTS scans (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id               UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    triggered_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    pr_number             INTEGER NOT NULL,
    pr_title              TEXT,
    commit_sha            TEXT NOT NULL,
    base_sha              TEXT,
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

    -- Cost summary
    total_cost_before     DECIMAL(12, 2) DEFAULT 0,
    total_cost_after      DECIMAL(12, 2) DEFAULT 0,
    cost_delta            DECIMAL(12, 2) DEFAULT 0,
    cost_delta_percent    REAL DEFAULT 0,

    -- Resource breakdown (denormalized for fast reads)
    resource_breakdown    JSONB DEFAULT '{}',

    -- GitHub comment tracking
    comment_id            BIGINT,                -- GitHub comment ID (for updating)

    -- Metadata
    processing_time_ms    INTEGER,               -- How long the scan took
    error_message         TEXT,                   -- Error details if status = 'failed'

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at          TIMESTAMPTZ,

    UNIQUE(repo_id, commit_sha)
);

CREATE INDEX idx_scans_repo ON scans(repo_id);
CREATE INDEX idx_scans_pr ON scans(repo_id, pr_number);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_scans_created ON scans(created_at DESC);

-- =============================================================================
-- Cost Line Items
-- =============================================================================
-- Per-resource cost breakdown within a scan.
CREATE TABLE IF NOT EXISTS cost_line_items (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id               UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    resource_type         TEXT NOT NULL,           -- e.g., "aws_instance"
    resource_name         TEXT NOT NULL,           -- e.g., "web_server"
    resource_address      TEXT,                    -- e.g., "aws_instance.web_server"
    action                TEXT NOT NULL             -- create, update, delete, replace
                          CHECK (action IN ('create', 'update', 'delete', 'replace')),
    provider              TEXT NOT NULL             -- aws, gcp
                          CHECK (provider IN ('aws', 'gcp', 'azure')),

    -- Cost data
    monthly_cost_before   DECIMAL(12, 4) DEFAULT 0,
    monthly_cost_after    DECIMAL(12, 4) DEFAULT 0,
    cost_delta            DECIMAL(12, 4) DEFAULT 0,

    -- Pricing details
    pricing_details       JSONB DEFAULT '{}',      -- Dimensions, unit prices, etc.
    confidence            TEXT NOT NULL DEFAULT 'medium'
                          CHECK (confidence IN ('high', 'medium', 'low')),
    is_fallback           BOOLEAN NOT NULL DEFAULT FALSE,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_line_items_scan ON cost_line_items(scan_id);
CREATE INDEX idx_line_items_type ON cost_line_items(resource_type);
CREATE INDEX idx_line_items_provider ON cost_line_items(provider);

-- =============================================================================
-- Subscriptions
-- =============================================================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id                    UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    stripe_customer_id        TEXT UNIQUE,
    stripe_subscription_id    TEXT UNIQUE,
    plan                      TEXT NOT NULL DEFAULT 'free'
                              CHECK (plan IN ('free', 'pro', 'business', 'enterprise')),
    status                    TEXT NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'past_due', 'canceled', 'incomplete', 'trialing', 'unpaid')),

    -- Usage tracking
    scan_limit                INTEGER NOT NULL DEFAULT 50,
    repo_limit                INTEGER NOT NULL DEFAULT 3,
    scans_used_this_period    INTEGER NOT NULL DEFAULT 0,

    -- Billing period
    current_period_start      TIMESTAMPTZ,
    current_period_end        TIMESTAMPTZ,
    cancel_at_period_end      BOOLEAN NOT NULL DEFAULT FALSE,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_org ON subscriptions(org_id);
CREATE INDEX idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id);
CREATE INDEX idx_subscriptions_stripe_sub ON subscriptions(stripe_subscription_id);

-- =============================================================================
-- Updated At Trigger
-- =============================================================================
-- Automatically update the updated_at column on row changes.
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_repositories_updated_at
    BEFORE UPDATE ON repositories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
