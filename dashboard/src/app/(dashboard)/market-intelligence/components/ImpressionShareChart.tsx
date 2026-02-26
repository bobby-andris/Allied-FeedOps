'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { ImpressionShareGap } from '@/lib/market-intelligence/types'

interface Props {
  data: ImpressionShareGap[]
}

function getBarColor(share: number | null): string {
  if (share === null) return '#94a3b8' // slate-400
  if (share > 50) return '#22c55e'     // green-500
  if (share >= 20) return '#f59e0b'    // amber-500
  return '#ef4444'                      // red-500
}

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '...' : str
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as ImpressionShareGap
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{d.queryText}</p>
      <p>Your impressions: {d.actualImpressions.toLocaleString()}</p>
      <p>Market volume: {d.marketVolume?.toLocaleString() ?? 'N/A'}</p>
      <p>Share: {d.sharePercent !== null ? `${d.sharePercent.toFixed(1)}%` : 'N/A'}</p>
    </div>
  )
}

export function ImpressionShareChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No impression share data available
      </div>
    )
  }

  const top20 = data
    .filter((d) => d.sharePercent !== null)
    .sort((a, b) => (a.sharePercent ?? 0) - (b.sharePercent ?? 0))
    .slice(0, 20)

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={top20} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
        <XAxis
          dataKey="queryText"
          tickFormatter={(v: string) => truncate(v, 25)}
          angle={-45}
          textAnchor="end"
          height={80}
          tick={{ fontSize: 11 }}
        />
        <YAxis
          tickFormatter={(v: number) => `${v}%`}
          domain={[0, 100]}
          tick={{ fontSize: 11 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="sharePercent" name="Impression Share">
          {top20.map((entry, i) => (
            <Cell key={i} fill={getBarColor(entry.sharePercent)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
