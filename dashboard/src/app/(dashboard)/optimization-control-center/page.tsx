'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, RefreshCw, ShieldAlert, Sparkles, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type DateRangePreset = '7d' | '30d' | '60d' | '90d'

const DATE_RANGE_OPTIONS: Array<{ value: DateRangePreset; label: string }> = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '60d', label: 'Last 60 days' },
  { value: '90d', label: 'Last 90 days' },
]

interface RecommendationQueueResponse {
  generated_at: string
  total_terms_evaluated: number
  queue_count: number
  action_distribution: Record<string, number>
  warnings?: string[]
  supplemental_confidence?: {
    multiplier: number
    reasons: string[]
    diagnostics: {
      ga4RiskLevel: 'low' | 'medium' | 'high' | 'unavailable'
      ga4QualityScore: number | null
      ga4UnassignedRevenueShare: number | null
      ga4NotSetCampaignRevenueShare: number | null
      shopifyMappedSkuCoverage: number | null
      shopifyUnmappedRevenueShare: number | null
    }
  }
  queue: Array<{
    searchTerm: string
    impactScore: number
    baseConfidence: number
    confidence: number
    confidenceMultiplier: number
    confidenceAdjustmentReasons: string[]
    actionType: string
    defaultTier?: string
    reasonCodes: string[]
    customLabelCount: number
    impressions: number
    clicks: number
    conversions: number
    cost: number
    conversionValue: number
  }>
}

interface ScoresResponse {
  summary: {
    termCount: number
    avgImpactScore: number
    avgExpectedProfitProxy: number
    avgUncertainty: number
    topImpactTerms: Array<{ searchTerm: string; impactScore: number }>
  }
  score_distribution: {
    high: number
    medium: number
    low: number
  }
}

interface OpportunitiesResponse {
  cluster_count: number
  account_median_roas?: number
  clusters: Array<{
    clusterKey: string
    termCount: number
    totalImpressions: number
    totalClicks: number
    totalCost: number
    aggregateImpactScore: number
    averageCpc: number
    attractivenessScore: number
    overlapRiskScore: number
    overlapRiskLevel: 'low' | 'medium' | 'high'
    averageRecommendationConfidence: number
    averageUncertainty: number
    uniqueLabelCount: number
    topCustomLabels: string[]
    topSearchTerms: string[]
  }>
  launch_briefs: Array<{
    clusterKey: string
    pilotName: string
    priority: 'high' | 'medium' | 'low'
    strategySummary: string
    budgetCapUsd: number
    observationWindowDays: number
    topTerms: string[]
    negativeControls: string[]
    buildoutChecklist: string[]
    successCriteria: {
      targetRoas: number
      minClicks: number
      minConversions: number
    }
    stopConditions: string[]
  }>
}

interface RoasResponse {
  recommendation_count: number
  recommendations: Array<{
    customLabel0: string
    tier: 'HIGH' | 'MEDIUM' | 'LOW'
    currentTargetRoas: number
    observedRoas: number
    roasGapRatio: number
    recommendedTargetRoas: number
    appliedStepPct: number
    maxAllowedStepPct: number
    direction: 'increase' | 'decrease' | 'hold'
    guardrailStatus: 'actionable' | 'insufficient_data' | 'near_target_band'
    confidence: number
    confidenceComponents: {
      clickConfidence: number
      conversionConfidence: number
      spendConfidence: number
      final: number
    }
    rationale: string
  }>
}

interface Ga4AttributionResponse {
  qualityScore: number
  riskLevel: 'low' | 'medium' | 'high'
  totalRevenue: number
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  problematic_rows: Array<{
    channelGroup: string
    campaignName: string
    purchaseRevenue: number
  }>
}

interface AudienceWatchlistResponse {
  watchlist: Array<{
    audienceName: string
    purpose: string
    sessions: number
    transactions: number
    purchaseRevenue: number
    conversionRate: number
    status: 'observe' | 'healthy' | 'at-risk'
  }>
}

interface AudienceRecommendationsResponse {
  recommendations: Array<{
    audienceName: string
    recommendationType: 'observe' | 'exclude' | 'target' | 'hold'
    priority: 'high' | 'medium' | 'low'
    reason: string
  }>
}

