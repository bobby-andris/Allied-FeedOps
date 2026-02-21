'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, BarChart3, RefreshCw, RotateCcw, ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type DateRangePreset = '7d' | '30d' | '60d' | '90d'

const DATE_RANGE_OPTIONS: Array<{ value: DateRangePreset; label: string }> = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '60d', label: 'Last 60 days' },
  { value: '90d', label: 'Last 90 days' },
]

interface IntentDecisionResponse {
  policy_version: string
  total_terms_evaluated: number
  review_required_count: number
  action_distribution: Record<string, number>
  decisions: Array<{
    search_term: string
    metrics: {
      impressions: number
      clicks: number
      conversions: number
      conversionsValue: number
      costMicros: number
    }
    decision: {
      routeAction: string
      recommendedTier?: string
      confidence: number
      requiresReview: boolean
      reasonCodes: string[]
      classification: {
        intentClass: string
      }
    }
  }>
}

interface GuardrailResponse {
  status: 'go' | 'hold' | 'blocked'
  reason_codes: string[]
  stale_data_hours: number
  open_critical_incidents: number
  open_high_incidents: number
  derived_incidents: Array<{
    ruleId: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    message: string
  }>
  open_incidents?: Array<{
    id: string
    rule_id: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    status: string
    message: string
    suggested_action?: string | null
    created_at: string
  }>
  warnings: string[]
}

interface BidPolicyResponse {
  decision_count: number
  decisions: Array<{
    key: string
    tier: 'HIGH' | 'MEDIUM' | 'LOW'
    observed_roas: number
    current_target_roas: number
    decision: {
      action: string
      recommendedTargetRoas: number
      confidence: number
      reasonCodes: string[]
    }
  }>
  warnings: string[]
}

interface RollbackSnapshot {
  id: string
  snapshot_key: string
  policy_version: string
  created_at?: string
}

interface ScorecardResponse {
  generated_at: string
  roas: number
  cpa: number
  totalRevenue: number
  totalCost: number
  totalConversions: number
  periodDays: number
  automationRate: number
  pendingReviewRate: number
  avgDecisionLatencyHours: number
  actionBreakdown: {
    promote: number
    demote: number
    negative: number
    hold: number
  }
  operationalHealth: {
    guardrailStatus: string
    openIncidentCount: number
    healthGrade: 'healthy' | 'degraded' | 'critical'
  }
  warnings: string[]
}

interface ReviewAnalyticsResponse {
  summary: {
    total_actions: number
    unique_entities: number
    unique_actors: number
    consistency_rate: number
    alignment_rate: number
    review_velocity_24h: number
  }
  queue_summaries: Array<{
    queue_name: string
    total_actions: number
    unique_entities: number
    unique_actors: number
    consistency_rate: number
    alignment_rate: number
  }>
  actor_summaries: Array<{
    actor: string
    total_actions: number
    unique_entities: number
    queue_count: number
    alignment_rate: number
  }>
  conflict_entities: Array<{
    queue_name: string
    entity_key: string
    actions: string[]
    actor_count: number
  }>
  warnings?: string[]
}

function guardrailVariant(status: GuardrailResponse['status']) {
  if (status === 'blocked') return 'destructive' as const
  if (status === 'hold') return 'outline' as const
  return 'secondary' as const
}

function normalizeReviewAnalyticsResponse(payload: Partial<ReviewAnalyticsResponse> | null | undefined) {
  return {
    summary: {
      total_actions: Number(payload?.summary?.total_actions ?? 0),
      unique_entities: Number(payload?.summary?.unique_entities ?? 0),
      unique_actors: Number(payload?.summary?.unique_actors ?? 0),
      consistency_rate: Number(payload?.summary?.consistency_rate ?? 0),
      alignment_rate: Number(payload?.summary?.alignment_rate ?? 0),
      review_velocity_24h: Number(payload?.summary?.review_velocity_24h ?? 0),
    },
    queue_summaries: Array.isArray(payload?.queue_summaries) ? payload.queue_summaries : [],
    actor_summaries: Array.isArray(payload?.actor_summaries) ? payload.actor_summaries : [],
    conflict_entities: Array.isArray(payload?.conflict_entities) ? payload.conflict_entities : [],
    warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
  } satisfies ReviewAnalyticsResponse
}

