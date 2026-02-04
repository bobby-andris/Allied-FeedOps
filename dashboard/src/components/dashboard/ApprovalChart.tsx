'use client'

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'

interface ApprovalChartProps {
  data: {
    approved: number
    pending: number
    rejected: number
  }
}

const COLORS = {
  approved: '#22c55e',
  pending: '#f59e0b',
  rejected: '#ef4444',
}

export function ApprovalChart({ data }: ApprovalChartProps) {
  const total = data.approved + data.pending + data.rejected

  const chartData = [
    { name: 'Approved', value: data.approved, color: COLORS.approved },
    { name: 'Pending', value: data.pending, color: COLORS.pending },
    { name: 'Rejected', value: data.rejected, color: COLORS.rejected },
  ].filter((item) => item.value > 0)

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-[250px] text-muted-foreground">
        No approval data yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          dataKey="value"
          label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [`${value} SKUs`, '']}
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  )
}
