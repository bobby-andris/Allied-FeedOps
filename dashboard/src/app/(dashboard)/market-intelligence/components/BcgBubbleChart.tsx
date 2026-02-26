'use client'

import { useCallback } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  Label,
} from 'recharts'
import type { ProductGroup } from '@/lib/market-intelligence/types'
import { BCG_COLORS, BCG_QUADRANT_LABELS } from '@/lib/market-intelligence/constants'

interface BcgBubbleChartProps {
  groups: ProductGroup[]
  medianRoas: number
  medianRevenue: number
  onGroupClick: (customLabel0: string) => void
  dimmed?: boolean
}

function formatRoas(value: number): string {
  return `${value.toFixed(1)}x`
}

function formatRevenue(value: number): string {
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`
  }
  return `$${value.toFixed(0)}`
}

interface TooltipPayloadEntry {
  payload?: ProductGroup
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadEntry[] }) {
  if (!active || !payload || !payload[0]?.payload) return null
  const group = payload[0].payload
  const quadrantInfo = BCG_QUADRANT_LABELS[group.quadrant]
  return (
    <div className="bg-popover text-popover-foreground rounded-md border px-3 py-2 shadow-md text-sm">
      <p className="font-semibold">{group.customLabel0}</p>
      <p className="text-muted-foreground text-xs">{quadrantInfo?.label}</p>
      <div className="mt-1 space-y-0.5 text-xs">
        <p>ROAS: {formatRoas(group.roas)}</p>
        <p>Revenue: {formatRevenue(group.revenue)}</p>
        <p>Spend: {formatRevenue(group.spend)}</p>
        <p>Trend: <span className={group.trendDirection === 'up' ? 'text-green-500' : group.trendDirection === 'down' ? 'text-red-500' : ''}>
          {group.trend > 0 ? '+' : ''}{group.trend.toFixed(1)}%
        </span></p>
      </div>
    </div>
  )
}

export function BcgBubbleChart({
  groups,
  medianRoas,
  medianRevenue,
  onGroupClick,
  dimmed = false,
}: BcgBubbleChartProps) {
  const handleClick = useCallback(
    // Recharts Scatter onClick passes { payload: ProductGroup, ... }
    (entry: { payload?: ProductGroup } | ProductGroup) => {
      const group = 'payload' in entry && entry.payload ? entry.payload : entry as ProductGroup
      if (group?.customLabel0) {
        onGroupClick(group.customLabel0)
      }
    },
    [onGroupClick]
  )

  return (
    <div className={`transition-opacity duration-300 ${dimmed ? 'opacity-40' : 'opacity-100'}`}>
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart margin={{ top: 30, right: 30, bottom: 30, left: 30 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
          <XAxis
            type="number"
            dataKey="roas"
            name="ROAS"
            tickFormatter={formatRoas}
          >
            <Label value="ROAS" position="bottom" offset={10} />
          </XAxis>
          <YAxis
            type="number"
            dataKey="revenue"
            name="Revenue"
            tickFormatter={formatRevenue}
          >
            <Label value="Revenue ($)" angle={-90} position="left" offset={10} />
          </YAxis>
          <ZAxis type="number" dataKey="spend" range={[40, 400]} name="Spend" />
          <Tooltip content={<CustomTooltip />} />

          {/* Median reference lines */}
          <ReferenceLine
            x={medianRoas}
            stroke="#9ca3af"
            strokeDasharray="5 5"
            label={{ value: 'Median ROAS', position: 'top', fill: '#9ca3af', fontSize: 11 }}
          />
          <ReferenceLine
            y={medianRevenue}
            stroke="#9ca3af"
            strokeDasharray="5 5"
            label={{ value: 'Median Revenue', position: 'right', fill: '#9ca3af', fontSize: 11 }}
          />

          <Scatter
            data={groups}
            cursor="pointer"
            onClick={handleClick}
          >
            {groups.map((group, index) => (
              <Cell
                key={`cell-${index}`}
                fill={BCG_COLORS[group.quadrant] || '#6b7280'}
                fillOpacity={0.8}
                stroke={BCG_COLORS[group.quadrant] || '#6b7280'}
                strokeWidth={1}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      {/* Quadrant legend */}
      <div className="flex justify-center gap-6 mt-2 text-xs">
        {Object.entries(BCG_QUADRANT_LABELS).map(([key, info]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: BCG_COLORS[key] }}
            />
            <span className="text-muted-foreground">{info.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
