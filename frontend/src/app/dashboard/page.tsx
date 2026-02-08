'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import Link from 'next/link';
import { CostChart } from '@/components/CostChart';
import { PRCostTable } from '@/components/PRCostTable';
import { apiClient } from '@/lib/api';

interface DashboardData {
  org: { id: string; name: string; slug: string };
  summary: {
    total_scans: number;
    total_cost_delta: number;
    avg_cost_per_pr: number;
    repos_active: number;
    cost_trend: string;
  };
  cost_by_day: Array<{ date: string; total_delta: number; scan_count: number }>;
  top_repos: Array<{
    repo_id: string;
    full_name: string;
    total_delta: number;
    scan_count: number;
    last_scan: string;
  }>;
  recent_scans: Array<{
    scan_id: string;
    repo_name: string;
    pr_number: number;
    pr_title: string;
    cost_delta: number;
    cost_delta_percent: number;
    status: string;
    created_at: string;
  }>;
}

/**
 * Dashboard Overview Page
 *
 * Shows the organization-level cost overview with:
 * - Key metrics (total scans, cost delta, active repos)
 * - Cost trend chart
 * - Top repositories by cost impact
 * - Recent scan activity
 */
export default function DashboardPage() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [period, setPeriod] = useState<string>('30d');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      if (!isLoaded || !isSignedIn) return;

      try {
        setLoading(true);
        const token = await getToken();
        const result = await apiClient.getDashboardOverview(token || '', period);
        setData(result);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [isLoaded, isSignedIn, getToken, period]);

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-500">Please sign in to view your dashboard.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-500">No data available. Install InfraCents on a repository to get started.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{data.org.name}</h1>
          <p className="mt-1 text-sm text-gray-500">Organization cost overview</p>
        </div>
        <div className="flex items-center gap-2">
          {['7d', '30d', '90d', '1y'].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                period === p
                  ? 'bg-brand-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Scans"
          value={data.summary.total_scans.toString()}
          icon="🔍"
        />
        <MetricCard
          label="Total Cost Delta"
          value={`$${data.summary.total_cost_delta.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          icon="💰"
          trend={data.summary.cost_trend}
        />
        <MetricCard
          label="Avg. Cost per PR"
          value={`$${data.summary.avg_cost_per_pr.toFixed(2)}`}
          icon="📊"
        />
        <MetricCard
          label="Active Repos"
          value={data.summary.repos_active.toString()}
          icon="📁"
        />
      </div>

      {/* Cost Trend Chart */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900">Cost Trend</h2>
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-6">
          <CostChart data={data.cost_by_day} period={period as any} />
        </div>
      </div>

      {/* Two-column layout: Top Repos + Recent Scans */}
      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Top Repositories */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Top Repositories</h2>
          <div className="mt-4 space-y-3">
            {data.top_repos.map((repo) => (
              <Link
                key={repo.repo_id}
                href={`/dashboard/${repo.full_name}`}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:border-brand-300 hover:shadow-sm transition-all"
              >
                <div>
                  <p className="font-medium text-gray-900">{repo.full_name}</p>
                  <p className="mt-0.5 text-xs text-gray-500">{repo.scan_count} scans</p>
                </div>
                <div className="text-right">
                  <p className={`font-semibold ${repo.total_delta >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {repo.total_delta >= 0 ? '+' : ''}${repo.total_delta.toFixed(2)}
                  </p>
                  <p className="text-xs text-gray-500">total delta</p>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent Scans */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Recent Scans</h2>
          <div className="mt-4">
            <PRCostTable scans={data.recent_scans} />
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  trend,
}: {
  label: string;
  value: string;
  icon: string;
  trend?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        {trend && (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              trend === 'increasing'
                ? 'bg-red-50 text-red-700'
                : trend === 'decreasing'
                ? 'bg-green-50 text-green-700'
                : 'bg-gray-50 text-gray-700'
            }`}
          >
            {trend === 'increasing' ? '↑ Increasing' : trend === 'decreasing' ? '↓ Decreasing' : '→ Stable'}
          </span>
        )}
      </div>
      <p className="mt-3 text-2xl font-bold text-gray-900">{value}</p>
      <p className="mt-1 text-sm text-gray-500">{label}</p>
    </div>
  );
}
