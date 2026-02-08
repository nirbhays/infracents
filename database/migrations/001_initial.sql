-- =============================================================================
-- InfraCents — Initial Migration (001)
-- =============================================================================
-- Creates all tables, indexes, and triggers for the InfraCents schema.
-- This file is idempotent (safe to run multiple times).

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Organizations
CREATE TABLE IF NOT EXISTS organizations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_org_id     TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    slug              TEXT NOT NULL UNIQUE,
    avatar_url        TEXT,
    installation_id   INTEGER UNIQUE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    settings          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_installation ON organizations(installation_id);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id     TEXT NOT NULL UNIQUE,
    github_username   TEXT NOT NULL,
    email             TEXT,
    avatar_url        TEXT,
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role              TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_clerk ON users(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_users_github ON users(github_username);

-- Repositories
CREATE TABLE IF NOT EXISTS repositories (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    github_repo_id    TEXT NOT NULL,
    full_name         TEXT NOT NULL,
    name              TEXT NOT NULL,
    default_branch    TEXT NOT NULL DEFAULT 'main',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    settings          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, github_repo_id)
);

CREATE INDEX IF NOT EXISTS idx_repos_org ON repositories(org_id);
CREATE INDEX IF NOT EXISTS idx_repos_full_name ON repositories(full_name);

-- Scans
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
    total_cost_before     DECIMAL(12, 2) DEFAULT 0,
    total_cost_after      DECIMAL(12, 2) DEFAULT 0,
    cost_delta            DECIMAL(12, 2) DEFAULT 0,
    cost_delta_percent    REAL DEFAULT 0,
    resource_breakdown    JSONB DEFAULT '{}',
    comment_id            BIGINT,
    processing_time_ms    INTEGER,
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at          TIMESTAMPTZ,
    UNIQUE(repo_id, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_scans_repo ON scans(repo_id);
CREATE INDEX IF NOT EXISTS idx_scans_pr ON scans(repo_id, pr_number);
CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);

-- Cost Line Items
CREATE TABLE IF NOT EXISTS cost_line_items (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id               UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    resource_type         TEXT NOT NULL,
    resource_name         TEXT NOT NULL,
    resource_address      TEXT,
    action                TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete', 'replace')),
    provider              TEXT NOT NULL CHECK (provider IN ('aws', 'gcp', 'azure')),
    monthly_cost_before   DECIMAL(12, 4) DEFAULT 0,
    monthly_cost_after    DECIMAL(12, 4) DEFAULT 0,
    cost_delta            DECIMAL(12, 4) DEFAULT 0,
    pricing_details       JSONB DEFAULT '{}',
    confidence            TEXT NOT NULL DEFAULT 'medium'
                          CHECK (confidence IN ('high', 'medium', 'low')),
    is_fallback           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_line_items_scan ON cost_line_items(scan_id);
CREATE INDEX IF NOT EXISTS idx_line_items_type ON cost_line_items(resource_type);

-- Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id                    UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    stripe_customer_id        TEXT UNIQUE,
    stripe_subscription_id    TEXT UNIQUE,
    plan                      TEXT NOT NULL DEFAULT 'free'
                              CHECK (plan IN ('free', 'pro', 'business', 'enterprise')),
    status                    TEXT NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'past_due', 'canceled', 'incomplete', 'trialing', 'unpaid')),
    scan_limit                INTEGER NOT NULL DEFAULT 50,
    repo_limit                INTEGER NOT NULL DEFAULT 3,
    scans_used_this_period    INTEGER NOT NULL DEFAULT 0,
    current_period_start      TIMESTAMPTZ,
    current_period_end        TIMESTAMPTZ,
    cancel_at_period_end      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_org ON subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id);

-- Updated At Trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DO $$ BEGIN
    CREATE TRIGGER update_organizations_updated_at
        BEFORE UPDATE ON organizations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_repositories_updated_at
        BEFORE UPDATE ON repositories
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_subscriptions_updated_at
        BEFORE UPDATE ON subscriptions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
