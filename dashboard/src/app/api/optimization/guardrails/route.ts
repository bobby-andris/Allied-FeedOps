import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getLabelTierPerformance,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import {
  buildOpportunityClusters,
  buildRecommendationQueue,
  buildRoasRecommendations,
} from '@/lib/optimization/control-center'
import { computeSupplementalConfidenceGate } from '@/lib/optimization/supplemental-confidence'
import { fetchGa4AttributionQuality, fetchGa4AudiencePerformance } from '@/lib/ga4/client'
import { fetchShopifyValueSignalsWithLabelMapping } from '@/lib/shopify/value-signals'
import {
  DEFAULT_AUDIENCE_WATCHLIST,
  buildAudienceRecommendations,
  buildAudienceWatchItems,
} from '@/lib/ga4/audience-watchlist'
import { createAdminClient } from '@/lib/supabase/admin'
import { evaluateOptimizationGuardrails } from '@/lib/optimization/guardrails'

function sanitizeLimit(input: string | null, fallback = 3000, max = 10000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function computeLookbackDays(startDate: string, endDate: string): number {
  const start = new Date(startDate)
  const end = new Date(endDate)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return 30
  }
  const dayMs = 24 * 60 * 60 * 1000
  const diff = Math.ceil((end.getTime() - start.getTime()) / dayMs) + 1
  return Math.min(Math.max(diff, 7), 365)
}

function parseBoolean(input: string | null, fallback = false): boolean {
  if (input === null) return fallback
  return input === '1' || input.toLowerCase() === 'true' || input.toLowerCase() === 'yes'
}

function normalizeReportDate(raw: string): string {
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) {
    return new Date().toISOString().slice(0, 10)
  }
  return parsed.toISOString().slice(0, 10)
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return 'Unknown error'
}

function isMissingRelationError(error: unknown, relationName?: string): boolean {
  const message = extractErrorMessage(error).toLowerCase()
  if (!message.includes('relation') || !message.includes('does not exist')) {
    return false
  }
  if (!relationName) {
    return true
  }
  return message.includes(relationName.toLowerCase())
}

function isPersistenceAuthorized(request: NextRequest, persist: boolean): boolean {
  if (!persist) return true
  if (process.env.NODE_ENV === 'development') return true
  const token = process.env.INTERNAL_API_TOKEN
  if (!token) return false
  return request.headers.get('x-internal-token') === token
}

