'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import {
  QueryTable,
  VariantSelector,
  FinishInsights,
  GapAnalysis,
  SyncStatusBanner,
} from '@/components/search-insights'
import {
  Search,
  TrendingUp,
  Eye,
  MousePointer,
  DollarSign,
  Target,
} from 'lucide-react'
import { CompetitionLevel } from '@/lib/supabase/types'

type Platform = 'google' | 'bing' | 'shopify'
type ViewType = 'aggregate' | 'variant'

interface StatsData {
  totalQueries: number
  totalImpressions: number
  totalClicks: number
  totalConversions: number
  totalConversionValue: number
  ctr: number
  cvr: number
}

interface FinishData {
  finish: string | null
  finish_code: string | null
  queries: Array<{
    query_text: string
    impressions: number
    clicks: number
  }>
  totalImpressions: number
  totalClicks: number
}

interface SearchInsightsData {
  stats?: StatsData
  queries?: Array<{
    query_text: string
    impressions?: number
    total_impressions?: number
    clicks?: number
    total_clicks?: number
    conversions?: number
    total_conversions?: number
    conversion_value?: number
    total_conversion_value?: number
    avg_monthly_searches?: number | null
    competition?: CompetitionLevel | null
  }>
  availableFinishes?: Array<{ finish: string | null; finish_code: string | null; count?: number }>
  byFinish?: Record<string, FinishData>
  note?: string
}

