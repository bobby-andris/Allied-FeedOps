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
  ChevronRight,
  ShieldAlert,
  ChevronDown,
} from 'lucide-react'
import Link from 'next/link'
import { BottleneckBadge } from '@/components/bottleneck/BottleneckBadge'

interface PerformanceDelta {
  master_sku: string
  platform: string
  environment: string
  publish_event_id: number
  label: 'positive' | 'negative' | 'neutral'
  confidence: number
  sample_size_treated: number
  sample_size_control: number
  days_since_publish: number | null
  primary_roas_did_lift_pct: number | null
  guardrails: {
    impressions: number | null
    conversions: number | null
    ctr: number | null
    cvr: number | null
    clicks: number | null
    cost: number | null
    conversion_value: number | null
  }
  metrics: Record<string, { did_lift_pct: number | null }>
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

interface GmcItemIssue {
  code: string
  canonical_attribute: string
  severity: string
  resolution: string
  applicable_contexts: string[]
}

interface GmcProductStatus {
  id: number
  gmc_offer_id: string
  master_sku: string | null
  offer_title: string | null
  status: string
  item_issues: GmcItemIssue[] | null
  issue_count: number
  disapproval_count: number
  synced_at: string
}

interface GmcSummary {
  total: number
  disapproved: number
  limited: number
  eligible: number
}

interface SnapshotResult {
  created: number
  type: 'search' | 'performance'
  error?: string
}

interface PerformanceSummary {
  total: number
  positive: number
  negative: number
  neutral: number
  avg_roas_did_lift_pct: number
}

interface SnapshotStaleness {
  latest_snapshot_date: string | null
  days_stale: number | null
  is_stale: boolean
}

interface BottleneckSummary {
  by_category: Record<string, number>
  total_count: number
}

export default function MonitoringPage() {
  const [performanceDeltas, setPerformanceDeltas] = useState<PerformanceDelta[]>([])
  const [searchDeltas, setSearchDeltas] = useState<SearchQueryDelta[]>([])
  const [loadingPerformance, setLoadingPerformance] = useState(false)
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [skuFilter, setSkuFilter] = useState('')
  const [activeTab, setActiveTab] = useState('performance')
  const [snapshotResult, setSnapshotResult] = useState<SnapshotResult | null>(null)
  const [performanceSummary, setPerformanceSummary] = useState<PerformanceSummary | null>(null)
  const [snapshotStaleness, setSnapshotStaleness] = useState<SnapshotStaleness | null>(null)
  const [bottleneckSummary, setBottleneckSummary] = useState<BottleneckSummary | null>(null)

  // GMC state
  const [gmcProducts, setGmcProducts] = useState<GmcProductStatus[]>([])
  const [gmcSummary, setGmcSummary] = useState<GmcSummary | null>(null)
  const [gmcLastSynced, setGmcLastSynced] = useState<string | null>(null)
  const [loadingGmc, setLoadingGmc] = useState(false)
  const [gmcSyncing, setGmcSyncing] = useState(false)
  const [gmcSyncResult, setGmcSyncResult] = useState<{ success: boolean; message: string } | null>(null)
  const [expandedGmcRows, setExpandedGmcRows] = useState<Set<number>>(new Set())
  const [gmcLoaded, setGmcLoaded] = useState(false)

  const fetchPerformanceDeltas = async () => {
    setLoadingPerformance(true)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/monitoring/performance-delta?${params}`)
      if (!res.ok) throw new Error('Failed to fetch performance deltas')

      const data = await res.json()
      setPerformanceDeltas(data.deltas || [])
      setPerformanceSummary(data.summary || null)
      setSnapshotStaleness(data.staleness || null)
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

  const fetchGmcStatus = async () => {
    setLoadingGmc(true)
    try {
      const params = new URLSearchParams()
      if (skuFilter) params.set('master_sku', skuFilter)

      const res = await fetch(`/api/gmc/status?${params}`)
      if (!res.ok) throw new Error('Failed to fetch GMC status')

      const data = await res.json()
      setGmcProducts(data.products || [])
      setGmcSummary(data.summary || null)
      setGmcLastSynced(data.last_synced || null)
      setGmcLoaded(true)
    } catch (err) {
      console.error('Failed to fetch GMC status:', err)
    } finally {
      setLoadingGmc(false)
    }
  }

  const triggerGmcSync = async () => {
    setGmcSyncing(true)
    setGmcSyncResult(null)
    try {
      const res = await fetch('/api/gmc/sync', { method: 'POST' })
      const data = await res.json()

      if (!res.ok) {
        setGmcSyncResult({ success: false, message: data.error || 'Sync failed' })
      } else {
        setGmcSyncResult({
          success: true,
          message: `GMC sync started (job ${data.job_id?.slice(0, 8)}...). Refresh in ~30 seconds to see updated data.`,
        })
      }
    } catch (err) {
      setGmcSyncResult({ success: false, message: `Sync error: ${String(err)}` })
    } finally {
      setGmcSyncing(false)
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
      setSnapshotResult({
        created: data.snapshots_created ?? data.captured ?? 0,
        type: 'performance',
      })

      // Refresh data
      fetchPerformanceDeltas()
      fetchSearchDeltas()
    } catch (err) {
      console.error('Failed to capture performance snapshots:', err)
      setSnapshotResult({ created: 0, type: 'performance', error: 'Failed to capture performance snapshots' })
    }
  }

  const toggleGmcRow = (id: number) => {
    setExpandedGmcRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  useEffect(() => {
    // Fetch bottleneck summary once on mount (no SKU filter — always full picture)
    fetch('/api/bottleneck/status?limit=1')
      .then((r) => r.json())
      .then((json) => setBottleneckSummary({ by_category: json.by_category ?? {}, total_count: json.total_count ?? 0 }))
      .catch(() => {/* non-critical */ })
  }, [])

  useEffect(() => {
    fetchPerformanceDeltas()
    fetchSearchDeltas()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skuFilter])

  // Lazy-load GMC data when tab is first selected
  useEffect(() => {
    if (activeTab === 'gmc' && !gmcLoaded) {
      fetchGmcStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const getLabelIcon = (label: string) => {
    switch (label) {
      case 'positive':
        return <TrendingUp className="h-4 w-4 text-green-500" />
      case 'negative':
        return <TrendingDown className="h-4 w-4 text-red-500" />
      default:
        return <Minus className="h-4 w-4 text-gray-500" />
    }
  }

  const getLabelBadge = (label: string) => {
    const colors = {
      positive: 'bg-green-100 text-green-800',
      negative: 'bg-red-100 text-red-800',
      neutral: 'bg-gray-100 text-gray-800',
    }
    return (
      <Badge className={colors[label as keyof typeof colors] || ''}>
        {label}
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

  const getGmcStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      disapproved: 'bg-red-100 text-red-800',
      limited: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      pending: 'bg-blue-100 text-blue-800',
    }
    return (
      <Badge className={colors[status] || 'bg-gray-100 text-gray-800'}>
        {status}
      </Badge>
    )
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'disapproval':
        return 'text-red-600'
      case 'demotion':
        return 'text-orange-600'
      default:
        return 'text-yellow-600'
    }
  }

  const formatPercent = (value: number | null) => {
    if (value === null || Number.isNaN(value)) return 'n/a'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return 'Never'
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Post-Publish Monitoring</h1>
        <p className="text-muted-foreground mt-2">
          Track performance changes and search query shifts after content optimization
        </p>
      </div>

      {/* Bottleneck Diagnostics Link */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Bottleneck Diagnostics</CardTitle>
              <CardDescription>Root cause classification for underperforming SKUs</CardDescription>
            </div>
            <Link href="/monitoring/bottleneck">
              <Button variant="outline" size="sm">
                View Diagnostic View
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        {bottleneckSummary && bottleneckSummary.total_count > 0 && (
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-3">
              {Object.entries(bottleneckSummary.by_category)
                .filter(([, count]) => count > 0)
                .sort(([, a], [, b]) => b - a)
                .map(([category, count]) => (
                  <div key={category} className="flex items-center gap-2">
                    <BottleneckBadge classification={category} />
                    <span className="text-sm text-muted-foreground">{count}</span>
                  </div>
                ))}
              <span className="text-sm text-muted-foreground self-center">
                ({bottleneckSummary.total_count} total)
              </span>
            </div>
          </CardContent>
        )}
        {bottleneckSummary && bottleneckSummary.total_count === 0 && (
          <CardContent className="pt-0">
            <p className="text-sm text-muted-foreground">
              No classifications yet.{' '}
              <Link href="/monitoring/bottleneck" className="text-primary underline underline-offset-2">
                Run classifier
              </Link>
              {' '}to diagnose underperforming SKUs.
            </p>
          </CardContent>
        )}
      </Card>

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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="performance">
            <Activity className="h-4 w-4 mr-2" />
            Performance Deltas
          </TabsTrigger>
          <TabsTrigger value="search">
            <Search className="h-4 w-4 mr-2" />
            Search Query Changes
          </TabsTrigger>
          <TabsTrigger value="gmc">
            <ShieldAlert className="h-4 w-4 mr-2" />
            GMC Status
          </TabsTrigger>
        </TabsList>

        {/* Performance Deltas Tab */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Changes</CardTitle>
              <CardDescription>
                Difference-in-differences impact by publish event
              </CardDescription>
            </CardHeader>
            <CardContent>
              {snapshotStaleness && (
                <Alert className="mb-4">
                  <AlertDescription>
                    Snapshot freshness:
                    {' '}
                    {snapshotStaleness.latest_snapshot_date || 'unknown'}
                    {' '}
                    (
                    {snapshotStaleness.days_stale ?? 'n/a'}
                    {' '}
                    days stale)
                    {snapshotStaleness.is_stale && (
                      <span className="text-red-600 ml-2">Data may be stale</span>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              {performanceSummary && performanceSummary.total > 0 && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Positive</div>
                    <div className="text-xl font-semibold">{performanceSummary.positive}</div>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Neutral</div>
                    <div className="text-xl font-semibold">{performanceSummary.neutral}</div>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Negative</div>
                    <div className="text-xl font-semibold">{performanceSummary.negative}</div>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Avg ROAS DID</div>
                    <div className="text-xl font-semibold">
                      {formatPercent(performanceSummary.avg_roas_did_lift_pct)}
                    </div>
                  </div>
                </div>
              )}

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
                          {getLabelIcon(delta.label)}
                          <div>
                            <div className="font-semibold">{delta.master_sku}</div>
                            <div className="text-sm text-muted-foreground">
                              {delta.platform}
                              {' • '}
                              {delta.environment}
                              {' • '}
                              {delta.days_since_publish ?? 'n/a'}
                              {' '}
                              days since publish
                            </div>
                          </div>
                        </div>
                        {getLabelBadge(delta.label)}
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <div>
                          <div className="text-sm text-muted-foreground">ROAS DID (Primary)</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">
                              {formatPercent(delta.primary_roas_did_lift_pct)}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Confidence: {(delta.confidence * 100).toFixed(0)}%
                          </div>
                        </div>

                        <div>
                          <div className="text-sm text-muted-foreground">Guardrails</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-sm">
                              Imp:
                              {' '}
                              {formatPercent(delta.guardrails.impressions)}
                            </span>
                            <span className="text-sm">
                              Conv:
                              {' '}
                              {formatPercent(delta.guardrails.conversions)}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            CTR:
                            {' '}
                            {formatPercent(delta.guardrails.ctr)}
                            {' • '}
                            CVR:
                            {' '}
                            {formatPercent(delta.guardrails.cvr)}
                          </div>
                        </div>

                        <div>
                          <div className="text-sm text-muted-foreground">Sample Size</div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-2xl font-bold">{delta.sample_size_treated}</span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Control: {delta.sample_size_control} • Event #{delta.publish_event_id}
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

        {/* GMC Status Tab */}
        <TabsContent value="gmc" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>GMC Disapproval Status</CardTitle>
                  <CardDescription>
                    Products disapproved or demoted in Google Merchant Center
                  </CardDescription>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={fetchGmcStatus}
                    disabled={loadingGmc}
                  >
                    <RefreshCw className={`h-4 w-4 mr-2 ${loadingGmc ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={triggerGmcSync}
                    disabled={gmcSyncing}
                  >
                    <ShieldAlert className="h-4 w-4 mr-2" />
                    {gmcSyncing ? 'Syncing...' : 'Sync Now'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {gmcSyncResult && (
                <Alert variant={gmcSyncResult.success ? 'default' : 'destructive'}>
                  {gmcSyncResult.success ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  <AlertDescription>{gmcSyncResult.message}</AlertDescription>
                </Alert>
              )}

              {/* Summary cards */}
              {gmcSummary && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Total Synced</div>
                    <div className="text-xl font-semibold">{gmcSummary.total}</div>
                  </div>
                  <div className="border border-red-200 rounded p-3">
                    <div className="text-xs text-red-600">Disapproved</div>
                    <div className="text-xl font-semibold text-red-700">{gmcSummary.disapproved}</div>
                  </div>
                  <div className="border border-yellow-200 rounded p-3">
                    <div className="text-xs text-yellow-600">Limited</div>
                    <div className="text-xl font-semibold text-yellow-700">{gmcSummary.limited}</div>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-xs text-muted-foreground">Last Sync</div>
                    <div className="text-sm font-medium">{formatDate(gmcLastSynced)}</div>
                  </div>
                </div>
              )}

              {/* Product table */}
              {loadingGmc ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : !gmcLoaded ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">Loading GMC status...</p>
                </div>
              ) : gmcProducts.length === 0 ? (
                <div className="text-center py-8 space-y-3">
                  <ShieldAlert className="h-12 w-12 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground">No disapproved or limited products found.</p>
                  <p className="text-sm text-muted-foreground">
                    Click &quot;Sync Now&quot; to fetch current data from Google Merchant Center.
                    If the table is empty after syncing, all products are eligible.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {/* Table header */}
                  <div className="grid grid-cols-12 gap-2 px-3 py-2 text-xs text-muted-foreground font-medium border-b">
                    <div className="col-span-2">SKU</div>
                    <div className="col-span-3">Title</div>
                    <div className="col-span-2">Status</div>
                    <div className="col-span-2">Issues</div>
                    <div className="col-span-2">Synced</div>
                    <div className="col-span-1"></div>
                  </div>

                  {gmcProducts.map((product) => (
                    <div key={product.id} className="border rounded-lg overflow-hidden">
                      {/* Row */}
                      <div
                        className="grid grid-cols-12 gap-2 px-3 py-3 hover:bg-accent transition-colors cursor-pointer items-center"
                        onClick={() => toggleGmcRow(product.id)}
                      >
                        <div className="col-span-2">
                          <div className="font-medium text-sm">
                            {product.master_sku || '—'}
                          </div>
                          <div className="text-xs text-muted-foreground truncate">
                            {product.gmc_offer_id.slice(-12)}
                          </div>
                        </div>
                        <div className="col-span-3">
                          <div className="text-sm truncate" title={product.offer_title || undefined}>
                            {product.offer_title || <span className="text-muted-foreground">No title</span>}
                          </div>
                        </div>
                        <div className="col-span-2">
                          {getGmcStatusBadge(product.status)}
                        </div>
                        <div className="col-span-2">
                          <div className="text-sm">
                            {product.disapproval_count > 0 && (
                              <span className="text-red-600 font-medium">
                                {product.disapproval_count} disapproval{product.disapproval_count !== 1 ? 's' : ''}
                              </span>
                            )}
                            {product.disapproval_count > 0 && product.issue_count > product.disapproval_count && (
                              <span className="text-muted-foreground"> + </span>
                            )}
                            {product.issue_count > product.disapproval_count && (
                              <span className="text-yellow-600">
                                {product.issue_count - product.disapproval_count} warning{product.issue_count - product.disapproval_count !== 1 ? 's' : ''}
                              </span>
                            )}
                            {product.issue_count === 0 && (
                              <span className="text-muted-foreground text-xs">None</span>
                            )}
                          </div>
                        </div>
                        <div className="col-span-2 text-xs text-muted-foreground">
                          {formatDate(product.synced_at)}
                        </div>
                        <div className="col-span-1 flex justify-end">
                          <ChevronDown
                            className={`h-4 w-4 text-muted-foreground transition-transform ${
                              expandedGmcRows.has(product.id) ? 'rotate-180' : ''
                            }`}
                          />
                        </div>
                      </div>

                      {/* Expanded issue detail */}
                      {expandedGmcRows.has(product.id) && (
                        <div className="border-t bg-muted/30 px-4 py-3 space-y-2">
                          <div className="text-xs font-medium text-muted-foreground mb-2">
                            Full Offer ID: {product.gmc_offer_id}
                          </div>
                          {!product.item_issues || product.item_issues.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No item issues recorded.</p>
                          ) : (
                            <div className="space-y-2">
                              {product.item_issues.map((issue, i) => (
                                <div key={i} className="bg-background border rounded p-3 text-sm">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                      <span className={`font-medium ${getSeverityColor(issue.severity)}`}>
                                        [{issue.severity.toUpperCase()}]
                                      </span>
                                      {' '}
                                      <span className="font-medium">{issue.code}</span>
                                      {issue.canonical_attribute && (
                                        <span className="text-muted-foreground ml-2">
                                          ({issue.canonical_attribute})
                                        </span>
                                      )}
                                    </div>
                                    {issue.resolution && (
                                      <Badge variant="outline" className="text-xs shrink-0">
                                        {issue.resolution.replace(/_/g, ' ').toLowerCase()}
                                      </Badge>
                                    )}
                                  </div>
                                  {issue.applicable_contexts.length > 0 && (
                                    <div className="mt-1 text-xs text-muted-foreground">
                                      Affects: {issue.applicable_contexts.join(', ')}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
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
