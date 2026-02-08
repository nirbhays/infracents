'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface CostDataPoint {
  date: string;
  total_delta: number;
  scan_count: number;
}

interface CostChartProps {
  data: CostDataPoint[];
  period: '7d' | '30d' | '90d' | '1y';
  loading?: boolean;
}

/**
 * Cost Trend Chart
 *
 * Renders an area chart showing cost deltas over time using Recharts.
 * Supports different time periods and responsive sizing.
 */
export function CostChart({ data, period, loading = false }: CostChartProps) {
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading chart...</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-gray-400">No data available for this period</p>
      </div>
    );
  }

  // Format the date label based on period
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (period === '7d') {
      return date.toLocaleDateString('en-US', { weekday: 'short' });
    } else if (period === '1y') {
      return date.toLocaleDateString('en-US', { month: 'short' });
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Custom tooltip component
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null;

    return (
      <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
        <p className="text-xs font-medium text-gray-500">{label}</p>
        <p className="mt-1 text-sm font-semibold text-gray-900">
          ${payload[0].value.toFixed(2)}
        </p>
        {payload[0].payload.scan_count !== undefined && (
          <p className="text-xs text-gray-500">
            {payload[0].payload.scan_count} scan{payload[0].payload.scan_count !== 1 ? 's' : ''}
          </p>
        )}
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
        <defs>
          <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 12, fill: '#94a3b8' }}
          axisLine={{ stroke: '#e2e8f0' }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(value) => `$${value}`}
          tick={{ fontSize: 12, fill: '#94a3b8' }}
          axisLine={false}
          tickLine={false}
          width={60}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="total_delta"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#costGradient)"
          activeDot={{ r: 5, strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
