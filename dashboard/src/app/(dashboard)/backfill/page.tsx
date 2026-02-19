'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Metric, ProgressBar } from '@tremor/react'

interface BackfillJob {
  job_id: string
  job_type: string
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  eta_seconds: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  progress_pct: number
}

interface BackfillJobListResponse {
  jobs: BackfillJob[]
  active_count: number
  max_concurrent: number
}

interface SyncJob {
  id: string
  status: string
  job_type: string
  days_lookback: number
  queries_fetched: number
  queries_enriched: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

interface SyncJobsData {
  active: SyncJob[]
  history: SyncJob[]
}

interface CoverageData {
  total_skus: number
  total_offer_ids: number
  search_terms_coverage: number
  search_terms_sku_coverage: number
  search_terms_offer_coverage: number
  performance_coverage: number
  keywords_coverage: number
}

interface SKUFreshness {
  master_sku: string
  search_terms_age_days: number
  performance_age_days: number
  keywords_age_days: number
}

interface FreshnessData {
  freshness: SKUFreshness[]
}

interface ApiHealthData {
  error_count: number
  provider_errors: number
  latency_p95_ms: number
  rate_limit_hits: number
  sample_size: number
}

interface BackfillHealthData {
  freshness: FreshnessData | null
  coverage: CoverageData | null
  apiHealth: ApiHealthData | null
}

export default function BackfillMonitoringPage() {
  const [jobs, setJobs] = useState<BackfillJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [syncJobs, setSyncJobs] = useState<SyncJobsData | null>(null)
  const [loadingSyncJobs, setLoadingSyncJobs] = useState(true)
  const [healthData, setHealthData] = useState<BackfillHealthData | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(true)

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/backfill')
      if (!res.ok) throw new Error('Failed to fetch jobs')
      const data: BackfillJobListResponse = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      console.error('Failed to fetch backfill jobs:', err)
    } finally {
      setLoadingJobs(false)
    }
  }

  const fetchSyncJobs = async () => {
    try {
      const res = await fetch('/api/monitoring/sync-jobs')
      if (!res.ok) throw new Error('Failed to fetch sync jobs')
      const data: SyncJobsData = await res.json()
      setSyncJobs(data)
    } catch (err) {
      console.error('Failed to fetch sync jobs:', err)
    } finally {
      setLoadingSyncJobs(false)
    }
  }

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/monitoring/backfill-health')
      if (!res.ok) throw new Error('Failed to fetch health data')
      const data: BackfillHealthData = await res.json()
      setHealthData(data)
    } catch (err) {
      console.error('Failed to fetch health data:', err)
    } finally {
      setLoadingHealth(false)
    }
  }

  // Initial fetch
  useEffect(() => {
    fetchJobs()
    fetchSyncJobs()
    fetchHealth()
  }, [])

  // Auto-refresh jobs every 5 seconds if any job is running
  useEffect(() => {
    const hasRunningJobs = jobs.some((job) => job.status === 'running')
    if (!hasRunningJobs) return

    const interval = setInterval(() => {
      fetchJobs()
    }, 5000)

    return () => clearInterval(interval)
  }, [jobs])

  // Auto-refresh sync jobs every 5 seconds if any sync job is running
  useEffect(() => {
    const hasRunningSyncJobs = syncJobs?.active && syncJobs.active.length > 0
    if (!hasRunningSyncJobs) return

    const interval = setInterval(() => {
      fetchSyncJobs()
    }, 5000)

    return () => clearInterval(interval)
  }, [syncJobs])

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      running: 'bg-blue-100 text-blue-800',
      pending: 'bg-blue-50 text-blue-700',
      complete: 'bg-green-100 text-green-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      partial: 'bg-yellow-100 text-yellow-800',
      creating: 'bg-gray-100 text-gray-800',
    }
    return (
      <Badge className={colors[status] || 'bg-gray-100 text-gray-800'}>
        {status}
      </Badge>
    )
  }

  const formatETA = (seconds: number | null) => {
    if (!seconds) return 'N/A'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    if (mins > 0) return `${mins}m ${secs}s`
    return `${secs}s`
  }

  const truncateJobId = (jobId: string) => {
    return jobId.slice(0, 8)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—'
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return dateStr
    }
  }

  const getCoverageColor = (coverage: number, total: number): string => {
    const pct = total > 0 ? (coverage / total) * 100 : 0
    if (pct > 90) return 'text-green-600'
    if (pct > 50) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getCoveragePercentage = (coverage: number, total: number): string => {
    const pct = total > 0 ? (coverage / total) * 100 : 0
    return `${pct.toFixed(1)}%`
  }

  const getFreshnessColor = (ageDays: number): string => {
    if (ageDays <= 7) return '#10b981' // green
    if (ageDays <= 30) return '#fbbf24' // yellow
    if (ageDays <= 60) return '#fb923c' // orange
    return '#ef4444' // red
  }

  const getLatencyColor = (latencyMs: number): string => {
    if (latencyMs < 500) return 'text-green-600'
    if (latencyMs < 2000) return 'text-yellow-600'
    return 'text-red-600'
  }

  // Combine sync jobs for display: active first, then history
  const allSyncJobs = syncJobs
    ? [...(syncJobs.active || []), ...(syncJobs.history || [])]
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Backfill Monitoring</h1>
        <p className="text-muted-foreground mt-2">
          Monitor data collection jobs, coverage, freshness, and API health
        </p>
      </div>

      {/* Coverage KPI Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {loadingHealth || !healthData?.coverage ? (
          <>
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </>
        ) : (
          <>
            {/* Search Terms Coverage — two numbers: SKU-level + offer-level */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Search Terms Coverage</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Master SKUs</div>
                    <Metric
                      className={getCoverageColor(
                        healthData.coverage.search_terms_sku_coverage ?? healthData.coverage.search_terms_coverage,
                        healthData.coverage.total_skus
                      )}
                    >
                      {healthData.coverage.search_terms_sku_coverage ?? healthData.coverage.search_terms_coverage}/{healthData.coverage.total_skus}
                    </Metric>
                    <div className="text-xs text-muted-foreground mt-1">
                      {getCoveragePercentage(
                        healthData.coverage.search_terms_sku_coverage ?? healthData.coverage.search_terms_coverage,
                        healthData.coverage.total_skus
                      )}{' '}
                      of master SKUs
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Variant Offer IDs</div>
                    <Metric
                      className={getCoverageColor(
                        healthData.coverage.search_terms_offer_coverage ?? 0,
                        healthData.coverage.total_offer_ids ?? healthData.coverage.total_skus
                      )}
                    >
                      {healthData.coverage.search_terms_offer_coverage ?? '—'}/{healthData.coverage.total_offer_ids ?? '—'}
                    </Metric>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Performance Baselines Coverage — one number */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Performance Baselines Coverage</CardTitle>
              </CardHeader>
              <CardContent>
                <Metric
                  className={getCoverageColor(
                    healthData.coverage.performance_coverage,
                    healthData.coverage.total_skus
                  )}
                >
                  {healthData.coverage.performance_coverage}/{healthData.coverage.total_skus}
                </Metric>
                <div className="text-xs text-muted-foreground mt-1">
                  {getCoveragePercentage(
                    healthData.coverage.performance_coverage,
                    healthData.coverage.total_skus
                  )}{' '}
                  of master SKUs
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Search Term Sync Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Search Term Sync Jobs</CardTitle>
          <CardDescription>search_query_sync_jobs — search terms fetched from Google Ads</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingSyncJobs ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : allSyncJobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No search term sync jobs found.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Queries Fetched</TableHead>
                  <TableHead>Days Lookback</TableHead>
                  <TableHead>Started At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {allSyncJobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className={
                      job.status === 'running' || job.status === 'pending'
                        ? 'border-l-2 border-l-blue-500'
                        : ''
                    }
                  >
                    <TableCell className="font-mono text-xs">
                      {truncateJobId(job.id)}
                      {(job.status === 'running' || job.status === 'pending') && (
                        <Badge className="ml-2 bg-blue-100 text-blue-800 text-xs">ACTIVE</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">{job.job_type}</TableCell>
                    <TableCell>{getStatusBadge(job.status)}</TableCell>
                    <TableCell className="text-sm">
                      {job.queries_fetched ?? 0}
                      {job.queries_enriched > 0 && (
                        <span className="text-muted-foreground ml-1">
                          ({job.queries_enriched} enriched)
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">{job.days_lookback ?? '—'}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(job.started_at ?? job.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Performance Backfill Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Backfill Jobs</CardTitle>
          <CardDescription>backfill_jobs — performance metrics backfill</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingJobs ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No backfill jobs found. Start a job to see progress here.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead>ETA</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.job_id}>
                    <TableCell className="font-mono text-xs">
                      {truncateJobId(job.job_id)}
                    </TableCell>
                    <TableCell className="text-sm">{job.job_type}</TableCell>
                    <TableCell>{getStatusBadge(job.status)}</TableCell>
                    <TableCell>
                      <div className="w-32">
                        <ProgressBar value={job.progress_pct} className="mt-1" />
                        <div className="text-xs text-muted-foreground mt-1">
                          {job.progress_pct.toFixed(1)}%
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {job.completed_items}/{job.total_items}
                    </TableCell>
                    <TableCell className="text-sm">
                      {formatETA(job.eta_seconds)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Row: Data Freshness Heatmap (left) + API Health (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Data Freshness Heatmap */}
        <Card>
          <CardHeader>
            <CardTitle>Data Freshness Heatmap</CardTitle>
            <CardDescription>SKU data age by collection type</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingHealth || !healthData?.freshness ? (
              <Skeleton className="h-64 w-full" />
            ) : healthData.freshness.freshness.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No freshness data available
              </div>
            ) : (
              <div>
                <div
                  className="grid gap-1"
                  style={{
                    gridTemplateColumns: 'repeat(auto-fill, 16px)',
                    maxHeight: '300px',
                    overflowY: 'auto',
                  }}
                >
                  {healthData.freshness.freshness.slice(0, 500).map((sku) => {
                    // Use the oldest age across all data types for heatmap color
                    const maxAge = Math.max(
                      sku.search_terms_age_days,
                      sku.performance_age_days,
                      sku.keywords_age_days
                    )
                    const color = getFreshnessColor(maxAge)
                    return (
                      <div
                        key={sku.master_sku}
                        className="w-4 h-4 rounded-sm cursor-pointer hover:opacity-80"
                        style={{ backgroundColor: color }}
                        title={`${sku.master_sku}: ${maxAge} days old`}
                      />
                    )
                  })}
                </div>

                {/* Legend */}
                <div className="flex items-center gap-4 mt-4 text-xs">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#10b981' }} />
                    <span>&le;7 days</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#fbbf24' }} />
                    <span>8-30 days</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#fb923c' }} />
                    <span>31-60 days</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#ef4444' }} />
                    <span>&gt;60 days</span>
                  </div>
                </div>

                {healthData.freshness.freshness.length > 500 && (
                  <div className="text-xs text-muted-foreground mt-2">
                    Showing first 500 SKUs of {healthData.freshness.freshness.length}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* API Health Panel */}
        <Card>
          <CardHeader>
            <CardTitle>API Health</CardTitle>
            <CardDescription>Request latency and error metrics</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingHealth || !healthData?.apiHealth ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <div className="space-y-6">
                <div>
                  <div className="text-sm text-muted-foreground">Latency P95</div>
                  <Metric className={getLatencyColor(healthData.apiHealth.latency_p95_ms)}>
                    {healthData.apiHealth.latency_p95_ms.toFixed(0)}ms
                  </Metric>
                  <div className="text-xs text-muted-foreground mt-1">
                    Based on {healthData.apiHealth.sample_size} requests
                  </div>
                </div>

                <div>
                  <div className="text-sm text-muted-foreground">Error Count</div>
                  <Metric className={healthData.apiHealth.error_count > 0 ? 'text-red-600' : 'text-green-600'}>
                    {healthData.apiHealth.error_count}
                  </Metric>
                  <div className="text-xs text-muted-foreground mt-1">HTTP request errors</div>
                </div>

                <div>
                  <div className="text-sm text-muted-foreground">Rate Limit Hits</div>
                  <Metric className={healthData.apiHealth.rate_limit_hits > 0 ? 'text-yellow-600' : 'text-green-600'}>
                    {healthData.apiHealth.rate_limit_hits}
                  </Metric>
                  <div className="text-xs text-muted-foreground mt-1">
                    Provider: {healthData.apiHealth.provider_errors} errors
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
