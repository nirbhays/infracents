-- =============================================================================
-- InfraCents — Seed Data for Development
-- =============================================================================
-- Populates the database with sample data for local development and testing.

-- Sample organization
INSERT INTO organizations (id, github_org_id, name, slug, installation_id, is_active)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    '12345678',
    'Demo Organization',
    'demo-org',
    99999999,
    TRUE
) ON CONFLICT (id) DO NOTHING;

-- Sample user
INSERT INTO users (id, clerk_user_id, github_username, email, org_id, role)
VALUES (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'user_dev_001',
    'demo-developer',
    'dev@infracents.dev',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'owner'
) ON CONFLICT (id) DO NOTHING;

-- Sample repositories
INSERT INTO repositories (id, org_id, github_repo_id, full_name, name, default_branch)
VALUES
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '111111', 'demo-org/infrastructure', 'infrastructure', 'main'),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '222222', 'demo-org/platform', 'platform', 'main'),
    ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '333333', 'demo-org/services', 'services', 'main')
ON CONFLICT DO NOTHING;

-- Sample scans
INSERT INTO scans (id, repo_id, triggered_by, pr_number, pr_title, commit_sha, status, total_cost_before, total_cost_after, cost_delta, cost_delta_percent, created_at, completed_at)
VALUES
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a66', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 142, 'Add new RDS instance for analytics', 'abc123def456', 'completed', 1158.00, 1300.50, 142.50, 12.3, NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a77', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 89, 'Scale up ECS service to 4 tasks', 'def456ghi789', 'completed', 580.00, 667.20, 87.20, 15.0, NOW() - INTERVAL '3 hours', NOW() - INTERVAL '2 hours 59 minutes'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a88', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 256, 'Remove unused ElastiCache cluster', 'ghi789jkl012', 'completed', 430.00, 365.00, -65.00, -15.1, NOW() - INTERVAL '8 hours', NOW() - INTERVAL '7 hours 59 minutes')
ON CONFLICT DO NOTHING;

-- Sample cost line items
INSERT INTO cost_line_items (scan_id, resource_type, resource_name, resource_address, action, provider, monthly_cost_before, monthly_cost_after, cost_delta, confidence)
VALUES
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a66', 'aws_db_instance', 'analytics_db', 'aws_db_instance.analytics_db', 'create', 'aws', 0.00, 142.50, 142.50, 'high'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a77', 'aws_ecs_service', 'api_service', 'aws_ecs_service.api_service', 'update', 'aws', 36.00, 123.20, 87.20, 'high'),
    ('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a88', 'aws_elasticache_cluster', 'session_cache', 'aws_elasticache_cluster.session_cache', 'delete', 'aws', 65.00, 0.00, -65.00, 'high')
ON CONFLICT DO NOTHING;

-- Sample subscription (Free plan)
INSERT INTO subscriptions (org_id, plan, status, scan_limit, repo_limit, scans_used_this_period, current_period_start, current_period_end)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'free',
    'active',
    50,
    3,
    3,
    DATE_TRUNC('month', NOW()),
    DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
) ON CONFLICT (org_id) DO NOTHING;
