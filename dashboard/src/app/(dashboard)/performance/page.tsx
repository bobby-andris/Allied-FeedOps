"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertCircle,
  Loader2,
  Info,
  Minus,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// Types matching the API response
interface SkuPerformance {
  sku: string
  name: string
  platform: string
  publishedAt: string
  daysSincePublish: number
  hasSnapshot: boolean
  baselineWindow: string
  snapshotWindow: string
  baseline: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
  current: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
}

interface VariantPerformance {
  gmc_offer_id: string
  finish: string | null
  finish_code: string | null
  impressions: number
  clicks: number
  ctr: number
}

interface SearchTerm {
  query_text: string
  impressions: number
  clicks: number
  ctr: number
}

interface SkuDetail {
  variants: VariantPerformance[]
  topSearchTerms: SearchTerm[]
}

interface PerformanceData {
  summary: {
    totalPublished: number
    totalWithSnapshot: number
    avgCtrChange: number
    avgCvrChange: number
    totalImpressions: number
    totalClicks: number
  }
  skus: SkuPerformance[]
  skuDetail?: SkuDetail | null
  warnings: string[]
}

type SortColumn = 'impressions' | 'clicks' | 'ctr' | 'cvr' | 'days'
type SortDir = 'asc' | 'desc'
type FilterMode = 'published' | 'all'
type TimeWindow = '7d' | '30d' | '60d'

// ---- Sub-components ----

function DeltaCell({
  baseline,
  current,
  format,
  hasSnapshot,
}: {
  baseline: number
  current: number
  format: 'percent' | 'number'
  hasSnapshot: boolean
}) {
  if (!hasSnapshot) {
    const baselineStr = format === 'percent'
      ? `${(baseline * 100).toFixed(2)}%`
      : baseline.toLocaleString()
    return (
      <div className="space-y-0.5">
        <div className="font-medium text-muted-foreground">{baselineStr}</div>
        <Badge variant="outline" className="text-xs text-muted-foreground">No snapshot</Badge>
      </div>
    )
  }

  // For percent format, values come as decimal (e.g. 0.045 = 4.5%)
  const displayCurrent = format === 'percent'
    ? `${(current * 100).toFixed(2)}%`
    : current.toLocaleString()
  const displayBaseline = format === 'percent'
    ? `${(baseline * 100).toFixed(2)}%`
    : baseline.toLocaleString()

  const deltaPct = baseline > 0
    ? ((current - baseline) / baseline) * 100
    : null

  const isPositive = deltaPct !== null && deltaPct >= 3
  const isNegative = deltaPct !== null && deltaPct <= -3

  const deltaColor = isPositive
    ? 'text-green-600'
    : isNegative
    ? 'text-red-600'
    : 'text-muted-foreground'

  const deltaStr = deltaPct === null
    ? '—'
    : `${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(1)}%`

  return (
    <div className="space-y-0.5">
      <div className="font-medium">{displayCurrent}</div>
      <div className="text-xs text-muted-foreground flex items-center gap-1">
        <span>{displayBaseline} →</span>
        <span className={deltaColor + ' font-medium'}>{deltaStr}</span>
      </div>
    </div>
  )
}

function SortIcon({ column, sortColumn, sortDir }: { column: SortColumn; sortColumn: SortColumn; sortDir: SortDir }) {
  if (sortColumn !== column) return <ArrowUpDown className="ml-1 h-3 w-3 inline text-muted-foreground" />
  return sortDir === 'asc'
    ? <ArrowUp className="ml-1 h-3 w-3 inline text-foreground" />
    : <ArrowDown className="ml-1 h-3 w-3 inline text-foreground" />
}

function computeDelta(current: number, baseline: number): number {
  return ((current - baseline) / Math.max(baseline, 0.0001)) * 100
}

function TrendIcon({ impressionsDelta }: { impressionsDelta: number }) {
  if (impressionsDelta >= 3) return <TrendingUp className="h-4 w-4 text-green-600" />
  if (impressionsDelta <= -3) return <TrendingDown className="h-4 w-4 text-red-600" />
  return <Minus className="h-4 w-4 text-muted-foreground" />
}

