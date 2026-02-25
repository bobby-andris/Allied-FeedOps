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

export const maxDuration = 60

/**
 * Aggregate impact ranges across all misplaced terms.
 * Sums the low/mid/high bounds independently.
 */
function aggregateImpact(scores: TermScore[]): ImpactRange {
  const misplaced = scores.filter(s => s.isMisplaced && s.impact)
  const totals = misplaced.reduce(
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
        totalImpact: { low: 0, mid: 0, high: 0, currency: 'USD', period: 'monthly' },
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

    // Score each term
    const scores: TermScore[] = []
    for (const term of existingTermsResult.terms) {
      // Skip terms with no valid funnel assignment
      if (!term.funnels.length) continue

      const primaryFunnel = term.funnels[0]
      const currentTier = mapTierToFunnelTier(primaryFunnel.tier)
      if (!currentTier) continue // Skip 'Campaign Negative' and 'Unknown'

      const groupKey = primaryFunnel.custom_label_0
      const groupDist = distributions.get(groupKey)
      if (!groupDist) continue // Skip if no distribution data for this group

      // Get intent features for NLP alignment
      const intentFeatures = decomposeSearchTerm(term.search_term)

      // Score the term
      const scored = scoreTerm(term, groupDist, globalFallbackDists, intentFeatures)
      scores.push(scored)
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
          },
        })),
        { onConflict: 'search_term,custom_label_0' }
      )

      if (error) {
        console.error('Failed to persist tier scores chunk:', error)
        // Continue processing remaining chunks even if one fails
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
      totalMisplaced: scores.filter(s => s.isMisplaced).length,
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
