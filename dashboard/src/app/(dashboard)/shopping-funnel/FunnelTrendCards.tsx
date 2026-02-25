'use client'

import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface PeriodMetrics {
  impressions: number
  clicks: number
  ctr: number
  cost_micros: number
  conversions: number
  conversions_value: number
  roas: number
}

interface TrendsResponse {
  has_data: boolean
  has_previous: boolean
  current: PeriodMetrics
  previous: PeriodMetrics | null
}

// ---------------------------------------------------------------------------
// Number formatters
// ---------------------------------------------------------------------------

const fmtInt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

const fmtCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const fmtDec1 = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

// ---------------------------------------------------------------------------
// TrendArrow sub-component
// ---------------------------------------------------------------------------

function TrendArrow({
  current,
  previous,
  hasPrevious,
  invertColor,
}: {
  current: number
  previous: number
  hasPrevious: boolean
  invertColor?: boolean
}) {
  if (!hasPrevious || previous === 0) {
    return <span className="text-xs text-muted-foreground">No prior data</span>
  }

  const pctChange = ((current - previous) / previous) * 100
  const absPct = Math.abs(pctChange)

  if (absPct <= 5) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="h-3 w-3" />
        Flat
      </span>
    )
  }

  const isUp = pctChange > 0
  // For most metrics: up = green. For Ad Spend (invertColor): up = red
  const isGood = invertColor ? !isUp : isUp
  const colorClass = isGood ? 'text-green-600' : 'text-red-600'
  const Icon = isUp ? TrendingUp : TrendingDown

  return (
    <span className={`flex items-center gap-1 text-xs ${colorClass}`}>
      <Icon className="h-3 w-3" />
      {pctChange >= 0 ? '+' : ''}{pctChange.toFixed(1)}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Card definitions
// ---------------------------------------------------------------------------

interface MetricCardDef {
  label: string
  key: keyof PeriodMetrics
  format: (v: number) => string
  invertColor?: boolean
}

const METRIC_CARDS: MetricCardDef[] = [
  {
    label: 'Impressions',
    key: 'impressions',
    format: (v) => fmtInt.format(v),
  },
  {
    label: 'Clicks',
    key: 'clicks',
    format: (v) => fmtInt.format(v),
  },
  {
    label: 'CTR',
    key: 'ctr',
    format: (v) => `${(v * 100).toFixed(2)}%`,
  },
  {
    label: 'Ad Spend',
    key: 'cost_micros',
    format: (v) => fmtCurrency.format(v / 1e6),
    invertColor: true,
  },
  {
    label: 'Conversions',
    key: 'conversions',
    format: (v) => fmtDec1.format(v),
  },
  {
    label: 'ROAS',
    key: 'roas',
    format: (v) => {
      // Show up to 2 decimals but trim trailing zeros (e.g., 75.5x not 75.50x)
      const str = v.toFixed(2).replace(/\.?0+$/, '')
      return `${str}x`
    },
  },
]

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function FunnelTrendCards() {
  const [data, setData] = useState<TrendsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function fetchTrends() {
      try {
        const res = await fetch('/api/funnel-snapshots/trends')
        if (!res.ok) return
        const json = await res.json()
        if (!cancelled) setData(json)
      } catch {
        // Silently fail -- cards just won't render
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchTrends()
    return () => { cancelled = true }
  }, [])

  // Loading state: show skeleton cards
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-4 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  // No data at all: render nothing
  if (!data || !data.has_data) {
    return null
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
      {METRIC_CARDS.map((card) => {
        const currentVal = data.current[card.key] as number
        const previousVal = data.previous ? (data.previous[card.key] as number) : 0

        return (
          <Card key={card.label} data-testid={`trend-card-${card.label.toLowerCase().replace(/\s+/g, '-')}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.format(currentVal)}</div>
              <TrendArrow
                current={currentVal}
                previous={previousVal}
                hasPrevious={data.has_previous}
                invertColor={card.invertColor}
              />
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export default FunnelTrendCards
