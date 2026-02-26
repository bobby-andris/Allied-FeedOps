import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  getLabelTierPerformance,
  getExistingFunnelTerms,
  defaultDateWindow,
  sanitizeDateInput,
  sanitizeCustomLabel,
} from '@/lib/shopping-funnel/service'
import { decomposeSearchTerm } from '@/lib/optimization/query-intelligence'
import {
  computeTierDistributions,
  computeGlobalDistributions,
  scoreTerm,
  getCachedDistributions,
  buildHeroCallout,
} from '@/lib/optimization/tier-scoring'
import type { TermScore, ImpactRange, FunnelTier } from '@/lib/optimization/tier-scoring.types'
import { DEFAULT_CALIBRATION } from '@/lib/optimization/tier-scoring.types'

export const maxDuration = 60

/**
 * Aggregate impact ranges across all actionable terms.
 * Includes both statistically misplaced terms AND trigger-based terms
 * (wasted_spend, promote_intent, promote_conversion, demote_underperform, under_invested).
 * Sums the low/mid/high bounds independently.
 */
function aggregateImpact(scores: TermScore[]): ImpactRange {
  const actionable = scores.filter(s =>
    (s.isMisplaced || (s.trigger && s.trigger !== 'observe')) && s.impact
  )
  const totals = actionable.reduce(
    (acc, s) => {
      if (s.impact) {
        acc.low += s.impact.low
        acc.mid += s.impact.mid
        acc.high += s.impact.high
      }
      return acc
    },
    { low: 0, mid: 0, high: 0 }
  )

  return {
    low: Math.round(totals.low * 100) / 100,
    mid: Math.round(totals.mid * 100) / 100,
    high: Math.round(totals.high * 100) / 100,
    currency: 'USD',
    period: 'monthly',
    direction: 'lateral' as const,
  }
}

/**
 * Map the tier string from ExistingFunnelAssignment to FunnelTier.
 * ExistingFunnelAssignment uses mixed case ('High' | 'Medium' | 'Low')
 * while FunnelTier is uppercase ('HIGH' | 'MEDIUM' | 'LOW').
 */
