'use client'

import { AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { useCompetitiveData } from '../hooks/useCompetitiveData'
import { BrandSplitChart } from './BrandSplitChart'
import { CompetitorTracker } from './CompetitorTracker'

interface Props {
  customLabel0?: string
}

function KpiSkeleton() {
  return (
    <Card>
      <CardContent className="pt-6">
        <Skeleton className="mb-2 h-4 w-24" />
        <Skeleton className="h-8 w-16" />
      </CardContent>
    </Card>
  )
}

function ChartSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-40" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[280px] w-full" />
      </CardContent>
    </Card>
  )
}

function formatDollars(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function CompetitiveTab({ customLabel0 }: Props) {
  const { data, loading, error, refresh } = useCompetitiveData(customLabel0)

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
        <Button variant="outline" onClick={refresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    )
  }

  if (loading || !data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <KpiSkeleton key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <ChartSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  const { kpis } = data

  const periodLabel = data.period?.from && data.period?.to
    ? `${new Date(data.period.from + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} — ${new Date(data.period.to + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
    : null

  return (
    <div className="space-y-4">
      {/* Period + Term Count */}
      {(periodLabel || data.period?.totalTerms > 0) && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          {periodLabel && (
            <Badge variant="outline" className="font-normal">{periodLabel}</Badge>
          )}
          {data.period?.totalTerms > 0 && (
            <span>{data.period.totalTerms.toLocaleString()} search terms analyzed</span>
          )}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Brand Revenue</p>
            <p className="text-2xl font-bold">{kpis.brandRevenuePercent.toFixed(1)}%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Non-Brand ROAS</p>
            <p className="text-2xl font-bold">{kpis.nonBrandRoas.toFixed(1)}x</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Competitor Spend</p>
            <p className="text-2xl font-bold">{formatDollars(kpis.competitorSpend)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Top Competitor</p>
            <p className="text-2xl font-bold capitalize">
              {kpis.topCompetitor ?? 'None'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 2-column Layout */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Brand / Non-Brand Revenue Split</CardTitle>
          </CardHeader>
          <CardContent>
            <BrandSplitChart data={data.brandSplit} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Competitor Mention Tracking</CardTitle>
          </CardHeader>
          <CardContent>
            <CompetitorTracker data={data.competitorMentions} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
