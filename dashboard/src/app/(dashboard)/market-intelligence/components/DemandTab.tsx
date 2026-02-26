'use client'

import { AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { useDemandData } from '../hooks/useDemandData'
import { ImpressionShareChart } from './ImpressionShareChart'
import { CpcOpportunityChart } from './CpcOpportunityChart'
import { SeasonalTrendsChart } from './SeasonalTrendsChart'
import { NewTermsCard } from './NewTermsCard'
import { LongTailAnalysis } from './LongTailAnalysis'

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
        <Skeleton className="h-[250px] w-full" />
      </CardContent>
    </Card>
  )
}

export function DemandTab({ customLabel0 }: Props) {
  const { data, loading, error, refresh } = useDemandData(customLabel0)

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
          {Array.from({ length: 4 }).map((_, i) => (
            <ChartSkeleton key={i} />
          ))}
        </div>
        <ChartSkeleton />
      </div>
    )
  }

  const { kpis } = data

  return (
    <div className="space-y-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Avg Impression Share</p>
            <p className="text-2xl font-bold">
              {kpis.avgImpressionShare !== null
                ? `${kpis.avgImpressionShare.toFixed(1)}%`
                : 'N/A'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">CPC Headroom</p>
            <p className="text-2xl font-bold">
              {kpis.avgCpcHeadroom !== null
                ? `${kpis.avgCpcHeadroom.toFixed(1)}%`
                : 'N/A'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Seasonal Alerts</p>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold">{kpis.seasonalAlertCount}</p>
              {kpis.seasonalAlertCount > 0 && (
                <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                  Active
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">New Terms</p>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold">{kpis.newTermCount}</p>
              {kpis.newTermCount > 0 && (
                <Badge variant="secondary" className="bg-green-100 text-green-800">
                  Discovered
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 2x2 Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Impression Share Gaps</CardTitle>
          </CardHeader>
          <CardContent>
            <ImpressionShareChart data={data.impressionShare} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">CPC Opportunity</CardTitle>
          </CardHeader>
          <CardContent>
            <CpcOpportunityChart data={data.cpcOpportunity} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Seasonal Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <SeasonalTrendsChart data={data.seasonal} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Terms</CardTitle>
          </CardHeader>
          <CardContent>
            <NewTermsCard data={data.newTerms} count={kpis.newTermCount} />
          </CardContent>
        </Card>
      </div>

      {/* Full-width Long-tail Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Long-Tail Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <LongTailAnalysis data={data.longTail} />
        </CardContent>
      </Card>
    </div>
  )
}