function LoadingSkeleton() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Skeleton className="h-9 w-48 mb-2" />
          <Skeleton className="h-5 w-72" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-[120px]" />
          <Skeleton className="h-10 w-[120px]" />
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-32" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-5 mb-8">
        {[...Array(5)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32 mb-2" />
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function ChangeCard({ value, label }: { value: number; label: string }) {
  const isPositive = value > 0
  const isZero = value === 0 || isNaN(value)
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold flex items-center gap-1 ${
          isZero ? 'text-muted-foreground' : isPositive ? 'text-green-600' : 'text-red-600'
        }`}>
          {!isZero && (isPositive ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />)}
          {isZero ? '—' : `${isPositive ? '+' : ''}${value.toFixed(1)}%`}
        </div>
      </CardContent>
    </Card>
  )
}

function SortableHeader({
  col,
  sortColumn,
  sortDir,
  onSort,
  children,
}: {
  col: SortColumn
  sortColumn: SortColumn
  sortDir: SortDir
  onSort: (col: SortColumn) => void
  children: React.ReactNode
}) {
  return (
    <TableHead
      className="cursor-pointer select-none hover:text-foreground whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      {children}
      <SortIcon column={col} sortColumn={sortColumn} sortDir={sortDir} />
    </TableHead>
  )
}

function ExpandedSkuDetail({ detail, loading }: { detail: SkuDetail | null; loading: boolean }) {
  if (loading) return <div className="p-4"><Skeleton className="h-32 w-full" /></div>
  if (!detail) return <div className="p-4 text-muted-foreground">No detail data available.</div>

  return (
    <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-6 bg-muted/20 rounded-lg">
      {/* Variant breakdown */}
      <div>
        <h4 className="font-semibold text-sm mb-3">Variant Performance (by finish)</h4>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Finish</TableHead>
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
              <TableHead className="text-right">CTR</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {detail.variants.map((v) => (
              <TableRow key={v.gmc_offer_id}>
                <TableCell className="text-sm">{v.finish ?? v.gmc_offer_id.split('_').pop()}</TableCell>
                <TableCell className="text-right text-sm">{v.impressions.toLocaleString()}</TableCell>
                <TableCell className="text-right text-sm">{v.clicks.toLocaleString()}</TableCell>
                <TableCell className="text-right text-sm">{v.ctr.toFixed(3)}%</TableCell>
              </TableRow>
            ))}
            {detail.variants.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  No variant data available
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Top search terms */}
      <div>
        <h4 className="font-semibold text-sm mb-3">Top Search Terms</h4>
        <div className="space-y-2">
          {detail.topSearchTerms.map((term, i) => (
            <div key={i} className="flex items-center justify-between text-sm py-1 border-b last:border-0">
              <span className="text-foreground truncate max-w-[60%]">{term.query_text}</span>
              <span className="text-muted-foreground text-xs">{term.impressions.toLocaleString()} impr</span>
            </div>
          ))}
          {detail.topSearchTerms.length === 0 && (
            <p className="text-muted-foreground text-sm">No search term data available</p>
          )}
        </div>
      </div>
    </div>
  )
}

function PerformanceTable({
  skus,
  filterMode,
  sortColumn,
  sortDir,
  onSort,
  expandedSku,
  skuDetail,
  detailLoading,
  onRowClick,
}: {
  skus: SkuPerformance[]
  filterMode: FilterMode
  sortColumn: SortColumn
  sortDir: SortDir
  onSort: (col: SortColumn) => void
  expandedSku: string | null
  skuDetail: SkuDetail | null
  detailLoading: boolean
  onRowClick: (skuKey: string) => void
}) {
  // Apply filter
  const filtered = filterMode === 'published'
    ? skus.filter(s => s.hasSnapshot)
    : skus

  // Apply sort
  const sorted = [...filtered].sort((a, b) => {
    let aVal: number
    let bVal: number

    if (sortColumn === 'days') {
      aVal = a.daysSincePublish
      bVal = b.daysSincePublish
    } else if (sortColumn === 'impressions') {
      aVal = computeDelta(a.current.impressions, a.baseline.impressions)
      bVal = computeDelta(b.current.impressions, b.baseline.impressions)
    } else if (sortColumn === 'clicks') {
      aVal = computeDelta(a.current.clicks, a.baseline.clicks)
      bVal = computeDelta(b.current.clicks, b.baseline.clicks)
    } else if (sortColumn === 'ctr') {
      aVal = computeDelta(a.current.ctr, a.baseline.ctr)
      bVal = computeDelta(b.current.ctr, b.baseline.ctr)
    } else {
      // cvr
      aVal = computeDelta(a.current.cvr, a.baseline.cvr)
      bVal = computeDelta(b.current.cvr, b.baseline.cvr)
    }

    return sortDir === 'asc' ? aVal - bVal : bVal - aVal
  })

  if (sorted.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No published SKUs with snapshot data for the selected window.
        Try expanding the snapshot window or run capture-snapshot.
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[160px]">SKU</TableHead>
          <TableHead>Platform</TableHead>
          <SortableHeader col="days" sortColumn={sortColumn} sortDir={sortDir} onSort={onSort}>Published</SortableHeader>
          <SortableHeader col="ctr" sortColumn={sortColumn} sortDir={sortDir} onSort={onSort}>CTR</SortableHeader>
          <SortableHeader col="impressions" sortColumn={sortColumn} sortDir={sortDir} onSort={onSort}>Impressions</SortableHeader>
          <SortableHeader col="clicks" sortColumn={sortColumn} sortDir={sortDir} onSort={onSort}>Clicks</SortableHeader>
          <SortableHeader col="cvr" sortColumn={sortColumn} sortDir={sortDir} onSort={onSort}>CVR</SortableHeader>
          <TableHead className="w-12">Trend</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((sku) => {
          const skuKey = `${sku.sku}::${sku.platform}`
          const isExpanded = expandedSku === skuKey
          const impressionsDelta = computeDelta(sku.current.impressions, sku.baseline.impressions)
          return (
            <>
              <TableRow
                key={skuKey}
                className={`cursor-pointer hover:bg-muted/50 transition-colors ${!sku.hasSnapshot ? 'bg-muted/30' : ''}`}
                onClick={() => onRowClick(skuKey)}
              >
                <TableCell>
                  <div className="flex items-center gap-1">
                    {isExpanded
                      ? <ChevronUp className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                      : <ChevronDown className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                    }
                    <div>
                      <div className="font-medium">{sku.sku}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-[130px]">{sku.name}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <PlatformBadge platform={sku.platform as 'google' | 'bing' | 'shopify'} />
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <div>{sku.publishedAt}</div>
                  <div className="text-xs text-muted-foreground">{sku.daysSincePublish}d ago</div>
                </TableCell>
                <TableCell>
                  <DeltaCell
                    baseline={sku.baseline.ctr}
                    current={sku.current.ctr}
                    format="percent"
                    hasSnapshot={sku.hasSnapshot}
                  />
                </TableCell>
                <TableCell>
                  <DeltaCell
                    baseline={sku.baseline.impressions}
                    current={sku.current.impressions}
                    format="number"
                    hasSnapshot={sku.hasSnapshot}
                  />
                </TableCell>
                <TableCell>
                  <DeltaCell
                    baseline={sku.baseline.clicks}
                    current={sku.current.clicks}
                    format="number"
                    hasSnapshot={sku.hasSnapshot}
                  />
                </TableCell>
                <TableCell>
                  {sku.baseline.cvr === 0 ? (
                    <span className="text-muted-foreground text-sm" title="Low data">—</span>
                  ) : (
                    <DeltaCell
                      baseline={sku.baseline.cvr}
                      current={sku.current.cvr}
                      format="percent"
                      hasSnapshot={sku.hasSnapshot}
                    />
                  )}
                </TableCell>
                <TableCell>
                  {sku.hasSnapshot
                    ? <TrendIcon impressionsDelta={impressionsDelta} />
                    : <Minus className="h-4 w-4 text-muted-foreground opacity-40" />
                  }
                </TableCell>
              </TableRow>
              {isExpanded && (
                <TableRow key={`${skuKey}--detail`}>
                  <TableCell colSpan={8} className="p-0">
                    <ExpandedSkuDetail detail={skuDetail} loading={detailLoading} />
                  </TableCell>
                </TableRow>
              )}
            </>
          )
        })}
      </TableBody>
    </Table>
  )
}

// ---- Main Page ----

export default function PerformancePage() {
  const [baselineWindow, setBaselineWindow] = useState<TimeWindow>('30d')
  const [snapshotWindow, setSnapshotWindow] = useState<TimeWindow>('30d')
  const [platform, setPlatform] = useState<string>('all')
  const [filterMode, setFilterMode] = useState<FilterMode>('published')
  const [sortColumn, setSortColumn] = useState<SortColumn>('days')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [data, setData] = useState<PerformanceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Inline SKU detail state
  const [expandedSku, setExpandedSku] = useState<string | null>(null)
  const [skuDetail, setSkuDetail] = useState<SkuDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const platformParam = platform !== 'all' ? `&platform=${platform}` : ''
      const url = `/api/performance?baselineWindow=${baselineWindow}&snapshotWindow=${snapshotWindow}${platformParam}`
      const response = await fetch(url)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to fetch performance data')
      }

      const result = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [baselineWindow, snapshotWindow, platform])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSort = (col: SortColumn) => {
    if (sortColumn === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(col)
      setSortDir('asc')
    }
  }

  const handleRowClick = useCallback(async (skuKey: string) => {
    if (expandedSku === skuKey) {
      setExpandedSku(null)
      setSkuDetail(null)
      return
    }
    setExpandedSku(skuKey)
    setDetailLoading(true)
    try {
      const masterSku = skuKey.split('::')[0]
      const res = await fetch(`/api/performance?sku=${encodeURIComponent(masterSku)}&snapshotWindow=${snapshotWindow}&baselineWindow=${baselineWindow}`)
      const json = await res.json()
      setSkuDetail(json.skuDetail)
    } finally {
      setDetailLoading(false)
    }
  }, [expandedSku, snapshotWindow, baselineWindow])

  if (loading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="p-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>Failed to load performance data: {error}</span>
            <Button variant="outline" size="sm" onClick={() => fetchData()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const performanceData = data || {
    summary: {
      totalPublished: 0,
      totalWithSnapshot: 0,
      avgCtrChange: 0,
      avgCvrChange: 0,
      totalImpressions: 0,
      totalClicks: 0,
    },
    skus: [],
    warnings: [],
  }

  // Filter SKUs by platform tab (server already filters, but handle 'all' client-side too)
  const tabSkus = platform === 'all'
    ? performanceData.skus
    : performanceData.skus.filter(s => s.platform === platform)

  const windowOptions: { value: TimeWindow; label: string }[] = [
    { value: '7d', label: '7 days' },
    { value: '30d', label: '30 days' },
    { value: '60d', label: '60 days' },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Performance</h1>
          <p className="text-muted-foreground mt-1">
            Published SKU metrics: pre-publish baseline vs. post-publish snapshot
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {/* Baseline window */}
          <div className="flex items-center gap-1.5">
            <span className="text-sm text-muted-foreground whitespace-nowrap">Baseline</span>
            <Select value={baselineWindow} onValueChange={(v) => setBaselineWindow(v as TimeWindow)}>
              <SelectTrigger className="w-[110px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {windowOptions.map(o => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* Snapshot window */}
          <div className="flex items-center gap-1.5">
            <span className="text-sm text-muted-foreground whitespace-nowrap">Snapshot</span>
            <Select value={snapshotWindow} onValueChange={(v) => setSnapshotWindow(v as TimeWindow)}>
              <SelectTrigger className="w-[110px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {windowOptions.map(o => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* Refresh */}
          <Button variant="outline" onClick={() => fetchData(true)} disabled={refreshing}>
            {refreshing
              ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              : <RefreshCw className="h-4 w-4 mr-2" />
            }
            Refresh
          </Button>
          {/* Filter toggle */}
          <div className="flex rounded-md border overflow-hidden">
            <button
              className={`px-3 py-2 text-sm transition-colors ${
                filterMode === 'published'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setFilterMode('published')}
            >
              With snapshot
            </button>
            <button
              className={`px-3 py-2 text-sm transition-colors ${
                filterMode === 'all'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setFilterMode('all')}
            >
              All SKUs
            </button>
          </div>
        </div>
      </div>

      {/* Info banner */}
      <Alert className="mb-4">
        <Info className="h-4 w-4" />
        <AlertTitle>Snapshot-based comparison</AlertTitle>
        <AlertDescription>
          Metrics are sourced from stored performance snapshots, not live Google Ads data.
          Baseline is the 30-day pre-publish window captured at optimization time.
          Impressions and clicks are shown as daily averages (snapshot total ÷ window days) for valid comparison.
          CTR and CVR are rates and compared directly.
        </AlertDescription>
      </Alert>

      {/* Warnings */}
      {performanceData.warnings.length > 0 && (
        <div className="mb-4 space-y-2">
          {performanceData.warnings.map((warning, i) => (
            <Alert key={i}>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{warning}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-5 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">SKUs with Snapshot</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceData.summary.totalWithSnapshot}
              <span className="text-sm font-normal text-muted-foreground ml-1">
                / {performanceData.summary.totalPublished}
              </span>
            </div>
          </CardContent>
        </Card>

        <ChangeCard value={performanceData.summary.avgCtrChange} label="Avg CTR Change" />
        <ChangeCard value={performanceData.summary.avgCvrChange} label="Avg CVR Change" />

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Impressions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceData.summary.totalImpressions.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Clicks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceData.summary.totalClicks.toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Platform tabs */}
      <Tabs value={platform} onValueChange={setPlatform} className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Platforms</TabsTrigger>
          <TabsTrigger value="google">Google</TabsTrigger>
          <TabsTrigger value="bing">Bing</TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <Card>
            <CardHeader>
              <CardTitle>SKU Performance</CardTitle>
              <CardDescription>
                Baseline vs. post-publish snapshot — all platforms. Click a row to view variant breakdown.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PerformanceTable
                skus={tabSkus}
                filterMode={filterMode}
                sortColumn={sortColumn}
                sortDir={sortDir}
                onSort={handleSort}
                expandedSku={expandedSku}
                skuDetail={skuDetail}
                detailLoading={detailLoading}
                onRowClick={handleRowClick}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="google">
          <Card>
            <CardHeader>
              <CardTitle>Google SKU Performance</CardTitle>
              <CardDescription>
                Baseline vs. post-publish snapshot — Google Shopping. Click a row to view variant breakdown.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PerformanceTable
                skus={tabSkus}
                filterMode={filterMode}
                sortColumn={sortColumn}
                sortDir={sortDir}
                onSort={handleSort}
                expandedSku={expandedSku}
                skuDetail={skuDetail}
                detailLoading={detailLoading}
                onRowClick={handleRowClick}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bing">
          <Card>
            <CardHeader>
              <CardTitle>Bing SKU Performance</CardTitle>
              <CardDescription>
                Baseline vs. post-publish snapshot — Bing Shopping. Click a row to view variant breakdown.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PerformanceTable
                skus={tabSkus}
                filterMode={filterMode}
                sortColumn={sortColumn}
                sortDir={sortDir}
                onSort={handleSort}
                expandedSku={expandedSku}
                skuDetail={skuDetail}
                detailLoading={detailLoading}
                onRowClick={handleRowClick}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
