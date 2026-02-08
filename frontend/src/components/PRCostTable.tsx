interface Scan {
  scan_id: string;
  repo_name: string;
  pr_number: number;
  pr_title: string;
  cost_delta: number;
  cost_delta_percent: number;
  status: string;
  created_at: string;
}

interface PRCostTableProps {
  scans: Scan[];
}

/**
 * PR Cost Table
 *
 * Displays a list of recent PR scans with cost deltas.
 * Used in the dashboard overview and repo detail pages.
 */
export function PRCostTable({ scans }: PRCostTableProps) {
  if (!scans || scans.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
        <p className="text-gray-500">No scans yet. Open a PR with .tf changes to get started.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {scans.map((scan) => (
        <div
          key={scan.scan_id}
          className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:border-brand-300 hover:shadow-sm transition-all"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-brand-600">
                #{scan.pr_number}
              </span>
              <span className="text-xs text-gray-400">•</span>
              <span className="text-xs text-gray-500 truncate">{scan.repo_name}</span>
            </div>
            <p className="mt-0.5 text-sm text-gray-900 truncate">{scan.pr_title}</p>
            <p className="mt-0.5 text-xs text-gray-400">
              {new Date(scan.created_at).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          </div>

          <div className="ml-4 text-right flex-shrink-0">
            <p
              className={`text-sm font-semibold ${
                scan.cost_delta >= 0 ? 'text-red-600' : 'text-green-600'
              }`}
            >
              {scan.cost_delta >= 0 ? '+' : ''}${Math.abs(scan.cost_delta).toFixed(2)}
            </p>
            <p
              className={`text-xs ${
                scan.cost_delta_percent >= 0 ? 'text-red-400' : 'text-green-400'
              }`}
            >
              {scan.cost_delta_percent >= 0 ? '+' : ''}
              {scan.cost_delta_percent.toFixed(1)}%
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
