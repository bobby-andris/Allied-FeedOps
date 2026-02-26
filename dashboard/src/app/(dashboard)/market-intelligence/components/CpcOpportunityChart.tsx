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
import type { CpcOpportunity } from '@/lib/market-intelligence/types'

interface Props {
  data: CpcOpportunity[]
}

function getBarColor(headroom: number | null): string {
  if (headroom === null) return '#94a3b8'
  if (headroom > 20) return '#22c55e'    // green — well below market
  if (headroom >= 0) return '#f59e0b'    // amber — near market
  return '#ef4444'                        // red — above market
}

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '...' : str
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as CpcOpportunity
  const actualCpc = (d.actualCpcMicros / 1_000_000).toFixed(2)
  const marketCpc = d.marketHighCpcMicros
    ? (d.marketHighCpcMicros / 1_000_000).toFixed(2)
    : 'N/A'
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{d.queryText}</p>
      <p>Your CPC: ${actualCpc}</p>
      <p>Market CPC: ${marketCpc}</p>
      <p>
        Headroom:{' '}
        {d.headroomPercent !== null ? `${d.headroomPercent.toFixed(1)}%` : 'N/A'}
      </p>
    </div>
  )
}

export function CpcOpportunityChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No CPC opportunity data available
      </div>
    )
  }

  const top20 = data
    .filter((d) => d.headroomPercent !== null)
    .sort((a, b) => (b.headroomPercent ?? 0) - (a.headroomPercent ?? 0))
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
          tick={{ fontSize: 11 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="headroomPercent" name="CPC Headroom">
          {top20.map((entry, i) => (
            <Cell key={i} fill={getBarColor(entry.headroomPercent)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
