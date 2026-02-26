'use client'

import { useState, useMemo } from 'react'
import { AlertCircle, RefreshCw, ArrowUpDown } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDemandData } from '../hooks/useDemandData'
import { ImpressionShareChart } from './ImpressionShareChart'
import { CpcOpportunityChart } from './CpcOpportunityChart'
import { SeasonalTrendsChart } from './SeasonalTrendsChart'
import { NewTermsCard } from './NewTermsCard'
import { LongTailAnalysis } from './LongTailAnalysis'

type TopTermSortField = 'queryText' | 'customLabel0' | 'actualImpressions' | 'marketVolume' | 'sharePercent' | 'gap'
type SortDirection = 'asc' | 'desc'

function TopTermSortableHeader({
  children,
  field,
  currentField,
  direction,
  onSort,
  className,
}: {
  children: React.ReactNode
  field: TopTermSortField
  currentField: TopTermSortField
  direction: SortDirection
  onSort: (field: TopTermSortField) => void
  className?: string
}) {
  const isActive = currentField === field
  return (
    <TableHead
      className={`cursor-pointer select-none hover:bg-muted/50 ${className || ''}`}
      onClick={() => onSort(field)}
    >
      <div className={`flex items-center gap-1 ${className?.includes('text-right') ? 'justify-end' : ''}`}>
        {children}
        <ArrowUpDown className={`h-3 w-3 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`} />
        {isActive && (
          <span className="text-[10px] text-muted-foreground">{direction === 'asc' ? '\u2191' : '\u2193'}</span>
        )}
      </div>
    </TableHead>
  )
}

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

  const periodLabel = data.period?.from && data.period?.to
    ? `${new Date(data.period.from + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} — ${new Date(data.period.to + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
    : null

  return (
    <div className="space-y-4">
      {/* Period + Term Count */}
      {(periodLabel || data.period?.totalTerms) && (
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

      {/* Top Terms Table — shows actual search terms with metrics */}
      <TopTermsTable data={data.impressionShare} />
    </div>
  )
}

function TopTermsTable({ data }: { data: { queryText: string; customLabel0: string; actualImpressions: number; marketVolume: number | null; sharePercent: number | null; gap: number | null }[] }) {
  const [sortField, setSortField] = useState<TopTermSortField>('marketVolume')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  function handleSort(field: TopTermSortField) {
    if (sortField === field) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const sortedData = useMemo(() => {
    const sliced = data.slice(0, 50)
    return [...sliced].sort((a, b) => {
      const aVal = a[sortField]
      const bVal = b[sortField]
      // Handle nulls — push to bottom
      if (aVal === null && bVal === null) return 0
      if (aVal === null) return 1
      if (bVal === null) return -1
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return sortDirection === 'asc' ? Number(aVal) - Number(bVal) : Number(bVal) - Number(aVal)
    })
  }, [data, sortField, sortDirection])

  const headerProps = { currentField: sortField, direction: sortDirection, onSort: handleSort }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Top Search Terms by Market Volume</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-[400px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TopTermSortableHeader field="queryText" {...headerProps}>Search Term</TopTermSortableHeader>
                <TopTermSortableHeader field="customLabel0" {...headerProps}>Product Group</TopTermSortableHeader>
                <TopTermSortableHeader field="actualImpressions" className="text-right" {...headerProps}>Your Impressions</TopTermSortableHeader>
                <TopTermSortableHeader field="marketVolume" className="text-right" {...headerProps}>Market Volume</TopTermSortableHeader>
                <TopTermSortableHeader field="sharePercent" className="text-right" {...headerProps}>Share</TopTermSortableHeader>
                <TopTermSortableHeader field="gap" className="text-right" {...headerProps}>Gap</TopTermSortableHeader>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedData.map((row) => (
                <TableRow key={row.queryText}>
                  <TableCell className="font-medium">{row.queryText}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{row.customLabel0 || '\u2014'}</TableCell>
                  <TableCell className="text-right">{row.actualImpressions.toLocaleString()}</TableCell>
                  <TableCell className="text-right">{row.marketVolume?.toLocaleString() ?? 'N/A'}</TableCell>
                  <TableCell className="text-right">
                    {row.sharePercent !== null ? (
                      <span className={row.sharePercent < 20 ? 'text-red-500' : row.sharePercent < 50 ? 'text-amber-500' : 'text-green-500'}>
                        {row.sharePercent.toFixed(1)}%
                      </span>
                    ) : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {row.gap !== null ? row.gap.toLocaleString() : '\u2014'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
