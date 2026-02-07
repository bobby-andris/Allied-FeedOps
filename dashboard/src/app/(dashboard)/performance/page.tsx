"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, TrendingDown, RefreshCw, Download, AlertCircle, Loader2, Info } from "lucide-react"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// Types matching the API response
interface SkuPerformance {
  sku: string
  name: string
  platform: string
  publishedAt: string
  shopifyProductId: string | null
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

interface PerformanceData {
  summary: {
    totalPublished: number
    avgCtrChange: number
    avgCvrChange: number
    totalImpressions: number
    totalClicks: number
  }
  skus: SkuPerformance[]
  warnings: string[]
}

function MetricChange({ baseline, current, format = 'percent' }: { 
  baseline: number
  current: number
  format?: 'percent' | 'number' 
}) {
  // Handle case where baseline is 0
  if (baseline === 0) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground">
          {format === 'percent' ? `${current.toFixed(2)}%` : current.toLocaleString()}
        </span>
        <span className="text-xs text-muted-foreground">N/A</span>
      </div>
    )
  }

  const change = ((current - baseline) / baseline) * 100
  const isPositive = change > 0
  const isZero = change === 0
  
  return (
    <div className="flex items-center gap-1">
      <span className={isZero ? 'text-muted-foreground' : isPositive ? 'text-green-600' : 'text-red-600'}>
        {format === 'percent' ? `${current.toFixed(2)}%` : current.toLocaleString()}
      </span>
      <span className={`text-xs flex items-center ${isZero ? 'text-muted-foreground' : isPositive ? 'text-green-600' : 'text-red-600'}`}>
        {!isZero && (isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />)}
        {isZero ? '—' : `${change > 0 ? '+' : ''}${change.toFixed(1)}%`}
      </span>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Skeleton className="h-9 w-48 mb-2" />
          <Skeleton className="h-5 w-64" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-[150px]" />
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-24" />
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
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function ChangeIndicator({ value, label }: { value: number; label: string }) {
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

export default function PerformancePage() {
  const [dateRange, setDateRange] = useState<string>("30d")
  const [platform, setPlatform] = useState<string>("all")
  const [data, setData] = useState<PerformanceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const platformParam = platform === 'all' ? '' : `&platform=${platform}`
      const response = await fetch(`/api/performance?dateRange=${dateRange}${platformParam}`)
      
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
  }, [dateRange, platform])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleRefresh = () => {
    fetchData(true)
  }

  const handleExport = () => {
    if (!data) return
    
    // Create CSV content
    const headers = ['SKU', 'Product', 'Platform', 'Published', 'Baseline CTR', 'Current CTR', 'Baseline CVR', 'Current CVR', 'Impressions', 'Clicks']
    const rows = data.skus.map(sku => [
      sku.sku,
      sku.name,
      sku.platform,
      sku.publishedAt,
      sku.baseline.ctr.toFixed(2),
      sku.current.ctr.toFixed(2),
      sku.baseline.cvr.toFixed(2),
      sku.current.cvr.toFixed(2),
      sku.current.impressions,
      sku.current.clicks,
    ])
    
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `performance-${dateRange}-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <LoadingSkeleton />
  }

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
    summary: { totalPublished: 0, avgCtrChange: 0, avgCvrChange: 0, totalImpressions: 0, totalClicks: 0 },
    skus: [],
    warnings: [],
  }

  // Filter SKUs by platform tab
  const filteredSkus = platform === 'all' 
    ? performanceData.skus 
    : performanceData.skus.filter(sku => sku.platform === platform)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Performance</h1>
          <p className="text-muted-foreground">
            Track performance metrics for published master SKUs (aggregated across all variants/finishes)
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Time range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Refresh
          </Button>
          <Button variant="outline" onClick={handleExport} disabled={performanceData.skus.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Info Callout */}
      <Alert className="mb-4">
        <Info className="h-4 w-4" />
        <AlertTitle>Master SKU Aggregated Performance</AlertTitle>
        <AlertDescription>
          Performance metrics are shown per master SKU and platform, aggregated across all finish variants.
          Each master SKU typically has 28 variant finishes (e.g., Polished Brass, Satin Nickel, etc.).
          For variant-level insights, see the <a href="/search-insights" className="underline font-medium">Search Insights</a> tab.
        </AlertDescription>
      </Alert>

      {/* Warnings */}
      {performanceData.warnings.length > 0 && (
        <div className="mb-4 space-y-2">
          {performanceData.warnings.map((warning, i) => (
            <Alert key={i} variant="default">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{warning}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-5 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Published SKUs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{performanceData.summary.totalPublished}</div>
          </CardContent>
        </Card>
        
        <ChangeIndicator 
          value={performanceData.summary.avgCtrChange} 
          label="Avg CTR Change" 
        />
        
        <ChangeIndicator 
          value={performanceData.summary.avgCvrChange} 
          label="Avg CVR Change" 
        />
        
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

      {/* Platform Tabs */}
      <Tabs value={platform} onValueChange={setPlatform} className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Platforms</TabsTrigger>
          <TabsTrigger value="google">Google</TabsTrigger>
          <TabsTrigger value="bing">Bing</TabsTrigger>
          <TabsTrigger value="shopify">Shopify</TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <PerformanceTable skus={filteredSkus} />
        </TabsContent>

        <TabsContent value="google">
          <PerformanceTable skus={filteredSkus} platform="google" />
        </TabsContent>

        <TabsContent value="bing">
          <PerformanceTable skus={filteredSkus} platform="bing" />
        </TabsContent>

        <TabsContent value="shopify">
          <PerformanceTable skus={filteredSkus} platform="shopify" />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function PerformanceTable({ skus, platform }: { skus: SkuPerformance[]; platform?: string }) {
  const platformLabel = platform 
    ? platform.charAt(0).toUpperCase() + platform.slice(1) 
    : 'All Platforms'

  return (
    <Card>
      <CardHeader>
        <CardTitle>SKU Performance</CardTitle>
        <CardDescription>
          Compare baseline vs current performance for {platformLabel.toLowerCase()} published SKUs
        </CardDescription>
      </CardHeader>
      <CardContent>
        {skus.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Master SKU</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Published</TableHead>
                <TableHead>CTR</TableHead>
                <TableHead>CVR</TableHead>
                <TableHead>Impressions</TableHead>
                <TableHead>Clicks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {skus.map((sku) => (
                <TableRow key={`${sku.sku}-${sku.platform}`}>
                  <TableCell className="font-medium">{sku.sku}</TableCell>
                  <TableCell>{sku.name}</TableCell>
                  <TableCell>
                    <PlatformBadge platform={sku.platform as 'google' | 'bing' | 'shopify'} />
                  </TableCell>
                  <TableCell>{sku.publishedAt}</TableCell>
                  <TableCell>
                    <MetricChange 
                      baseline={sku.baseline.ctr} 
                      current={sku.current.ctr} 
                    />
                  </TableCell>
                  <TableCell>
                    <MetricChange 
                      baseline={sku.baseline.cvr} 
                      current={sku.current.cvr} 
                    />
                  </TableCell>
                  <TableCell>
                    <MetricChange 
                      baseline={sku.baseline.impressions} 
                      current={sku.current.impressions}
                      format="number"
                    />
                  </TableCell>
                  <TableCell>
                    <MetricChange 
                      baseline={sku.baseline.clicks} 
                      current={sku.current.clicks}
                      format="number"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            {platform 
              ? `No published SKUs for ${platformLabel} yet. Approve and publish content to see performance data.`
              : 'No published SKUs yet. Approve and publish content to see performance data.'}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
