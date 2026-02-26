'use client'

import { useMemo } from 'react'
import type { GroupDistributions, MetricDistribution } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface RoasBoxPlotProps {
  distributions: Record<string, GroupDistributions>
}

interface BoxPlotData {
  tier: FunnelTier
  label: string
  p25: number
  p50: number
  p75: number
  min: number
  max: number
  color: string
  hasData: boolean
}

const TIER_ORDER: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']

const TIER_COLORS: Record<FunnelTier, string> = {
  HIGH: '#22c55e',   // green-500
  MEDIUM: '#3b82f6', // blue-500
  LOW: '#f59e0b',    // amber-500
}

const TIER_BG: Record<FunnelTier, string> = {
  HIGH: 'bg-green-500',
  MEDIUM: 'bg-blue-500',
  LOW: 'bg-amber-500',
}

const TIER_LABELS: Record<FunnelTier, string> = {
  HIGH: 'Premium',
  MEDIUM: 'Mid-tier',
  LOW: 'Budget',
}

/**
 * Aggregate ROAS distributions across all product groups by averaging per tier.
 */
export function aggregateDistributions(
  distributions: Record<string, GroupDistributions>
): BoxPlotData[] {
  const groups = Object.values(distributions)

  return TIER_ORDER.map(tier => {
    const tierDists: MetricDistribution[] = []
    for (const group of groups) {
      const td = group.tiers[tier]
      if (td && td.sampleSize > 0) {
        tierDists.push(td.metrics.roas)
      }
    }

    if (tierDists.length === 0) {
      return {
        tier,
        label: TIER_LABELS[tier],
        p25: 0,
        p50: 0,
        p75: 0,
        min: 0,
        max: 0,
        color: TIER_COLORS[tier],
        hasData: false,
      }
    }

    const avg = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length

    return {
      tier,
      label: TIER_LABELS[tier],
      p25: avg(tierDists.map(d => d.p25)),
      p50: avg(tierDists.map(d => d.p50)),
      p75: avg(tierDists.map(d => d.p75)),
      min: avg(tierDists.map(d => d.min)),
      max: avg(tierDists.map(d => d.max)),
      color: TIER_COLORS[tier],
      hasData: true,
    }
  })
}

/**
 * Check for overlap zones between adjacent tiers.
 */
export function detectOverlaps(data: BoxPlotData[]): Array<{ left: string; right: string }> {
  const overlaps: Array<{ left: string; right: string }> = []
  for (let i = 0; i < data.length - 1; i++) {
    const higher = data[i]
    const lower = data[i + 1]
    if (higher.hasData && lower.hasData && higher.p25 < lower.p75) {
      overlaps.push({ left: higher.tier, right: lower.tier })
    }
  }
  return overlaps
}

export function RoasBoxPlot({ distributions }: RoasBoxPlotProps) {
  const boxData = useMemo(() => aggregateDistributions(distributions), [distributions])

  // Calculate scale for positioning
  const allValues = boxData.filter(d => d.hasData).flatMap(d => [d.min, d.max])
  const scaleMin = allValues.length > 0 ? Math.min(...allValues) : 0
  const scaleMax = allValues.length > 0 ? Math.max(...allValues) : 1
  const range = scaleMax - scaleMin || 1

  const toPercent = (val: number) => ((val - scaleMin) / range) * 100

  const overlaps = useMemo(() => detectOverlaps(boxData), [boxData])

  return (
    <div className="w-full space-y-1">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">ROAS Distribution by Tier</h3>
      <div className="space-y-4">
        {boxData.map(d => (
          <div key={d.tier} className="flex items-center gap-3">
            {/* Tier label */}
            <span className="text-xs font-medium w-16 shrink-0 text-right">{d.label}</span>

            {/* Box plot visualization */}
            <div className="relative flex-1 h-8">
              {!d.hasData ? (
                <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                  No data
                </div>
              ) : (
                <>
                  {/* Whisker line (min to max) */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 h-px bg-border"
                    style={{
                      left: `${toPercent(d.min)}%`,
                      width: `${toPercent(d.max) - toPercent(d.min)}%`,
                    }}
                  />

                  {/* Min whisker dot */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-2 w-2 rounded-full"
                    style={{
                      left: `${toPercent(d.min)}%`,
                      backgroundColor: d.color,
                      opacity: 0.5,
                    }}
                  />

                  {/* Max whisker dot */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-2 w-2 rounded-full"
                    style={{
                      left: `${toPercent(d.max)}%`,
                      backgroundColor: d.color,
                      opacity: 0.5,
                    }}
                  />

                  {/* IQR box (p25 to p75) */}
                  <div
                    className="absolute top-1 bottom-1 rounded-sm"
                    style={{
                      left: `${toPercent(d.p25)}%`,
                      width: `${toPercent(d.p75) - toPercent(d.p25)}%`,
                      backgroundColor: d.color,
                      opacity: 0.3,
                    }}
                  />

                  {/* Median line */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5"
                    style={{
                      left: `${toPercent(d.p50)}%`,
                      backgroundColor: d.color,
                    }}
                  />

                  {/* Median label */}
                  <span
                    className="absolute -bottom-3.5 -translate-x-1/2 text-[10px] text-muted-foreground"
                    style={{ left: `${toPercent(d.p50)}%` }}
                  >
                    {d.p50.toFixed(1)}x
                  </span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Overlap warning */}
      {overlaps.length > 0 && (
        <p className="text-[10px] text-amber-600 mt-2">
          Overlap detected between {overlaps.map(o => `${o.left}/${o.right}`).join(', ')} tiers
        </p>
      )}

      {/* Scale labels */}
      {allValues.length > 0 && (
        <div className="flex justify-between text-[10px] text-muted-foreground pl-[76px]">
          <span>{scaleMin.toFixed(1)}x</span>
          <span>{scaleMax.toFixed(1)}x</span>
        </div>
      )}
    </div>
  )
}
