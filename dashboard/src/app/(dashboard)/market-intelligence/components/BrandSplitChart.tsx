'use client'

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { BrandSplit } from '@/lib/market-intelligence/types'

interface Props {
  data: BrandSplit[]
}

const SEGMENT_COLORS: Record<string, string> = {
  brand: '#3b82f6',       // blue-500
  non_brand: '#94a3b8',   // slate-400
  competitor: '#ef4444',   // red-500
}

const SEGMENT_LABELS: Record<string, string> = {
  brand: 'Brand',
  non_brand: 'Non-Brand',
  competitor: 'Competitor',
}

function formatDollars(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as BrandSplit & { name: string }
  const totalRevenue = payload[0].payload._totalRevenue as number
  const pct = totalRevenue > 0 ? ((d.revenue / totalRevenue) * 100).toFixed(1) : '0'
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{SEGMENT_LABELS[d.segment] ?? d.segment}</p>
      <p>Revenue: {formatDollars(d.revenue)} ({pct}%)</p>
      <p>ROAS: {d.roas.toFixed(2)}x</p>
      <p>Terms: {d.termCount}</p>
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderLabel(entry: any) {
  const name = entry.name ?? ''
  const pct = typeof entry.percent === 'number' ? (entry.percent * 100).toFixed(0) : '0'
  return `${name} ${pct}%`
}

export function BrandSplitChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted-foreground">
        No brand split data available
      </div>
    )
  }

  const totalRevenue = data.reduce((sum, d) => sum + d.revenue, 0)

  const pieData = data.map((d) => ({
    ...d,
    name: SEGMENT_LABELS[d.segment] ?? d.segment,
    value: d.revenue,
    _totalRevenue: totalRevenue,
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            dataKey="value"
            nameKey="name"
            label={renderLabel}
          >
            {pieData.map((entry, i) => (
              <Cell
                key={i}
                fill={SEGMENT_COLORS[entry.segment] ?? '#94a3b8'}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>

      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-sm">
        {data.map((d) => (
          <div key={d.segment} className="rounded-md border p-2">
            <p className="text-muted-foreground">{SEGMENT_LABELS[d.segment]}</p>
            <p className="font-semibold">{d.roas.toFixed(2)}x ROAS</p>
            <p className="text-xs text-muted-foreground">{formatDollars(d.revenue)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
