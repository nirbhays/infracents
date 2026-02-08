'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import { CostChart } from '@/components/CostChart';
import { PRCostTable } from '@/components/PRCostTable';
import { apiClient } from '@/lib/api';

/**
 * Repository Detail Page
 *
 * Shows cost history and PR scan details for a specific repository.
 * Accessible at /dashboard/[org]/[repo]
 */
export default function RepoDetailPage() {
  const params = useParams();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [data, setData] = useState<any>(null);
  const [period, setPeriod] = useState('30d');
  const [loading, setLoading] = useState(true);

  // The repo param captures the full path: org/repo
  const repoSlug = Array.isArray(params.repo) ? params.repo.join('/') : params.repo;

  useEffect(() => {
    async function fetchData() {
      if (!isLoaded || !isSignedIn || !repoSlug) return;

      try {
        setLoading(true);
        const token = await getToken();
        const result = await apiClient.getRepoDetail(token || '', repoSlug, period);
        setData(result);
      } catch (error) {
        console.error('Failed to fetch repo data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [isLoaded, isSignedIn, getToken, repoSlug, period]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-500">Loading repository data...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-500">Repository not found or no data available.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <a href="/dashboard" className="hover:text-brand-600">Dashboard</a>
            <span>/</span>
            <span>{data.repo.full_name}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{data.repo.full_name}</h1>
          <p className="mt-1 text-sm text-gray-500">
            Default branch: <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">{data.repo.default_branch}</code>
          </p>
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

      {/* Cost Trend Chart */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900">Cost Trend</h2>
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-6">
          <CostChart data={data.cost_by_day || []} period={period as any} />
        </div>
      </div>

      {/* Scans Table */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900">Pull Request Scans</h2>
        <div className="mt-4">
          {data.scans && data.scans.length > 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PR</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cost Delta</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">% Change</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data.scans.map((scan: any) => (
                    <tr key={scan.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-brand-600">
                        #{scan.pr_number}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                        {scan.pr_title}
                      </td>
                      <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium text-right ${
                        scan.cost_delta >= 0 ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {scan.cost_delta >= 0 ? '+' : ''}${Math.abs(scan.cost_delta).toFixed(2)}
                      </td>
                      <td className={`px-6 py-4 whitespace-nowrap text-sm text-right ${
                        scan.cost_delta_percent >= 0 ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {scan.cost_delta_percent >= 0 ? '+' : ''}{scan.cost_delta_percent.toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${
                          scan.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : scan.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {scan.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(scan.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-500 py-8 text-center">No scans found for this repository.</p>
          )}
        </div>
      </div>

      {/* Pagination */}
      {data.pagination && data.pagination.total_pages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {data.scans.length} of {data.pagination.total} scans
          </p>
          <div className="flex gap-2">
            <button className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
              Previous
            </button>
            <button className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