function mapTierToFunnelTier(tier: string): FunnelTier | null {
  const mapping: Record<string, FunnelTier> = {
    high: 'HIGH',
    medium: 'MEDIUM',
    low: 'LOW',
  }
  return mapping[tier.toLowerCase()] ?? null
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const forceRefresh = params.get('forceRefresh') === 'true'
    const customLabel0Filter = sanitizeCustomLabel(params.get('customLabel0'))

    // Build date window
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate

    // Fetch data in parallel
    const [labelTierPerf, existingTermsResult] = await Promise.all([
      getLabelTierPerformance({ startDate, endDate }),
      getExistingFunnelTerms({
        startDate,
        endDate,
        customLabel0: customLabel0Filter,
        tier: 'all',
        limit: 5000,
        offset: 0,
      }),
    ])

    // Handle empty data
    if (labelTierPerf.rows.length === 0) {
      return NextResponse.json({
        distributions: {},
        globalFallback: {},
        scores: [],
        heroCallout: 'No tier performance data available',
        computedAt: new Date().toISOString(),
        totalGroups: 0,
        totalTermsScored: 0,
        totalMisplaced: 0,
        totalImpact: { low: 0, mid: 0, high: 0, currency: 'USD', period: 'monthly', direction: 'lateral' as const },
        message: 'No tier performance data available for the selected date range.',
      })
    }

    // Filter labelTierPerf rows by customLabel0 if specified
    const filteredRows = customLabel0Filter
      ? labelTierPerf.rows.filter(
          r => r.custom_label_0.toLowerCase() === customLabel0Filter.toLowerCase()
        )
      : labelTierPerf.rows

    // Compute distributions (use cache unless forceRefresh)
    const { distributions, globalFallback } = forceRefresh
      ? {
          distributions: computeTierDistributions(filteredRows),
          globalFallback: computeGlobalDistributions(labelTierPerf.rows),
        }
      : getCachedDistributions(filteredRows)

    // Also compute global fallback from all rows (not just filtered)
    const globalFallbackDists = forceRefresh
      ? globalFallback
      : computeGlobalDistributions(labelTierPerf.rows)

    // Fetch feed alignment scores from Cloud Run /score-intent (Domain A)
    // Gracefully degrade if unavailable — scoring works with behavioral signals only
    const uniqueTerms = [...new Set(
      existingTermsResult.terms
        .filter(t => t.funnels.length > 0)
        .map(t => t.search_term)
    )]

    let feedAlignmentMap = new Map<string, number>()
    const AVG_CPA = 64.22 // From Google Ads account audit (90-day window)

    try {
      const pipelineUrl = process.env.FEEDOPS_PIPELINE_URL || 'https://feedops-pipeline-623866089882.us-east1.run.app'
      const intentRes = await fetch(`${pipelineUrl}/score-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queries: uniqueTerms }),
        signal: AbortSignal.timeout(10000), // 10s timeout
      })

      if (intentRes.ok) {
        const intentData = await intentRes.json()
        if (intentData.scores && Array.isArray(intentData.scores)) {
          for (const scoreItem of intentData.scores) {
            if (scoreItem.query && typeof scoreItem.feed_alignment_score === 'number') {
              feedAlignmentMap.set(scoreItem.query, scoreItem.feed_alignment_score)
            }
          }
        }
        console.log(`Feed alignment scores fetched for ${feedAlignmentMap.size}/${uniqueTerms.length} terms`)
      } else {
        console.warn(`Cloud Run /score-intent returned ${intentRes.status} — proceeding without feed alignment`)
      }
    } catch (err) {
      console.warn('Cloud Run /score-intent unavailable — proceeding with behavioral signals only:', err instanceof Error ? err.message : err)
    }

    // Score each term once per custom_label_0 funnel assignment (multi-label support)
    const scores: TermScore[] = []
    for (const term of existingTermsResult.terms) {
      if (!term.funnels.length) continue

      const intentFeatures = decomposeSearchTerm(term.search_term)
      const feedScore = feedAlignmentMap.get(term.search_term)

      // Score once per custom_label_0 funnel assignment
      for (const funnel of term.funnels) {
        const currentTier = mapTierToFunnelTier(funnel.tier)
        if (!currentTier) continue // Skip 'Campaign Negative' and 'Unknown'

        const groupKey = funnel.custom_label_0
        const groupDist = distributions.get(groupKey)
        if (!groupDist) continue // Skip if no distribution data for this group

        // scoreTerm reads funnels[0] internally — shallow copy with this funnel first
        const termForThisFunnel = {
          ...term,
          funnels: [funnel, ...term.funnels.filter(f => f !== funnel)],
        }

        const scored = scoreTerm(termForThisFunnel, groupDist, globalFallbackDists, intentFeatures, DEFAULT_CALIBRATION, feedScore, AVG_CPA)
        scores.push(scored)
      }
    }

    // Update scoredTerms on each group's distribution
    for (const score of scores) {
      const groupDist = distributions.get(score.customLabel0)
      if (groupDist) {
        groupDist.scoredTerms++
      }
    }

    // Build hero callout
    const heroCallout = buildHeroCallout(scores)

    // Persist scores to query_value_scores in chunks of 500
    const supabase = createAdminClient()
    for (let i = 0; i < scores.length; i += 500) {
      const chunk = scores.slice(i, i + 500)
      const { error } = await supabase.from('query_value_scores').upsert(
        chunk.map(s => ({
          search_term: s.searchTerm,
          custom_label_0: s.customLabel0,
          score_version: 'v2-tier-scoring',
          tier_fit_scores: s.tierFitScores,
          recommended_tier: s.recommendedTier,
          net_monthly_impact: s.impact?.mid ?? 0,
          scored_at: new Date().toISOString(),
          // Preserve existing columns with reasonable defaults
          expected_clicks: 0,
          expected_cvr: 0,
          expected_conversion_value: 0,
          expected_profit_proxy: 0,
          uncertainty: 1 - s.confidence.score,
          impact_score: s.impact?.mid ?? 0,
          model_inputs: {
            confidence: s.confidence,
            fallbackLevel: s.fallbackLevel,
            currentTier: s.currentTier,
            fitScoreDelta: s.fitScoreDelta,
            dataConfirmed: s.dataConfirmed,
            isMisplaced: s.isMisplaced,
            recommendedAction: s.recommendedAction,
            actionReason: s.actionReason,
            totalImpressions: s.totalImpressions,
            actualRoas: s.actualRoas,
            totalConversions: s.totalConversions,
            totalCostMicros: s.totalCostMicros,
            trigger: s.trigger,
            intentScore: s.intentScore,
            targetTier: s.targetTier,
          },
        })),
        { onConflict: 'search_term,custom_label_0' }
      )

      if (error) {
        console.error('Failed to persist tier scores chunk:', error)
        // Continue processing remaining chunks even if one fails
      }
    }

    // Auto-identify search promotion candidates (high-ROAS, high-volume, converting terms)
    const searchCandidates = scores
      .filter(s => s.actualRoas > 3.0 && (s.totalImpressions ?? 0) > 100 && s.totalConversions > 0)
      .map(s => ({
        search_term: s.searchTerm,
        custom_label_0: s.customLabel0,
        recommended_search_tier: 'exact' as const,
        status: 'candidate',
        confidence: s.confidence.score,
        metadata: {
          source: 'tier_scoring_auto',
          actual_roas: s.actualRoas,
          total_conversions: s.totalConversions,
          total_impressions: s.totalImpressions,
          identified_at: new Date().toISOString(),
        },
      }))

    if (searchCandidates.length > 0) {
      const { error: searchError } = await supabase
        .from('search_buildout_recommendations')
        .upsert(searchCandidates, { onConflict: 'search_term' })

      if (searchError) {
        console.error('Failed to persist search candidates:', searchError)
      }
    }

    // Convert Map to plain object for JSON serialization
    const distributionsObject: Record<string, unknown> = {}
    for (const [key, value] of distributions) {
      distributionsObject[key] = value
    }

    return NextResponse.json({
      distributions: distributionsObject,
      globalFallback: globalFallbackDists,
      scores,
      heroCallout,
      computedAt: new Date().toISOString(),
      totalGroups: distributions.size,
      totalTermsScored: scores.length,
      totalMisplaced: scores.filter(s => s.isMisplaced || (s.trigger && s.trigger !== 'observe')).length,
      totalImpact: aggregateImpact(scores),
    })
  } catch (error) {
    console.error('Tier scoring computation failed:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    )
  }
}