async function evaluateGuardrails(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const range = params.get('range')
  const fallbackWindow = defaultDateWindow(range)
  const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
  const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate
  const customLabel0 = sanitizeCustomLabel(params.get('custom_label_0'))
  const minImpressions = sanitizeMinImpressions(params.get('min_impressions'))
  const limit = sanitizeLimit(params.get('limit'))

  const warnings: string[] = []
  const reportDate = normalizeReportDate(endDate)

  const termsResult = await getNeedsDecisionTerms({
    startDate,
    endDate,
    customLabel0,
    minImpressions,
    limit,
    offset: 0,
    sortBy: 'impact_desc',
  })

  const [ga4Signal, shopifySignal] = await Promise.all([
    fetchGa4AttributionQuality({ startDate, endDate, limit: 500 })
      .then((quality) => ({
        available: true,
        qualityScore: quality.qualityScore,
        riskLevel: quality.riskLevel,
        unassignedRevenueShare: quality.unassignedRevenueShare,
        notSetCampaignRevenueShare: quality.notSetCampaignRevenueShare,
      }))
      .catch((error) => {
        warnings.push(`GA4 supplemental signal unavailable: ${extractErrorMessage(error)}`)
        return { available: false }
      }),
    fetchShopifyValueSignalsWithLabelMapping({
      lookbackDays: computeLookbackDays(startDate, endDate),
      maxOrders: 750,
    })
      .then((summary) => ({
        available: true,
        mappedSkuCount: summary.mappedSkuCount,
        skuCountInOrders: summary.skuCountInOrders,
        totalRevenue: summary.totalRevenue,
        unmappedSkuRevenue: summary.unmappedSkuRevenue,
      }))
      .catch((error) => {
        warnings.push(`Shopify supplemental signal unavailable: ${extractErrorMessage(error)}`)
        return { available: false }
      }),
  ])

  const supplemental = computeSupplementalConfidenceGate({
    ga4: ga4Signal,
    shopify: shopifySignal,
  })
  warnings.push(...supplemental.warnings)

  const queue = buildRecommendationQueue(termsResult.terms, 3000, {
    supplementalGate: supplemental,
  })
  const highImpactQueue = queue.filter((item) => item.impactScore >= 150)
  const lowConfidenceHighImpactQueue = highImpactQueue.filter((item) => item.confidence < 0.55)

  const performance = await getLabelTierPerformance({ startDate, endDate })
  const roasRecommendations = buildRoasRecommendations(
    performance.rows.map((row) => ({
      customLabel0: row.custom_label_0,
      tier: row.tier,
      spend: row.cost_micros / 1_000_000,
      conversionValue: row.conversions_value,
      conversions: row.conversions,
      clicks: row.clicks,
    }))
  )
  const actionableRoasRecommendations = roasRecommendations.filter(
    (item) => item.guardrailStatus === 'actionable'
  )

  const clusters = buildOpportunityClusters(termsResult.terms)
  const highOverlapClusters = clusters.filter((item) => item.overlapRiskLevel === 'high')

  let highPriorityAudienceCount = 0
  try {
    const [attributionQuality, audiencePerformance] = await Promise.all([
      fetchGa4AttributionQuality({ startDate, endDate, limit: 500 }),
      fetchGa4AudiencePerformance({ startDate, endDate, limit: 200 }),
    ])
    const watchItems = buildAudienceWatchItems(audiencePerformance.rows, DEFAULT_AUDIENCE_WATCHLIST)
    const audienceRecommendations = buildAudienceRecommendations(watchItems, attributionQuality)
    highPriorityAudienceCount = audienceRecommendations.filter((item) => item.priority === 'high').length
  } catch (error) {
    warnings.push(`Audience recommendation context unavailable: ${extractErrorMessage(error)}`)
  }

  const evaluation = evaluateOptimizationGuardrails({
    supplementalMultiplier: supplemental.multiplier,
    supplementalWarnings: Array.from(new Set(warnings)),
    queueMetrics: {
      total: queue.length,
      highImpactCount: highImpactQueue.length,
      lowConfidenceHighImpactCount: lowConfidenceHighImpactQueue.length,
    },
    roasMetrics: {
      total: roasRecommendations.length,
      actionableCount: actionableRoasRecommendations.length,
    },
    opportunityMetrics: {
      total: clusters.length,
      highOverlapCount: highOverlapClusters.length,
    },
    audienceMetrics: {
      highPriorityCount: highPriorityAudienceCount,
    },
    reportDate,
  })

  return {
    startDate,
    endDate,
    reportDate,
    warnings: Array.from(new Set(warnings)),
    termsResult,
    supplemental,
    evaluation,
    metrics: {
      queue_total: queue.length,
      queue_high_impact_count: highImpactQueue.length,
      queue_low_confidence_high_impact_count: lowConfidenceHighImpactQueue.length,
      roas_total: roasRecommendations.length,
      roas_actionable_count: actionableRoasRecommendations.length,
      opportunities_total: clusters.length,
      opportunities_high_overlap_count: highOverlapClusters.length,
      audience_high_priority_count: highPriorityAudienceCount,
      low_confidence_high_impact_share: evaluation.metrics.lowConfidenceHighImpactShare,
      roas_actionable_share: evaluation.metrics.roasActionableShare,
      high_overlap_cluster_share: evaluation.metrics.highOverlapClusterShare,
    },
  }
}

