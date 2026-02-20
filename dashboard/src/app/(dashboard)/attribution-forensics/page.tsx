'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, RefreshCw, Save } from 'lucide-react'
import { AttributionHealthCards } from '@/components/attribution/AttributionHealthCards'
import { AttributionTrendChart } from '@/components/attribution/AttributionTrendChart'
import { HandoffPacketPanel } from '@/components/attribution/HandoffPacketPanel'
import { IncidentPanel, type IncidentPanelItem } from '@/components/attribution/IncidentPanel'
import { RootCauseTable } from '@/components/attribution/RootCauseTable'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'

type DateRangePreset = '7d' | '30d' | '60d' | '90d'

const DATE_RANGE_OPTIONS: Array<{ value: DateRangePreset; label: string }> = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '60d', label: 'Last 60 days' },
  { value: '90d', label: 'Last 90 days' },
]

const DATE_RANGE_TO_START: Record<DateRangePreset, string> = {
  '7d': '7daysAgo',
  '30d': '30daysAgo',
  '60d': '60daysAgo',
  '90d': '90daysAgo',
}

interface AttributionTrendPoint {
  reportDate: string
  totalRevenue: number
  unassignedRevenue: number
  notSetCampaignRevenue: number
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  qualityScore: number
}

interface RootCauseRow {
  rootCauseType: 'source_medium' | 'campaign_pattern' | 'landing_page'
  rootCauseKey: string
  sessions: number
  transactions: number
  purchaseRevenue: number
  revenueShare: number
  sessionShare: number
  sampleValues: string[]
}

interface AttributionForensicsResponse {
  property_id: string
  start_date: string
  end_date: string
  generated_at: string
  quality_summary: {
    qualityScore: number
    riskLevel: 'low' | 'medium' | 'high'
    unassignedRevenueShare: number
    notSetCampaignRevenueShare: number
    totalRevenue: number
  }
  landing_invalid_revenue_share: number
  root_cause_rows: RootCauseRow[]
  incidents: IncidentPanelItem[]
  warnings: string[]
  available: boolean
}

interface AttributionTrendResponse {
  points: AttributionTrendPoint[]
  warnings: string[]
  available: boolean
}

interface ReconciliationResponse {
  ga4Revenue: number
  shopifyRevenue: number
  revenueDelta: number
  revenueRatio: number | null
  orderCount: number
  warnings: string[]
  available: boolean
}

export default function AttributionForensicsPage() {
  const [range, setRange] = useState<DateRangePreset>('30d')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [capturing, setCapturing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  const [forensics, setForensics] = useState<AttributionForensicsResponse | null>(null)
  const [trend, setTrend] = useState<AttributionTrendResponse | null>(null)
  const [reconciliation, setReconciliation] = useState<ReconciliationResponse | null>(null)

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      start_date: DATE_RANGE_TO_START[range],
      end_date: 'yesterday',
    })
    return params.toString()
  }, [range])

  const loadData = useCallback(async () => {
    const fetchJson = async <T,>(url: string): Promise<T> => {
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(await response.text())
      }
      return (await response.json()) as T
    }

    const [forensicsPayload, trendPayload, reconciliationPayload] = await Promise.all([
      fetchJson<AttributionForensicsResponse>(`/api/ga4/attribution-forensics?${queryString}`),
      fetchJson<AttributionTrendResponse>(`/api/ga4/attribution-trend?${queryString}`),
      fetchJson<ReconciliationResponse>(`/api/ga4/reconciliation?${queryString}`),
    ])

    setForensics(forensicsPayload)
    setTrend(trendPayload)
    setReconciliation(reconciliationPayload)
    setWarnings([
      ...(forensicsPayload.warnings ?? []),
      ...(trendPayload.warnings ?? []),
      ...(reconciliationPayload.warnings ?? []),
    ])
  }, [queryString])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setErrorMessage(null)
    try {
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load attribution forensics')
    } finally {
      setRefreshing(false)
    }
  }, [loadData])

  const captureNow = useCallback(async () => {
    setCapturing(true)
    setErrorMessage(null)
    try {
      const response = await fetch(`/api/ga4/snapshot-capture?${queryString}`, { method: 'POST' })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      await refresh()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to capture snapshot')
    } finally {
      setCapturing(false)
    }
  }, [queryString, refresh])

  useEffect(() => {
    setLoading(true)
    setErrorMessage(null)
    void loadData()
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load attribution forensics')
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
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const quality = forensics?.quality_summary
  const handoffPacket = {
    exported_at: new Date().toISOString(),
    property_id: forensics?.property_id ?? 'properties/342525135',
    date_window: {
      start_date: forensics?.start_date ?? DATE_RANGE_TO_START[range],
      end_date: forensics?.end_date ?? 'yesterday',
    },
    summary: {
      quality_score: quality?.qualityScore ?? 0,
      risk_level: quality?.riskLevel ?? 'high',
      unassigned_revenue_share: quality?.unassignedRevenueShare ?? 0,
      not_set_campaign_revenue_share: quality?.notSetCampaignRevenueShare ?? 0,
      landing_invalid_revenue_share: forensics?.landing_invalid_revenue_share ?? 0,
      ga4_revenue: reconciliation?.ga4Revenue ?? 0,
      shopify_revenue: reconciliation?.shopifyRevenue ?? 0,
      reconciliation_ratio: reconciliation?.revenueRatio ?? null,
      order_count: reconciliation?.orderCount ?? 0,
    },
    root_causes: forensics?.root_cause_rows ?? [],
    incidents: forensics?.incidents ?? [],
    warnings,
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Attribution Forensics</h1>
          <p className="text-muted-foreground">
            Diagnose Unassigned / (not set) leakage with read-only evidence from GA4 and Shopify.
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
          <Button variant="outline" onClick={() => void refresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => void captureNow()} disabled={capturing}>
            <Save className={`mr-2 h-4 w-4 ${capturing ? 'animate-pulse' : ''}`} />
            Capture now
          </Button>
        </div>
      </div>

      {errorMessage && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Attribution Forensics Error</AlertTitle>
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}

      {warnings.length > 0 && (
        <Card className="border-amber-300/60">
          <CardContent className="space-y-1 pt-6 text-sm">
            {warnings.map((warning) => (
              <p key={warning} className="text-amber-700">
                {warning}
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <AttributionHealthCards
        qualityScore={quality?.qualityScore ?? 0}
        riskLevel={quality?.riskLevel ?? 'high'}
        unassignedRevenueShare={quality?.unassignedRevenueShare ?? 0}
        notSetCampaignRevenueShare={quality?.notSetCampaignRevenueShare ?? 0}
        landingInvalidRevenueShare={forensics?.landing_invalid_revenue_share ?? 0}
        reconciliationRatio={reconciliation?.revenueRatio ?? null}
      />

      <AttributionTrendChart points={trend?.points ?? []} />
      <RootCauseTable rows={forensics?.root_cause_rows ?? []} />
      <IncidentPanel incidents={forensics?.incidents ?? []} />
      <HandoffPacketPanel packet={handoffPacket} />
    </div>
  )
}
