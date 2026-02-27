'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw } from 'lucide-react'

interface Outlier {
  request_id: string | null
  master_sku: string
  platform: string
  content_type: string
  mode: string
  cost_usd: number | null
  latency_ms: number | null
  provider_attempt_count: number | null
  parse_retry_count: number | null
  created_at: string
}

interface ReconciliationWindow {
  window_start: string
  window_end: string
  openai_total_cost_usd: number | null
  internal_total_cost_usd: number
  delta_cost_usd: number | null
  delta_ratio: number | null
  status: 'ok' | 'attention' | 'missing_openai_data'
  categories: string[]
  openai_total_requests: number
  internal_total_requests: number
  internal_missing_cost_requests: number
  provider_attempt_count_sum: number
  parse_retry_count_sum: number
  warnings: string[]
}

interface CostReconciliationReport {
  generated_at: string
  lookback_days: number
  latest: ReconciliationWindow | null
  windows: ReconciliationWindow[]
  cost_outliers: Outlier[]
  latency_outliers: Outlier[]
}

const formatUsd = (value: number | null): string => {
  if (value === null || Number.isNaN(value)) {
    return 'n/a'
  }
  return `$${value.toFixed(4)}`
}

const formatPercent = (value: number | null): string => {
  if (value === null || Number.isNaN(value)) {
    return 'n/a'
  }
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(2)}%`
}

const formatDateTime = (value: string): string => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

function statusVariant(status: ReconciliationWindow['status']): 'default' | 'destructive' | 'secondary' {
  if (status === 'attention') {
    return 'destructive'
  }
  if (status === 'missing_openai_data') {
    return 'secondary'
  }
  return 'default'
}

export default function CostReconciliationPage() {
  const [report, setReport] = useState<CostReconciliationReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [capturing, setCapturing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [captureMessage, setCaptureMessage] = useState<string | null>(null)
  const [lookbackDays, setLookbackDays] = useState(14)

  const effectiveLookbackDays = useMemo(
    () => Math.max(1, Math.min(Math.floor(lookbackDays || 1), 90)),
    [lookbackDays]
  )

  const fetchReport = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `/api/monitoring/cost-reconciliation?lookback_days=${effectiveLookbackDays}`,
        {
          cache: 'no-store',
        }
      )
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error || 'Failed to load cost reconciliation report')
      }
      setReport(body.report)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cost reconciliation report')
    } finally {
      setLoading(false)
    }
  }, [effectiveLookbackDays])

  useEffect(() => {
    fetchReport()
  }, [fetchReport])

  const runCapture = async () => {
    setCapturing(true)
    setCaptureMessage(null)
    setError(null)
    try {
      const response = await fetch(
        `/api/monitoring/cost-reconciliation?lookback_days=${Math.max(
          1,
          Math.min(effectiveLookbackDays, 30)
        )}`,
        {
          method: 'POST',
        }
      )
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error || 'Failed to run reconciliation capture')
      }
      setCaptureMessage(
        `Captured ${body.capture?.windows_processed ?? 0} window(s) at ${new Date(
          body.capture?.generated_at ?? Date.now()
        ).toLocaleString()}`
      )
      await fetchReport()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run reconciliation capture')
    } finally {
      setCapturing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Cost Reconciliation</h1>
        <p className="text-muted-foreground mt-2">
          Compare OpenAI organization usage windows against internal regenerate lineage costs.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Controls</CardTitle>
          <CardDescription>
            Reconciliation uses UTC daily windows and highlights mismatches from retry amplification or missing cost rows.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="w-40">
            <label className="mb-1 block text-xs text-muted-foreground">Lookback days</label>
            <Input
              type="number"
              min={1}
              max={90}
              value={lookbackDays}
              onChange={(event) => setLookbackDays(Number(event.target.value) || 1)}
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={fetchReport} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button variant="outline" onClick={runCapture} disabled={capturing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${capturing ? 'animate-spin' : ''}`} />
              Run Capture
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {captureMessage && (
        <Alert>
          <AlertDescription>{captureMessage}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      )}

      {!loading && report && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Latest Window</CardTitle>
              <CardDescription>
                Generated at {formatDateTime(report.generated_at)} • {report.lookback_days} day lookback
              </CardDescription>
            </CardHeader>
            <CardContent>
              {report.latest ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Status</p>
                    <Badge variant={statusVariant(report.latest.status)}>{report.latest.status}</Badge>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">OpenAI cost</p>
                    <p className="text-sm font-medium">{formatUsd(report.latest.openai_total_cost_usd)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Internal cost</p>
                    <p className="text-sm font-medium">{formatUsd(report.latest.internal_total_cost_usd)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Delta ratio</p>
                    <p className="text-sm font-medium">{formatPercent(report.latest.delta_ratio)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">OpenAI requests</p>
                    <p className="text-sm font-medium">{report.latest.openai_total_requests}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Internal requests</p>
                    <p className="text-sm font-medium">{report.latest.internal_total_requests}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Provider attempts</p>
                    <p className="text-sm font-medium">{report.latest.provider_attempt_count_sum}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Parse retries</p>
                    <p className="text-sm font-medium">{report.latest.parse_retry_count_sum}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No reconciliation windows captured yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Window History</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="py-2 text-left pr-3">Window</th>
                    <th className="py-2 text-left pr-3">Status</th>
                    <th className="py-2 text-left pr-3">OpenAI</th>
                    <th className="py-2 text-left pr-3">Internal</th>
                    <th className="py-2 text-left pr-3">Delta</th>
                    <th className="py-2 text-left pr-3">Delta %</th>
                    <th className="py-2 text-left pr-3">Req (O/I)</th>
                    <th className="py-2 text-left pr-3">Categories</th>
                  </tr>
                </thead>
                <tbody>
                  {report.windows.map((window) => (
                    <tr key={`${window.window_start}-${window.window_end}`} className="border-b align-top">
                      <td className="py-2 pr-3">
                        <div>{window.window_start.slice(0, 10)}</div>
                        <div className="text-xs text-muted-foreground">to {window.window_end.slice(0, 10)}</div>
                      </td>
                      <td className="py-2 pr-3">
                        <Badge variant={statusVariant(window.status)}>{window.status}</Badge>
                      </td>
                      <td className="py-2 pr-3">{formatUsd(window.openai_total_cost_usd)}</td>
                      <td className="py-2 pr-3">{formatUsd(window.internal_total_cost_usd)}</td>
                      <td className="py-2 pr-3">{formatUsd(window.delta_cost_usd)}</td>
                      <td className="py-2 pr-3">{formatPercent(window.delta_ratio)}</td>
                      <td className="py-2 pr-3">
                        {window.openai_total_requests}/{window.internal_total_requests}
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {window.categories.join(', ') || 'none'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Top Cost Outliers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {report.cost_outliers.length === 0 && (
                  <p className="text-sm text-muted-foreground">No outliers in selected window.</p>
                )}
                {report.cost_outliers.map((row) => (
                  <div
                    key={`cost-${row.request_id ?? row.created_at}-${row.master_sku}-${row.platform}`}
                    className="rounded border p-2"
                  >
                    <p className="text-sm font-medium">
                      {row.master_sku} • {row.platform}/{row.content_type}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatUsd(row.cost_usd)} • attempts {row.provider_attempt_count ?? 0} • parse retries{' '}
                      {row.parse_retry_count ?? 0}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(row.created_at)}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top Latency Outliers</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {report.latency_outliers.length === 0 && (
                  <p className="text-sm text-muted-foreground">No latency outliers in selected window.</p>
                )}
                {report.latency_outliers.map((row) => (
                  <div
                    key={`latency-${row.request_id ?? row.created_at}-${row.master_sku}-${row.platform}`}
                    className="rounded border p-2"
                  >
                    <p className="text-sm font-medium">
                      {row.master_sku} • {row.platform}/{row.content_type}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {row.latency_ms ?? 0} ms • {formatUsd(row.cost_usd)} • attempts{' '}
                      {row.provider_attempt_count ?? 0}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(row.created_at)}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