async function persistGuardrailArtifacts(input: {
  reportDate: string
  incidents: ReturnType<typeof evaluateOptimizationGuardrails>['incidents']
  decision: ReturnType<typeof evaluateOptimizationGuardrails>['decision']
  metrics: Record<string, unknown>
  startDate: string
  endDate: string
  supplemental: ReturnType<typeof computeSupplementalConfidenceGate>
}) {
  const supabase = createAdminClient()
  const result = {
    incidentsInserted: 0,
    experimentSnapshotsInserted: 0,
  }

  if (input.incidents.length > 0) {
    const ruleIds = input.incidents.map((incident) => incident.ruleId)
    const { data: existing, error: existingError } = await supabase
      .from('guardrail_incidents')
      .select('rule_id, metadata, status')
      .in('rule_id', ruleIds)
      .in('status', ['open', 'acknowledged'])

    if (existingError) {
      throw existingError
    }

    const existingKeys = new Set(
      (existing ?? [])
        .map((row) => {
          const metadata = (row.metadata ?? {}) as Record<string, unknown>
          const existingDate = typeof metadata.report_date === 'string' ? metadata.report_date : null
          return existingDate ? `${row.rule_id}|${existingDate}` : null
        })
        .filter((value): value is string => Boolean(value))
    )

    const payload = input.incidents
      .filter((incident) => !existingKeys.has(`${incident.ruleId}|${input.reportDate}`))
      .map((incident) => ({
        rule_id: incident.ruleId,
        severity: incident.severity,
        status: incident.status,
        impacted_entities: incident.impactedEntities,
        message: incident.message,
        suggested_action: incident.suggestedAction,
        metadata: incident.metadata,
      }))

    if (payload.length > 0) {
      const { error } = await supabase.from('guardrail_incidents').insert(payload)
      if (error) {
        throw error
      }
      result.incidentsInserted = payload.length
    }
  }

  const experimentPayload = {
    experiment_key: 'optimization_guardrail_rollout_v1',
    window_start: input.startDate,
    window_end: input.endDate,
    decision_status: input.decision.status,
    confidence: input.decision.confidence,
    blocking_rules: input.incidents
      .filter((incident) => incident.severity === 'critical' || incident.severity === 'high')
      .map((incident) => incident.ruleId),
    metrics: {
      ...input.metrics,
      supplemental_multiplier: input.supplemental.multiplier,
      supplemental_reasons: input.supplemental.reasons,
      supplemental_diagnostics: input.supplemental.diagnostics,
      decision_rationale: input.decision.rationale,
    },
  }

  const { error: experimentError } = await supabase
    .from('optimization_experiment_snapshots')
    .insert(experimentPayload)
  if (experimentError) {
    throw experimentError
  }
  result.experimentSnapshotsInserted = 1

  return result
}

export async function GET(request: NextRequest) {
  try {
    const evaluation = await evaluateGuardrails(request)
    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: {
        startDate: evaluation.startDate,
        endDate: evaluation.endDate,
      },
      report_date: evaluation.reportDate,
      pipeline: evaluation.termsResult.pipeline,
      supplemental_confidence: evaluation.supplemental,
      guardrail_decision: evaluation.evaluation.decision,
      incidents: evaluation.evaluation.incidents,
      metrics: evaluation.metrics,
      warnings: evaluation.warnings,
      available: evaluation.warnings.length === 0,
    })
  } catch (error) {
    console.error('Optimization guardrail evaluation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const persist = parseBoolean(params.get('persist'), true)

  if (!isPersistenceAuthorized(request, persist)) {
    return NextResponse.json({ error: 'Unauthorized.' }, { status: 401 })
  }

  try {
    const evaluation = await evaluateGuardrails(request)

    let persistenceResult: {
      incidentsInserted: number
      experimentSnapshotsInserted: number
    } | null = null
    const warnings = [...evaluation.warnings]

    if (persist) {
      try {
        persistenceResult = await persistGuardrailArtifacts({
          reportDate: evaluation.reportDate,
          incidents: evaluation.evaluation.incidents,
          decision: evaluation.evaluation.decision,
          metrics: evaluation.metrics,
          startDate: evaluation.startDate,
          endDate: evaluation.endDate,
          supplemental: evaluation.supplemental,
        })
      } catch (error) {
        if (isMissingRelationError(error, 'optimization_experiment_snapshots')) {
          warnings.push(
            'Guardrail experiment instrumentation unavailable: table "optimization_experiment_snapshots" is missing. Apply migration 035.'
          )
        } else if (isMissingRelationError(error, 'guardrail_incidents')) {
          warnings.push(
            'Guardrail incident persistence unavailable: table "guardrail_incidents" is missing. Apply migration 033.'
          )
        } else {
          warnings.push(`Guardrail persistence failed: ${extractErrorMessage(error)}`)
        }
      }
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: {
        startDate: evaluation.startDate,
        endDate: evaluation.endDate,
      },
      report_date: evaluation.reportDate,
      persist_requested: persist,
      pipeline: evaluation.termsResult.pipeline,
      supplemental_confidence: evaluation.supplemental,
      guardrail_decision: evaluation.evaluation.decision,
      incidents: evaluation.evaluation.incidents,
      metrics: evaluation.metrics,
      persistence: persistenceResult,
      warnings,
      available: warnings.length === 0,
    })
  } catch (error) {
    console.error('Optimization guardrail persistence failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
