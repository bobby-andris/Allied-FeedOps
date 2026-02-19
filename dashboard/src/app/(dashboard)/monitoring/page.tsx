'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Search,
  Activity,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import Link from 'next/link'

interface PerformanceDelta {
  master_sku: string
  platform: string
  days_since_publish: number
  trend: 'improving' | 'declining' | 'stable'
  significance: 'high' | 'medium' | 'low' | 'insufficient_data'
  ctr_delta: number
  cvr_delta: number
  roas_delta: number
  impressions_delta: number
  clicks_delta: number
  baseline_ctr: number
  current_ctr: number
  baseline_conversions: number
  current_conversions: number
}

interface SearchQueryDelta {
  query_text: string
  master_sku: string
  status: 'new' | 'lost' | 'volume_increase' | 'volume_decrease' | 'stable'
  opportunity_score: number
  impressions_delta: number
  clicks_delta: number
  before_impressions: number
  after_impressions: number
  before_clicks: number
  after_clicks: number
  after_avg_monthly_searches: number | null
  competition: string | null
}

interface SnapshotResult {
  created: number
  type: 'search' | 'performance'
  error?: string
}

export default function MonitoringPage() {
  const [performanceDeltas, setPerformanceDeltas] = useState<PerformanceDelta[]>([])
  const [searchDeltas, setSearchDeltas] = useState<SearchQueryDelta[]>([])
  const [loadingPerformance, setLoadingPerformance] = useState(false)
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [skuFilter, setSkuFilter] = useState('')
  const [activeTab, setActiveTab] = useState('performance')
  const [snapshotResult, setSnapshotResult] = useState<SnapshotResult | null>(null)

  const fetchPerformanceDeltas = async () => {
    setLoadingPerformance(true)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/monitoring/performance-delta?${params}`)
      if (!res.ok) throw new Error('Failed to fetch performance deltas')

      const data = await res.json()
      setPerformanceDeltas(data.deltas || [])
    } catch (err) {
      console.error('Failed to fetch performance deltas:', err)
    } finally {
      setLoadingPerformance(false)
    }
  }

  const fetchSearchDeltas = async () => {
    setLoadingSearch(true)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/monitoring/search-delta?${params}`)
      if (!res.ok) throw new Error('Failed to fetch search deltas')

      const data = await res.json()
      setSearchDeltas(data.deltas || [])
    } catch (err) {
      console.error('Failed to fetch search deltas:', err)
    } finally {
      setLoadingSearch(false)
    }
  }

  const captureSearchSnapshots = async () => {
    setSnapshotResult(null)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/monitoring/snapshot-capture?${params}`, {
        method: 'POST',
      })

      if (!res.ok) throw new Error('Failed to capture snapshots')

      const data = await res.json()
      setSnapshotResult({ created: data.snapshots_created, type: 'search' })

      // Refresh data
      fetchPerformanceDeltas()
      fetchSearchDeltas()
    } catch (err) {
      console.error('Failed to capture search snapshots:', err)
      setSnapshotResult({ created: 0, type: 'search', error: 'Failed to capture search snapshots' })
    }
  }

  const capturePerformanceSnapshots = async () => {
    setSnapshotResult(null)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/performance/capture-snapshot?${params}`, {
        method: 'POST',
      })

      if (!res.ok) throw new Error('Failed to capture performance snapshots')

      const data = await res.json()
      setSnapshotResult({ created: data.snapshots_created ?? data.captured ?? 0, type: 'performance' })

      // Refresh data
      fetchPerformanceDeltas()
      fetchSearchDeltas()
    } catch (err) {
      console.error('Failed to capture performance snapshots:', err)
      setSnapshotResult({ created: 0, type: 'performance', error: 'Failed to capture performance snapshots' })
    }
  }

  useEffect(() => {
    fetchPerformanceDeltas()
    fetchSearchDeltas()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skuFilter])

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <TrendingUp className="h-4 w-4 text-green-500" />
      case 'declining':
        return <TrendingDown className="h-4 w-4 text-red-500" />
      default:
        return <Minus className="h-4 w-4 text-gray-500" />
    }
  }

  const getSignificanceBadge = (significance: string) => {
    const colors = {
      high: 'bg-red-100 text-red-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-blue-100 text-blue-800',
      insufficient_data: 'bg-gray-100 text-gray-800',
    }
    return (
      <Badge className={colors[significance as keyof typeof colors] || ''}>
        {significance.replace('_', ' ')}
      </Badge>
    )
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      new: 'bg-green-100 text-green-800',
      lost: 'bg-red-100 text-red-800',
      volume_increase: 'bg-blue-100 text-blue-800',
      volume_decrease: 'bg-orange-100 text-orange-800',
      stable: 'bg-gray-100 text-gray-800',
    }
    return (
      <Badge className={colors[status as keyof typeof colors] || ''}>
        {status.replace('_', ' ')}
      </Badge>
    )
  }

  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Post-Publish Monitoring</h1>
        <p className="text-muted-foreground mt-2">
          Track performance changes and search query shifts after content optimization
        </p>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Monitoring Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Filter by SKU (e.g., WP-2/16-GAL)..."
                value={skuFilter}
                onChange={(e) => setSkuFilter(e.target.value)}
              />
            </div>
            <Button onClick={captureSearchSnapshots} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Capture Search Snapshots
            </Button>
            <Button onClick={capturePerformanceSnapshots} variant="outline">
              <Activity className="h-4 w-4 mr-2" />
              Capture Performance Snapshots
            </Button>
          </div>
          {snapshotResult && (
            <Alert variant={snapshotResult.error ? 'destructive' : 'default'}>
              {snapshotResult.error ? (
                <XCircle className="h-4 w-4" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              <AlertDescription>
                {snapshotResult.error
                  ? snapshotResult.error
                  : `Captured ${snapshotResult.created} ${snapshotResult.type} snapshot${snapshotResult.created !== 1 ? 's' : ''}`}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="performance">
            <Activity className="h-4 w-4 mr-2" />
            Performance Deltas
          </TabsTrigger>
          <TabsTrigger value="search">
            <Search className="h-4 w-4 mr-2" />
            Search Query Changes
          </TabsTrigger>
        </TabsList>

        {/* Performance Deltas Tab */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Changes</CardTitle>
              <CardDescription>
                Compare baseline metrics to post-publish performance
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loadingPerformance ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : performanceDeltas.length === 0 ? (
                <div className="text-center py-8 space-y-3">
                  <p className="text-muted-foreground">No performance delta data available yet.</p>
                  <p className="text-sm text-muted-foreground">
                    Performance deltas appear after content is published and at least 7 days have passed.
                    Snapshots are captured automatically each night.
                  </p>
                  <Link href="/performance" className="text-sm text-primary underline underline-offset-2">
                    View performance snapshots →
                  </Link>
                </div>
              ) : (
                <div className="space-y-4">
                  {performanceDeltas.map((delta, idx) => (
                    <div
                      key={idx}
                      className="border rounded-lg p-4 hover:bg-accent transition-colors"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          {getTrendIcon(delta.trend)}
                          <div>
                            <div className="font-semibold">{delta.master_sku}</div>
                            <div className="text-sm text-muted-foreground">
                              {delta.platform} • {delta.days_since_publish} days since publish
                            </div>
                          </div>
                        </div>
                        {getSignificanceBadge(delta.significance)}
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <div>
                          <div className="text-sm text-muted-foreground">CTR</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">
                              {(delta.current_ctr * 100).toFixed(2)}%
                            </span>
                            <span
                              className={
                                delta.ctr_delta > 0 ? 'text-green-600' : 'text-red-600'
                              }
                            >
                              {formatPercent(delta.ctr_delta)}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Baseline: {(delta.baseline_ctr * 100).toFixed(2)}%
                          </div>
                        </div>

                        <div>
                          <div className="text-sm text-muted-foreground">CVR</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">
                              {formatPercent(delta.cvr_delta)}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Conversions: {delta.current_conversions} (baseline: {delta.baseline_conversions})
                          </div>
                        </div>

                        <div>
                          <div className="text-sm text-muted-foreground">ROAS</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">
                              {formatPercent(delta.roas_delta)}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Clicks: {formatPercent(delta.clicks_delta)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Search Query Changes Tab */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Search Query Changes</CardTitle>
              <CardDescription>
                New queries, lost queries, and volume shifts
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loadingSearch ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : searchDeltas.length === 0 ? (
                <div className="text-center py-8 space-y-3">
                  <p className="text-muted-foreground">No search query delta data yet.</p>
                  <p className="text-sm text-muted-foreground">
                    Search query changes appear after content is published and search terms have been synced.
                  </p>
                  <Link href="/search-insights" className="text-sm text-primary underline underline-offset-2">
                    Go to Search Insights to sync →
                  </Link>
                </div>
              ) : (
                <div className="space-y-3">
                  {searchDeltas.slice(0, 20).map((delta, idx) => (
                    <div
                      key={idx}
                      className="border rounded-lg p-4 hover:bg-accent transition-colors"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="font-medium">{delta.query_text}</div>
                          <div className="text-sm text-muted-foreground">
                            {delta.master_sku}
                            {delta.after_avg_monthly_searches && (
                              <> • {delta.after_avg_monthly_searches.toLocaleString()} monthly searches</>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {getStatusBadge(delta.status)}
                          <Badge variant="outline">Score: {delta.opportunity_score}</Badge>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-3 pt-3 border-t">
                        <div>
                          <div className="text-xs text-muted-foreground">Impressions</div>
                          <div className="flex items-baseline gap-2">
                            <span className="font-semibold">{delta.after_impressions}</span>
                            {delta.before_impressions > 0 && (
                              <span
                                className={
                                  delta.impressions_delta > 0
                                    ? 'text-green-600 text-sm'
                                    : 'text-red-600 text-sm'
                                }
                              >
                                {delta.impressions_delta > 0 ? '+' : ''}
                                {delta.impressions_delta}
                              </span>
                            )}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs text-muted-foreground">Clicks</div>
                          <div className="flex items-baseline gap-2">
                            <span className="font-semibold">{delta.after_clicks}</span>
                            {delta.before_clicks > 0 && (
                              <span
                                className={
                                  delta.clicks_delta > 0
                                    ? 'text-green-600 text-sm'
                                    : 'text-red-600 text-sm'
                                }
                              >
                                {delta.clicks_delta > 0 ? '+' : ''}
                                {delta.clicks_delta}
                              </span>
                            )}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs text-muted-foreground">CTR</div>
                          <div className="font-semibold">
                            {delta.after_impressions > 0
                              ? ((delta.after_clicks / delta.after_impressions) * 100).toFixed(2)
                              : '0.00'}
                            %
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