export default function IntentControlCenterPage() {
  const [range, setRange] = useState<DateRangePreset>('30d')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [incidentMessage, setIncidentMessage] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [incidentUpdatingId, setIncidentUpdatingId] = useState<string | null>(null)
  const [rollbackRunningId, setRollbackRunningId] = useState<string | null>(null)
  const [rollbackSnapshots, setRollbackSnapshots] = useState<RollbackSnapshot[]>([])
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null)

  const [decisionData, setDecisionData] = useState<IntentDecisionResponse | null>(null)
  const [guardrailData, setGuardrailData] = useState<GuardrailResponse | null>(null)
  const [bidPolicyData, setBidPolicyData] = useState<BidPolicyResponse | null>(null)
  const [reviewAnalytics, setReviewAnalytics] = useState<ReviewAnalyticsResponse | null>(null)
  const [scorecardData, setScorecardData] = useState<ScorecardResponse | null>(null)

  const topDecisions = useMemo(
    () => decisionData?.decisions.slice(0, 40) ?? [],
    [decisionData]
  )
  const openIncidents = useMemo(() => guardrailData?.open_incidents ?? [], [guardrailData])

  const loadData = useCallback(async () => {
    const decisionRes = await fetch(`/api/intent/decisions?range=${range}&limit=500`)
    if (!decisionRes.ok) {
      throw new Error(await decisionRes.text())
    }

    const periodDays = range === '7d' ? 7 : range === '60d' ? 60 : range === '90d' ? 90 : 30
    const [guardrailRes, bidPolicyRes, rollbackRes, reviewAnalyticsRes, scorecardRes] = await Promise.all([
      fetch('/api/intent/guardrails'),
      fetch('/api/intent/bid-policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }),
      fetch('/api/intent/rollback?limit=20'),
      fetch(`/api/intent/review-analytics?range=${range}&limit=2000`),
      fetch(`/api/intent/scorecard?period_days=${periodDays}`),
    ])

    if (!guardrailRes.ok) {
      throw new Error(await guardrailRes.text())
    }

    if (!bidPolicyRes.ok) {
      throw new Error(await bidPolicyRes.text())
    }
    if (!rollbackRes.ok) {
      throw new Error(await rollbackRes.text())
    }
    if (!reviewAnalyticsRes.ok) {
      throw new Error(await reviewAnalyticsRes.text())
    }
    if (!scorecardRes.ok) {
      throw new Error(await scorecardRes.text())
    }

    const decisions = (await decisionRes.json()) as IntentDecisionResponse
    const guardrails = (await guardrailRes.json()) as GuardrailResponse
    const bidPolicy = (await bidPolicyRes.json()) as BidPolicyResponse
    const rollback = (await rollbackRes.json()) as {
      snapshots?: RollbackSnapshot[]
      warnings?: string[]
    }
    const reviewAnalyticsPayload = normalizeReviewAnalyticsResponse(
      (await reviewAnalyticsRes.json()) as Partial<ReviewAnalyticsResponse>
    )
    const scorecard = (await scorecardRes.json()) as ScorecardResponse

    const mergedWarnings = [
      ...(guardrails.warnings ?? []),
      ...(bidPolicy.warnings ?? []),
      ...(rollback.warnings ?? []),
      ...(reviewAnalyticsPayload.warnings ?? []),
      ...(scorecard.warnings ?? []),
    ]

    setDecisionData(decisions)
    setGuardrailData(guardrails)
    setBidPolicyData(bidPolicy)
    setReviewAnalytics(reviewAnalyticsPayload)
    setScorecardData(scorecard)
    const snapshots = rollback.snapshots ?? []
    setRollbackSnapshots(snapshots)
    setSelectedSnapshotId((current) => {
      if (current && snapshots.some((snapshot) => snapshot.id === current)) {
        return current
      }
      return snapshots[0]?.id ?? null
    })
    setWarnings(Array.from(new Set(mergedWarnings)))
  }, [range])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setErrorMessage(null)
    try {
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load intent control center')
    } finally {
      setRefreshing(false)
    }
  }, [loadData])

  const updateIncidentStatus = useCallback(
    async (incidentId: string, status: 'acknowledged' | 'resolved') => {
      setIncidentUpdatingId(incidentId)
      setErrorMessage(null)
      try {
        const res = await fetch('/api/intent/guardrails/incidents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            incident_id: incidentId,
            status,
            actor: 'dashboard:intent-control-center',
          }),
        })

        if (!res.ok) {
          throw new Error(await res.text())
        }

        const payload = (await res.json()) as { incident?: { status?: string } }
        const nextStatus = payload.incident?.status ?? status
        setIncidentMessage(`Incident ${incidentId} updated to ${nextStatus}.`)
        await loadData()
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to update incident status')
      } finally {
        setIncidentUpdatingId(null)
      }
    },
    [loadData]
  )

  const runRollback = useCallback(
    async (incidentId: string) => {
      setRollbackRunningId(incidentId)
      setErrorMessage(null)
      try {
        const response = await fetch('/api/intent/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            snapshot_id: selectedSnapshotId ?? undefined,
            reason: `incident:${incidentId}`,
            created_by: 'dashboard:intent-control-center',
          }),
        })

        if (!response.ok) {
          throw new Error(await response.text())
        }

        const payload = (await response.json()) as {
          rollback_applied?: boolean
          deactivated_negative_count?: number
        }
        const deactivatedCount = Number(payload.deactivated_negative_count ?? 0)
        setIncidentMessage(
          `Rollback executed for ${incidentId}. Deactivated negatives: ${deactivatedCount}.`
        )
        await loadData()
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to run rollback')
      } finally {
        setRollbackRunningId(null)
      }
    },
    [loadData, selectedSnapshotId]
  )

  useEffect(() => {
    setLoading(true)
    setErrorMessage(null)
    void loadData()
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load intent control center')
      })
      .finally(() => setLoading(false))
  }, [loadData])

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Intent Control Center</h1>
          <p className="text-muted-foreground">
            Unified intent routing, confidence-gated decisioning, and guardrail-aware optimization for Shopping + Search.
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
          <Button onClick={() => void refresh()} disabled={refreshing || loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {errorMessage ? (
        <Card className="border-destructive/50">
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      ) : null}

      {incidentMessage ? (
        <Card className="border-emerald-500/40">
          <CardContent className="py-4 text-sm text-emerald-700">{incidentMessage}</CardContent>
        </Card>
      ) : null}

      {guardrailData ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5" />
              Guardrail Status
            </CardTitle>
            <CardDescription>
              Automated safety posture for promotions, bid updates, and Search graduation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={guardrailVariant(guardrailData.status)}>{guardrailData.status.toUpperCase()}</Badge>
              <span className="text-sm text-muted-foreground">
                Stale data: {guardrailData.stale_data_hours.toFixed(1)}h | Critical incidents:{' '}
                {guardrailData.open_critical_incidents} | High incidents: {guardrailData.open_high_incidents}
              </span>
            </div>
            {guardrailData.derived_incidents.length > 0 ? (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {guardrailData.derived_incidents.map((incident) => (
                  <li key={`${incident.ruleId}-${incident.severity}`}>
                    <span className="font-medium">{incident.ruleId}</span>: {incident.message}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No derived incidents from current thresholds.</p>
            )}
            {openIncidents.length > 0 ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Open incidents requiring operator action</p>
                <div className="space-y-2">
                  {openIncidents.map((incident) => {
                    const isUpdating = incidentUpdatingId === incident.id
                    return (
                      <div
                        key={incident.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2"
                      >
                        <div className="space-y-1">
                          <p className="text-sm font-medium">
                            {incident.id} · {incident.rule_id}
                          </p>
                          <p className="text-xs text-muted-foreground">{incident.message}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{incident.severity.toUpperCase()}</Badge>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => void runRollback(incident.id)}
                            disabled={isUpdating || rollbackRunningId === incident.id}
                          >
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Run rollback {incident.id}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void updateIncidentStatus(incident.id, 'acknowledged')}
                            disabled={isUpdating}
                          >
                            Acknowledge {incident.id}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => void updateIncidentStatus(incident.id, 'resolved')}
                            disabled={isUpdating || rollbackRunningId === incident.id}
                          >
                            Resolve {incident.id}
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}
            <div className="rounded-md border p-3 text-sm">
              <p className="font-medium">Rollback snapshot source</p>
              {rollbackSnapshots.length > 0 ? (
                <p className="text-muted-foreground">
                  Using snapshot {selectedSnapshotId ?? rollbackSnapshots[0].id} ({rollbackSnapshots.length}{' '}
                  available).
                </p>
              ) : (
                <p className="text-muted-foreground">
                  No snapshots available. Rollback runs in log-only mode until snapshots are created.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {scorecardData ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Executive Scorecard
            </CardTitle>
            <CardDescription>
              Profit, efficiency, and decision velocity for the last {scorecardData.periodDays} days.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">ROAS</p>
                <p className="text-xl font-semibold">{scorecardData.roas.toFixed(2)}x</p>
                <p className="text-xs text-muted-foreground">
                  ${scorecardData.totalRevenue.toLocaleString()} rev / ${scorecardData.totalCost.toLocaleString()} cost
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">CPA</p>
                <p className="text-xl font-semibold">${scorecardData.cpa.toFixed(2)}</p>
                <p className="text-xs text-muted-foreground">
                  {scorecardData.totalConversions.toLocaleString()} conversions
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Automation rate</p>
                <p className="text-xl font-semibold">{(scorecardData.automationRate * 100).toFixed(0)}%</p>
                <p className="text-xs text-muted-foreground">
                  {(scorecardData.pendingReviewRate * 100).toFixed(0)}% pending review
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Decision latency</p>
                <p className="text-xl font-semibold">{scorecardData.avgDecisionLatencyHours.toFixed(1)}h</p>
                <p className="text-xs text-muted-foreground">
                  Health:{' '}
                  <Badge
                    variant={
                      scorecardData.operationalHealth.healthGrade === 'critical'
                        ? 'destructive'
                        : scorecardData.operationalHealth.healthGrade === 'degraded'
                          ? 'outline'
                          : 'secondary'
                    }
                  >
                    {scorecardData.operationalHealth.healthGrade.toUpperCase()}
                  </Badge>
                </p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-md border p-3 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Promote</p>
                <p className="text-lg font-semibold text-emerald-600">
                  {(scorecardData.actionBreakdown.promote * 100).toFixed(0)}%
                </p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Demote</p>
                <p className="text-lg font-semibold text-amber-600">
                  {(scorecardData.actionBreakdown.demote * 100).toFixed(0)}%
                </p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Negative</p>
                <p className="text-lg font-semibold text-red-600">
                  {(scorecardData.actionBreakdown.negative * 100).toFixed(0)}%
                </p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Hold</p>
                <p className="text-lg font-semibold text-slate-600">
                  {(scorecardData.actionBreakdown.hold * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Terms evaluated</CardDescription>
            <CardTitle>{decisionData?.total_terms_evaluated.toLocaleString() ?? '0'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Review required</CardDescription>
            <CardTitle>{decisionData?.review_required_count.toLocaleString() ?? '0'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Policy version</CardDescription>
            <CardTitle>{decisionData?.policy_version ?? 'intent_v1'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Bid policy rows</CardDescription>
            <CardTitle>{bidPolicyData?.decision_count.toLocaleString() ?? '0'}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {reviewAnalytics ? (
        <Card>
          <CardHeader>
            <CardTitle>Operator Calibration & Decision Consistency</CardTitle>
            <CardDescription>
              Review actions, policy alignment, and cross-operator consistency for high-volume queue management.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Review actions</p>
                <p className="text-xl font-semibold">
                  {reviewAnalytics.summary.total_actions.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  {reviewAnalytics.summary.review_velocity_24h.toLocaleString()} in last 24h
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Consistency rate</p>
                <p className="text-xl font-semibold">
                  {(reviewAnalytics.summary.consistency_rate * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-muted-foreground">
                  Based on conflicting action patterns by queue/entity
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Policy alignment</p>
                <p className="text-xl font-semibold">
                  {(reviewAnalytics.summary.alignment_rate * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-muted-foreground">
                  {reviewAnalytics.summary.unique_actors.toLocaleString()} active operators
                </p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <p className="text-sm font-medium">Queue consistency</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Queue</TableHead>
                      <TableHead>Actions</TableHead>
                      <TableHead>Entities</TableHead>
                      <TableHead>Consistency</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reviewAnalytics.queue_summaries.slice(0, 5).map((queue) => (
                      <TableRow key={queue.queue_name}>
                        <TableCell>{queue.queue_name}</TableCell>
                        <TableCell>{queue.total_actions.toLocaleString()}</TableCell>
                        <TableCell>{queue.unique_entities.toLocaleString()}</TableCell>
                        <TableCell>{(queue.consistency_rate * 100).toFixed(0)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Operator calibration</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Actor</TableHead>
                      <TableHead>Actions</TableHead>
                      <TableHead>Queues</TableHead>
                      <TableHead>Alignment</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reviewAnalytics.actor_summaries.slice(0, 5).map((actor) => (
                      <TableRow key={actor.actor}>
                        <TableCell>{actor.actor}</TableCell>
                        <TableCell>{actor.total_actions.toLocaleString()}</TableCell>
                        <TableCell>{actor.queue_count.toLocaleString()}</TableCell>
                        <TableCell>{(actor.alignment_rate * 100).toFixed(0)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Top Intent Decisions</CardTitle>
          <CardDescription>Highest-priority route outcomes with confidence and explainability.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Search term</TableHead>
                <TableHead>Intent class</TableHead>
                <TableHead>Route</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Review</TableHead>
                <TableHead>Reason codes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {topDecisions.map((row) => (
                <TableRow key={row.search_term}>
                  <TableCell className="max-w-[320px] truncate">{row.search_term}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{row.decision.classification.intentClass}</Badge>
                  </TableCell>
                  <TableCell>{row.decision.routeAction}</TableCell>
                  <TableCell>{row.decision.recommendedTier ?? '-'}</TableCell>
                  <TableCell>{(row.decision.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>
                    <Badge variant={row.decision.requiresReview ? 'outline' : 'secondary'}>
                      {row.decision.requiresReview ? 'REVIEW' : 'AUTO-SAFE'}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-[420px] truncate">{row.decision.reasonCodes.join(', ')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {bidPolicyData ? (
        <Card>
          <CardHeader>
            <CardTitle>Bid Policy Recommendations</CardTitle>
            <CardDescription>Intent-aware target recommendations with confidence gating.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Key</TableHead>
                  <TableHead>Observed ROAS</TableHead>
                  <TableHead>Current target</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Recommended target</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bidPolicyData.decisions.slice(0, 20).map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>{row.key}</TableCell>
                    <TableCell>{row.observed_roas.toFixed(2)}</TableCell>
                    <TableCell>{row.current_target_roas.toFixed(2)}</TableCell>
                    <TableCell>{row.decision.action}</TableCell>
                    <TableCell>{row.decision.recommendedTargetRoas.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}

      {warnings.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Warnings</CardTitle>
            <CardDescription>Non-blocking issues detected during control-plane load.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
