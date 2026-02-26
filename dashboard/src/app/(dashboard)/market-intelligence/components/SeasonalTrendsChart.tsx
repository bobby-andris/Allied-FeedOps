'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import type { SeasonalTerm } from '@/lib/market-intelligence/types'

interface Props {
  data: SeasonalTerm[]
}

const LINE_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1',
]

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function SeasonalTrendsChart({ data }: Props) {
  // Filter to terms that have monthly volume data
  const termsWithData = data.filter((d) => d.monthlyVolumes.length > 0)

  if (!termsWithData.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        Seasonal data requires Keyword Planner enrichment
      </div>
    )
  }

  // Limit to 10 terms for readability
  const displayTerms = termsWithData.slice(0, 10)

  // Build chart data: one row per month, columns per term
  const allMonths = new Set<string>()
  for (const term of displayTerms) {
    for (const mv of term.monthlyVolumes) {
      allMonths.add(`${mv.year}-${String(mv.month).padStart(2, '0')}`)
    }
  }

  const sortedMonths = Array.from(allMonths).sort()
  const chartData = sortedMonths.map((monthKey) => {
    const [yearStr, monthStr] = monthKey.split('-')
    const row: Record<string, string | number> = {
      month: `${MONTHS[parseInt(monthStr) - 1]} ${yearStr.slice(2)}`,
    }
    for (const term of displayTerms) {
      const mv = term.monthlyVolumes.find(
        (v) => `${v.year}-${String(v.month).padStart(2, '0')}` === monthKey
      )
      row[term.queryText] = mv?.searches ?? 0
    }
    return row
  })

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-2">
        {displayTerms
          .filter((t) => t.direction !== 'stable')
          .map((t) => (
            <Badge
              key={t.queryText}
              variant={t.direction === 'spiking' ? 'default' : 'destructive'}
            >
              {t.queryText.slice(0, 20)}: {t.direction === 'spiking' ? '+' : ''}
              {t.changePercent.toFixed(0)}%
            </Badge>
          ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(v: number) => v.toLocaleString()} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {displayTerms.map((term, i) => (
            <Line
              key={term.queryText}
              type="monotone"
              dataKey={term.queryText}
              stroke={LINE_COLORS[i % LINE_COLORS.length]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
