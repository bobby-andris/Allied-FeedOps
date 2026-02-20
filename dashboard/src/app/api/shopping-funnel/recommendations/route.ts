import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4AttributionQuality } from '@/lib/ga4/client'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildRecommendationQueue } from '@/lib/optimization/control-center'
import { computeSupplementalConfidenceGate } from '@/lib/optimization/supplemental-confidence'
import { fetchShopifyValueSignalsWithLabelMapping } from '@/lib/shopify/value-signals'

function sanitizeLimit(input: string | null, fallback = 100, max = 1000): number {
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

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(params.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(params.get('min_impressions'))
    const limit = sanitizeLimit(params.get('limit'))

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit: 3000,
      offset: 0,
      sortBy: 'impact_desc',
    })
    const warnings: string[] = []

    const [ga4Signal, shopifySignal] = await Promise.all([
      fetchGa4AttributionQuality({
        startDate,
        endDate,
        limit: 500,
      })
        .then((quality) => ({
          available: true,
          qualityScore: quality.qualityScore,
          riskLevel: quality.riskLevel,
          unassignedRevenueShare: quality.unassignedRevenueShare,
          notSetCampaignRevenueShare: quality.notSetCampaignRevenueShare,
        }))
        .catch((error) => {
          warnings.push(
            `GA4 supplemental confidence unavailable: ${
              error instanceof Error ? error.message : 'Unknown error'
            }`
          )
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
          warnings.push(
            `Shopify supplemental confidence unavailable: ${
              error instanceof Error ? error.message : 'Unknown error'
            }`
          )
          return { available: false }
        }),
    ])

    const supplementalConfidence = computeSupplementalConfidenceGate({
      ga4: ga4Signal,
      shopify: shopifySignal,
    })
    warnings.push(...supplementalConfidence.warnings)
    const uniqueWarnings = Array.from(new Set(warnings))

    const queue = buildRecommendationQueue(termsResult.terms, limit, {
      supplementalGate: supplementalConfidence,
    })

    const actionDistribution = queue.reduce<Record<string, number>>((acc, item) => {
      acc[item.actionType] = (acc[item.actionType] ?? 0) + 1
      return acc
    }, {})

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      pipeline: termsResult.pipeline,
      supplemental_confidence: supplementalConfidence,
      warnings: uniqueWarnings,
      total_terms_evaluated: termsResult.total_count,
      queue_count: queue.length,
      action_distribution: actionDistribution,
      queue,
    })
  } catch (error) {
    console.error('Shopping funnel recommendations fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