export default function SearchInsightsPage() {
  const [data, setData] = useState<SearchInsightsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [skuInput, setSkuInput] = useState('')
  const [activeSku, setActiveSku] = useState<string | null>(null)
  const [platform, setPlatform] = useState<Platform>('google')
  const [viewType, setViewType] = useState<ViewType>('aggregate')
  const [selectedFinish, setSelectedFinish] = useState<string | null>(null)
  const [lastSynced, setLastSynced] = useState<string | null>(null)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)

  // Fetch initial sync info
  useEffect(() => {
    async function fetchSyncInfo() {
      try {
        const res = await fetch('/api/search-insights/sync')
        if (res.ok) {
          const syncData = await res.json()
          setLastSynced(syncData.lastSync)
        }
      } catch (err) {
        console.error('Failed to fetch sync info:', err)
      }
    }
    fetchSyncInfo()
  }, [])

  const fetchData = useCallback(async () => {
    if (!activeSku) {
      setData(null)
      return
    }

    setLoading(true)
    try {
      const params = new URLSearchParams({
        platform,
        view: viewType,
        sku: activeSku,
        ...(selectedFinish && { finish: selectedFinish }),
      })

      const res = await fetch(`/api/search-insights?${params}`)
      if (res.ok) {
        const json = await res.json()
        setData(json)
      } else {
        console.error('Failed to fetch search insights')
        setData(null)
      }
    } catch (err) {
      console.error('Error fetching search insights:', err)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [activeSku, platform, viewType, selectedFinish])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  function handleSearch() {
    if (skuInput.trim()) {
      setActiveSku(skuInput.trim())
      setSelectedFinish(null) // Reset finish filter when changing SKU
    }
  }

  function handleKeyPress(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  async function handleSync() {
    try {
      const res = await fetch('/api/search-insights/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          days: 30,
          limit: 1000,
          enrichWithKeywordPlanner: true,
        }),
      })

      if (res.ok) {
        const result = await res.json()
        setCurrentJobId(result.jobId)
      }
    } catch (err) {
      console.error('Sync failed:', err)
    }
  }

  const stats: StatsData | null = data?.stats || null

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Search Query Insights</h1>
        <p className="text-muted-foreground">
          Analyze actual search terms from Google Ads with variant-level tracking
        </p>
      </div>

      {/* Sync Status Banner */}
      <SyncStatusBanner
        lastSynced={lastSynced}
        onSync={handleSync}
        currentJobId={currentJobId}
      />

      {/* Platform & SKU Selection */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex gap-4 items-center flex-wrap">
            <Tabs
              value={platform}
              onValueChange={(v) => {
                setPlatform(v as Platform)
                setSelectedFinish(null)
              }}
            >
              <TabsList>
                <TabsTrigger value="google">Google Shopping</TabsTrigger>
                <TabsTrigger value="bing">Bing Shopping</TabsTrigger>
                <TabsTrigger value="shopify">Shopify</TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex gap-2">
              <Input
                placeholder="Enter Master SKU..."
                value={skuInput}
                onChange={(e) => setSkuInput(e.target.value)}
                onKeyPress={handleKeyPress}
                className="w-40"
              />
              <Button onClick={handleSearch} disabled={!skuInput.trim()}>
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
            </div>
          </div>

          {/* Platform-specific view selector */}
          {activeSku && platform !== 'shopify' && (
            <VariantSelector
              platform={platform}
              viewType={viewType}
              selectedFinish={selectedFinish}
              availableFinishes={data?.availableFinishes || []}
              onViewTypeChange={setViewType}
              onFinishChange={setSelectedFinish}
            />
          )}

          {activeSku && platform === 'shopify' && (
            <VariantSelector
              platform={platform}
              viewType={viewType}
              selectedFinish={null}
              availableFinishes={[]}
              onViewTypeChange={() => {}}
              onFinishChange={() => {}}
            />
          )}
        </CardContent>
      </Card>

      {/* Loading State */}
      {loading && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i}>
                <CardContent className="pt-6">
                  <Skeleton className="h-4 w-20 mb-2" />
                  <Skeleton className="h-8 w-24" />
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardContent className="pt-6">
              <Skeleton className="h-64 w-full" />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Results */}
      {!loading && data && (
        <div className="space-y-6">
          {/* Info banner */}
          {data.note && (
            <div className="p-3 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">{data.note}</p>
            </div>
          )}

          {/* Stats Cards */}
          {stats && (
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Total Queries</p>
                      <p className="text-2xl font-bold">
                        {stats.totalQueries.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Impressions</p>
                      <p className="text-2xl font-bold">
                        {stats.totalImpressions.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <MousePointer className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Clicks (CTR)</p>
                      <p className="text-2xl font-bold">
                        {stats.totalClicks.toLocaleString()}
                        <span className="text-sm font-normal text-muted-foreground ml-1">
                          ({stats.ctr.toFixed(2)}%)
                        </span>
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-green-600" />
                    <div>
                      <p className="text-sm text-muted-foreground">Conv. Value</p>
                      <p className="text-2xl font-bold text-green-600">
                        ${stats.totalConversionValue.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Variant insights (Google/Bing only) */}
          {platform !== 'shopify' && viewType === 'variant' && data.byFinish && (
            <FinishInsights byFinish={data.byFinish} />
          )}

          {/* Gap Analysis */}
          {activeSku && data.queries && data.queries.length > 0 && (
            <GapAnalysis
              queries={data.queries}
              currentTitle={undefined} // Would need to fetch title from generated_content
            />
          )}

          {/* Query table */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                {viewType === 'aggregate'
                  ? 'Top Search Queries (All Variants)'
                  : selectedFinish
                  ? `Queries for ${selectedFinish} Variant`
                  : 'Queries by Variant'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <QueryTable
                queries={data.queries || []}
                viewType={platform === 'shopify' ? 'shopify' : viewType}
                showKeywordMetrics={true}
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Empty State */}
      {!loading && !data && !activeSku && (
        <Card>
          <CardContent className="pt-6 py-12 text-center">
            <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Search Query Insights</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              Enter a Master SKU above to view actual search terms from Google Ads,
              broken down by variant (finish). This data helps optimize product titles
              and descriptions for how customers actually search.
            </p>
          </CardContent>
        </Card>
      )}

      {/* No Results */}
      {!loading && activeSku && data?.queries?.length === 0 && (
        <Card>
          <CardContent className="pt-6 py-12 text-center">
            <Target className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No Search Data Found</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              No search query data found for SKU &quot;{activeSku}&quot;. This could mean:
            </p>
            <ul className="text-sm text-muted-foreground mt-2 space-y-1">
              <li>• The SKU has not been synced yet (click &quot;Sync Data&quot;)</li>
              <li>• The SKU does not have Shopping ads data in Google Ads</li>
              <li>• The variant mapping is not configured in variant_index</li>
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
