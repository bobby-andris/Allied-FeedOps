'use client'

import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { MetricDistribution } from '@/lib/optimization/tier-scoring.types'

interface DistributionChartProps {
  distribution: MetricDistribution
  metricName: string
  tierColor: string
  terms?: number[]
}

const UNIT_MAP: Record<string, string> = {
  roas: 'x',
  cvr: '%',
  ctr: '%',
  cpc: '$',
}

function formatMetricValue(value: number, metricName: string): string {
  const unit = UNIT_MAP[metricName.toLowerCase()] ?? ''
  if (unit === '$') return `$${value.toFixed(2)}`
  if (unit === '%') return `${(value * 100).toFixed(1)}%`
  return `${value.toFixed(2)}${unit}`
}

export function DistributionChart({ distribution, metricName, tierColor }: DistributionChartProps) {
  const { p25, p50, p75, min, max } = distribution

  const chartData = useMemo(() => {
    const range = max - min || 1
    // Create three zones: below p25, p25-p75, above p75
    return [
      {
        name: 'dist',
        belowP25: Math.max(0, p25 - min),
        healthy: Math.max(0, p75 - p25),
        aboveP75: Math.max(0, max - p75),
      },
    ]
  }, [p25, p75, min, max])

  const unit = UNIT_MAP[metricName.toLowerCase()] ?? ''
  const metricLabel = metricName.toUpperCase()

  // Readable explanation
  const explanation = metricName.toLowerCase() === 'roas'
    ? `Median ROAS: ${p50.toFixed(1)}x — half of terms in this tier earn more than ${p50.toFixed(1)}x return on ad spend`
    : `Median ${metricLabel}: ${formatMetricValue(p50, metricName)}`

  return (
    <div className="space-y-1">
      <div className="h-[48px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 4, right: 4, bottom: 4, left: 4 }}
            barSize={24}
          >
            <XAxis
              type="number"
              domain={[min, max]}
              hide
            />
            <YAxis type="category" dataKey="name" hide />
            <Bar dataKey="belowP25" stackId="dist" fill="#f97316" radius={[4, 0, 0, 4]} opacity={0.4} />
            <Bar dataKey="healthy" stackId="dist" fill={tierColor} radius={0} opacity={0.85} />
            <Bar dataKey="aboveP75" stackId="dist" fill="#3b82f6" radius={[0, 4, 4, 0]} opacity={0.4} />
            <ReferenceLine x={p50 - min} stroke="#111" strokeWidth={2} strokeDasharray="3 3" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground px-1">
        <span>{formatMetricValue(min, metricName)}</span>
        <div className="flex items-center gap-2">
          <span className="text-orange-500">p25: {formatMetricValue(p25, metricName)}</span>
          <span className="font-semibold text-foreground">p50: {formatMetricValue(p50, metricName)}</span>
          <span className="text-blue-500">p75: {formatMetricValue(p75, metricName)}</span>
        </div>
        <span>{formatMetricValue(max, metricName)}</span>
      </div>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <p className="text-xs text-muted-foreground truncate cursor-help">
              {explanation}
            </p>
          </TooltipTrigger>
          <TooltipContent>
            <div className="space-y-1 text-xs">
              <p>Min: {formatMetricValue(min, metricName)}</p>
              <p>P25: {formatMetricValue(p25, metricName)}</p>
              <p>Median (P50): {formatMetricValue(p50, metricName)}</p>
              <p>P75: {formatMetricValue(p75, metricName)}</p>
              <p>Max: {formatMetricValue(max, metricName)}</p>
              <p>MAD: {formatMetricValue(distribution.mad, metricName)}</p>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  )
}