interface ShopifyValueSignalsResponse {
  orderCount: number
  uniqueCustomers: number
  repeatCustomerRate: number
  totalRevenue: number
  averageOrderValue: number
  topCustomLabels: Array<{
    customLabel0: string
    revenue: number
    orderCount: number
    skuCount: number
  }>
  unmappedSkuRevenue: number
}

function riskBadgeVariant(risk: 'low' | 'medium' | 'high') {
  if (risk === 'high') return 'destructive' as const
  if (risk === 'medium') return 'outline' as const
  return 'secondary' as const
}

function recommendationPriorityVariant(priority: 'low' | 'medium' | 'high') {
  if (priority === 'high') return 'destructive' as const
  if (priority === 'medium') return 'outline' as const
  return 'secondary' as const
}

function overlapRiskBadgeVariant(risk: 'low' | 'medium' | 'high') {
  if (risk === 'high') return 'destructive' as const
  if (risk === 'medium') return 'outline' as const
  return 'secondary' as const
}

export default function OptimizationControlCenterPage() {
  const [range, setRange] = useState<DateRangePreset>('30d')
  const [loading, setLoading] = useState<boolean>(true)
  const [refreshing, setRefreshing] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [supplementalWarnings, setSupplementalWarnings] = useState<string[]>([])

  const [recommendations, setRecommendations] = useState<RecommendationQueueResponse | null>(null)
  const [scores, setScores] = useState<ScoresResponse | null>(null)
  const [opportunities, setOpportunities] = useState<OpportunitiesResponse | null>(null)
  const [roas, setRoas] = useState<RoasResponse | null>(null)
  const [ga4Attribution, setGa4Attribution] = useState<Ga4AttributionResponse | null>(null)
  const [audienceWatchlist, setAudienceWatchlist] = useState<AudienceWatchlistResponse | null>(null)
  const [audienceRecommendations, setAudienceRecommendations] =
    useState<AudienceRecommendationsResponse | null>(null)
  const [shopifySignals, setShopifySignals] = useState<ShopifyValueSignalsResponse | null>(null)

  const highPriorityAudienceRecommendations = useMemo(
    () => audienceRecommendations?.recommendations.filter((item) => item.priority === 'high') ?? [],
    [audienceRecommendations]
  )

  const loadData = useCallback(async () => {
    const qs = new URLSearchParams({ range }).toString()

    const fetchRequiredJson = async <T,>(url: string, label: string): Promise<T> => {
      const response = await fetch(url)
      if (!response.ok) {
        const detail = await response.text()
        throw new Error(`${label} unavailable: ${detail || `HTTP ${response.status}`}`)
      }
      return (await response.json()) as T
    }

    const fetchOptionalJson = async <T,>(
      url: string,
      label: string
    ): Promise<{ data: T | null; warnings: string[] }> => {
      try {
        const response = await fetch(url)
        if (!response.ok) {
          const detail = await response.text()
          return {
            data: null,
            warnings: [`${label} unavailable: ${detail || `HTTP ${response.status}`}`],
          }
        }

        const payload = (await response.json()) as T & {
          available?: boolean
          warnings?: unknown
        }
        const warnings: string[] = []

        if (payload.available === false) {
          warnings.push(`${label} is currently reporting degraded availability.`)
        }

        if (Array.isArray(payload.warnings)) {
          for (const warning of payload.warnings) {
            if (typeof warning === 'string' && warning.trim()) {
              warnings.push(`${label}: ${warning}`)
            }
          }
        }

        return { data: payload as T, warnings }
      } catch (error) {
        return {
          data: null,
          warnings: [
            `${label} unavailable: ${error instanceof Error ? error.message : 'Unknown error'}`,
          ],
        }
      }
    }

    const [
      recommendationPayload,
      scorePayload,
      opportunitiesPayload,
      roasPayload,
    ] = await Promise.all([
      fetchRequiredJson<RecommendationQueueResponse>(
        `/api/shopping-funnel/recommendations?${qs}`,
        'Shopping recommendations'
      ),
      fetchRequiredJson<ScoresResponse>(`/api/shopping-funnel/scores?${qs}`, 'Query scores'),
      fetchRequiredJson<OpportunitiesResponse>(
        `/api/shopping-funnel/opportunities?${qs}`,
        'Opportunity clusters'
      ),
      fetchRequiredJson<RoasResponse>(
        `/api/shopping-funnel/roas-recommendations?${qs}`,
        'ROAS recommendations'
      ),
    ])

    const [ga4AttributionResult, audienceWatchlistResult, audienceRecommendationsResult, shopifySignalsResult] =
      await Promise.all([
        fetchOptionalJson<Ga4AttributionResponse>(`/api/ga4/attribution-quality`, 'GA4 attribution'),
        fetchOptionalJson<AudienceWatchlistResponse>(`/api/audiences/watchlist`, 'Audience watchlist'),
        fetchOptionalJson<AudienceRecommendationsResponse>(
          `/api/audiences/recommendations`,
          'Audience recommendations'
        ),
        fetchOptionalJson<ShopifyValueSignalsResponse>(
          `/api/shopify/value-signals`,
          'Shopify value signals'
        ),
      ])

    const warnings = [
      ...(recommendationPayload.warnings ?? []),
      ...ga4AttributionResult.warnings,
      ...audienceWatchlistResult.warnings,
      ...audienceRecommendationsResult.warnings,
      ...shopifySignalsResult.warnings,
    ]

    setSupplementalWarnings(Array.from(new Set(warnings)))

    setRecommendations(recommendationPayload)
    setScores(scorePayload)
    setOpportunities(opportunitiesPayload)
    setRoas(roasPayload)
    setGa4Attribution(ga4AttributionResult.data)
    setAudienceWatchlist(audienceWatchlistResult.data)
    setAudienceRecommendations(audienceRecommendationsResult.data)
    setShopifySignals(shopifySignalsResult.data)
  }, [range])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setErrorMessage(null)
    try {
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load optimization control center')
    } finally {
      setRefreshing(false)
    }
  }, [loadData])

  useEffect(() => {
    setLoading(true)
    setErrorMessage(null)
    setSupplementalWarnings([])
    void loadData()
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load optimization control center')
      })
      .finally(() => setLoading(false))
  }, [loadData])

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-16 w-full" />
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-[520px] w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Optimization Control Center</h1>
          <p className="text-muted-foreground">
            Closed-loop Google Ads optimization: intelligence, opportunities, bidding policy, and guardrails.
            GA4 and Shopify are supplemental.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={range} onValueChange={(value) => setRange(value as DateRangePreset)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DATE_RANGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => void refresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {errorMessage && (
        <Card className="border-destructive/40">
          <CardContent className="flex items-center gap-2 pt-6 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      )}

      {supplementalWarnings.length > 0 && (
        <Card className="border-amber-300/70 bg-amber-50/40">
          <CardContent className="space-y-1 pt-6 text-sm text-amber-900">
            <p className="font-medium">Supplemental signals degraded</p>
            {supplementalWarnings.map((warning) => (
              <p key={warning} className="text-xs">
                {warning}
              </p>
            ))}
            <p className="pt-1 text-xs text-amber-800">
              Core Google Ads optimization data is still live and actionable.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Terms Evaluated</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{(recommendations?.total_terms_evaluated ?? 0).toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Current decision universe</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Impact Score</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{(scores?.summary.avgImpactScore ?? 0).toFixed(2)}</p>
            <p className="text-xs text-muted-foreground">Profit-weighted priority proxy</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">ROAS Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{(roas?.recommendation_count ?? 0).toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Label × tier recommendations</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Attribution Quality</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-2xl font-bold">
              {typeof ga4Attribution?.qualityScore === 'number'
                ? `${(ga4Attribution.qualityScore * 100).toFixed(1)}%`
                : '—'}
            </p>
            {ga4Attribution?.riskLevel && (
              <Badge variant={riskBadgeVariant(ga4Attribution.riskLevel)}>
                {ga4Attribution.riskLevel.toUpperCase()} risk
              </Badge>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="query-intelligence" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto">
          <TabsTrigger value="query-intelligence">Query Intelligence</TabsTrigger>
          <TabsTrigger value="bidding-policy">Bidding Policy</TabsTrigger>
          <TabsTrigger value="audience-value">Audience + Value</TabsTrigger>
          <TabsTrigger value="guardrails">Guardrails</TabsTrigger>
        </TabsList>

        <TabsContent value="query-intelligence" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recommendation Queue</CardTitle>
              <CardDescription>High-impact terms first, with confidence and rationale.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {(recommendations?.queue ?? []).slice(0, 20).map((item) => (
                <div key={item.searchTerm} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{item.searchTerm}</p>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{item.impressions.toLocaleString()} impressions</span>
                        <span>{item.clicks.toLocaleString()} clicks</span>
                        <span>{item.conversions.toFixed(2)} conv</span>
                        <span>${item.cost.toFixed(2)} cost</span>
                      </div>
                      {item.reasonCodes.length > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Why: {item.reasonCodes.join(', ')}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">Impact {item.impactScore.toFixed(2)}</Badge>
                      <Badge variant="outline">{Math.round(item.confidence * 100)}% confidence</Badge>
                      {item.confidence !== item.baseConfidence && (
                        <Badge variant="outline">
                          gated from {Math.round(item.baseConfidence * 100)}%
                        </Badge>
                      )}
                      <Badge variant="secondary">
                        {item.actionType}
                        {item.defaultTier ? ` (${item.defaultTier})` : ''}
                      </Badge>
                    </div>
                  </div>
                  {item.confidenceAdjustmentReasons.length > 0 && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Supplemental confidence gates: {item.confidenceAdjustmentReasons.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Opportunity Clusters</CardTitle>
              <CardDescription>
                Low-CPC, high-attractiveness clusters with overlap risk scoring for safe pilot expansion.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {(opportunities?.clusters ?? []).slice(0, 9).map((cluster) => (
                <div key={cluster.clusterKey} className="rounded-md border p-3">
                  <p className="font-medium">{cluster.clusterKey}</p>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{cluster.termCount} terms</span>
                    <span>{cluster.totalImpressions.toLocaleString()} impressions</span>
                    <span>${cluster.averageCpc.toFixed(2)} avg CPC</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant="outline">Attractiveness {cluster.attractivenessScore.toFixed(2)}</Badge>
                    <Badge variant={overlapRiskBadgeVariant(cluster.overlapRiskLevel)}>
                      Overlap {cluster.overlapRiskLevel}
                    </Badge>
                    <Badge variant="outline">{Math.round(cluster.averageRecommendationConfidence * 100)}% conf</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Labels: {cluster.topCustomLabels.slice(0, 3).join(', ')}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Launch Briefs</CardTitle>
              <CardDescription>
                Pilot-ready campaign/ad-group briefs with budget caps, overlap controls, and stop rules.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(opportunities?.launch_briefs ?? []).slice(0, 6).map((brief) => (
                <div key={brief.clusterKey} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{brief.pilotName}</p>
                      <p className="text-xs text-muted-foreground">{brief.strategySummary}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={recommendationPriorityVariant(brief.priority)}>
                        {brief.priority.toUpperCase()} priority
                      </Badge>
                      <Badge variant="outline">${brief.budgetCapUsd} cap</Badge>
                      <Badge variant="outline">{brief.observationWindowDays}d window</Badge>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>Target ROAS: {brief.successCriteria.targetRoas.toFixed(2)}x</span>
                    <span>Min clicks: {brief.successCriteria.minClicks}</span>
                    <span>Min conversions: {brief.successCriteria.minConversions}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Terms: {brief.topTerms.slice(0, 3).join(' • ')}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Controls: {brief.negativeControls.slice(0, 2).join(' • ')}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bidding-policy" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Adaptive tROAS Recommendations</CardTitle>
              <CardDescription>
                Recommend-only mode with direction, confidence, and bounded step changes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {(roas?.recommendations ?? []).slice(0, 25).map((item) => (
                <div key={`${item.customLabel0}-${item.tier}`} className="rounded-md border p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{item.customLabel0}</p>
                      <p className="text-xs text-muted-foreground">Tier: {item.tier}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{item.rationale}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">Observed ROAS {item.observedRoas.toFixed(2)}x</Badge>
                      <Badge variant="outline">
                        {item.currentTargetRoas.toFixed(2)}x → {item.recommendedTargetRoas.toFixed(2)}x
                      </Badge>
                      <Badge variant="outline">
                        Step {(item.appliedStepPct * 100).toFixed(1)}% (cap {(item.maxAllowedStepPct * 100).toFixed(0)}%)
                      </Badge>
                      <Badge variant="secondary">{item.direction}</Badge>
                      <Badge
                        variant={
                          item.guardrailStatus === 'actionable'
                            ? 'secondary'
                            : item.guardrailStatus === 'near_target_band'
                              ? 'outline'
                              : 'destructive'
                        }
                      >
                        {item.guardrailStatus}
                      </Badge>
                      <Badge variant="outline">{Math.round(item.confidence * 100)}% confidence</Badge>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>ROAS gap {(item.roasGapRatio * 100).toFixed(1)}%</span>
                    <span>click conf {(item.confidenceComponents.clickConfidence * 100).toFixed(0)}%</span>
                    <span>conv conf {(item.confidenceComponents.conversionConfidence * 100).toFixed(0)}%</span>
                    <span>spend conf {(item.confidenceComponents.spendConfidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audience-value" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>GA4 Audience Watchlist</CardTitle>
                <CardDescription>Monitor-first audience framework from your approved roadmap.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {(audienceWatchlist?.watchlist ?? []).map((item) => (
                  <div key={item.audienceName} className="rounded-md border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium">{item.audienceName}</p>
                      <Badge variant={item.status === 'at-risk' ? 'destructive' : 'outline'}>
                        {item.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{item.purpose}</p>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{item.sessions.toLocaleString()} sessions</span>
                      <span>{item.transactions.toLocaleString()} transactions</span>
                      <span>${item.purchaseRevenue.toFixed(2)} revenue</span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Shopify Value Signals</CardTitle>
                <CardDescription>Order economics and repeat-customer quality from Shopify Admin API.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md border p-2">
                    <p className="text-xs text-muted-foreground">Orders</p>
                    <p className="font-semibold">{(shopifySignals?.orderCount ?? 0).toLocaleString()}</p>
                  </div>
                  <div className="rounded-md border p-2">
                    <p className="text-xs text-muted-foreground">Total Revenue</p>
                    <p className="font-semibold">${(shopifySignals?.totalRevenue ?? 0).toFixed(2)}</p>
                  </div>
                  <div className="rounded-md border p-2">
                    <p className="text-xs text-muted-foreground">Repeat Customer Rate</p>
                    <p className="font-semibold">
                      {((shopifySignals?.repeatCustomerRate ?? 0) * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="rounded-md border p-2">
                    <p className="text-xs text-muted-foreground">Unmapped SKU Revenue</p>
                    <p className="font-semibold">${(shopifySignals?.unmappedSkuRevenue ?? 0).toFixed(2)}</p>
                  </div>
                </div>
                <div className="space-y-2">
                  {(shopifySignals?.topCustomLabels ?? []).slice(0, 6).map((label) => (
                    <div
                      key={label.customLabel0}
                      className="flex items-center justify-between rounded-md border p-2 text-xs"
                    >
                      <span>{label.customLabel0}</span>
                      <span className="font-medium">${label.revenue.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="guardrails" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Automation Guardrails</CardTitle>
              <CardDescription>
                Blocks unsafe automation when attribution quality degrades or audience risk spikes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-600" />
                <span className="text-sm">
                  Unassigned revenue share: {((ga4Attribution?.unassignedRevenueShare ?? 0) * 100).toFixed(1)}%
                </span>
                <span className="text-sm">
                  (not set) campaign share: {((ga4Attribution?.notSetCampaignRevenueShare ?? 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="space-y-2">
                {highPriorityAudienceRecommendations.length === 0 ? (
                  <div className="rounded-md border p-3 text-sm text-muted-foreground">
                    No high-priority audience incidents detected in current window.
                  </div>
                ) : (
                  highPriorityAudienceRecommendations.map((item) => (
                    <div key={`${item.audienceName}-${item.recommendationType}`} className="rounded-md border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium">{item.audienceName}</p>
                        <Badge variant={recommendationPriorityVariant(item.priority)}>{item.priority}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {item.recommendationType.toUpperCase()}: {item.reason}
                      </p>
                    </div>
                  ))
                )}
              </div>
              {ga4Attribution?.problematic_rows?.length ? (
                <div className="rounded-md border p-3">
                  <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                    <Sparkles className="h-4 w-4" />
                    Top attribution risk rows
                  </p>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {ga4Attribution.problematic_rows.slice(0, 8).map((row, index) => (
                      <div key={`${row.channelGroup}-${row.campaignName}-${index}`}>
                        {row.channelGroup} / {row.campaignName}: ${row.purchaseRevenue.toFixed(2)}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 pt-6 text-xs text-muted-foreground">
          <TrendingUp className="h-3.5 w-3.5" />
          <span>Primary decision source: live Google Ads Shopping data.</span>
          <span>Canonical GA4 property: `properties/342525135` (supplemental diagnostics).</span>
        </CardContent>
      </Card>
    </div>
  )
}
