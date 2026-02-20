import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { DEFAULT_STALE_THRESHOLD_HOURS } from '@/lib/optimization/decomposition/config'
import { computeCoverageStats } from '@/lib/optimization/decomposition/repository'

function sanitizeLimit(input: string | null, fallback = 500, max = 5000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function confidenceBucket(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.8) {
    return 'high'
  }
  if (confidence >= 0.6) {
    return 'medium'
  }
  return 'low'
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
      limit,
      offset: 0,
      sortBy: 'impact_desc',
      pipeline: {
        enabled: true,
        persist: false,
      },
    })

    const pairInputs = termsResult.terms.flatMap((term) =>
      term.custom_label_0s.map((assignment) => ({
        searchTerm: term.search_term,
        customLabel0: assignment.custom_label_0,
      }))
    )

    const coverage = await computeCoverageStats(pairInputs, DEFAULT_STALE_THRESHOLD_HOURS)

    const confidenceDistribution = termsResult.terms.reduce(
      (acc, term) => {
        const bucket = confidenceBucket(term.recommendation?.confidence ?? 0)
        acc[bucket] += 1
        return acc
      },
      {
        high: 0,
        medium: 0,
        low: 0,
      }
    )

    const lowConfidenceTerms = termsResult.terms
      .map((term) => ({
        search_term: term.search_term,
        confidence: term.recommendation?.confidence ?? 0,
        reason_codes: term.recommendation?.reason_codes ?? [],
        total_impressions: term.custom_label_0s.reduce((sum, assignment) => sum + assignment.impressions, 0),
      }))
      .sort((a, b) => a.confidence - b.confidence)
      .slice(0, 25)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      pipeline: termsResult.pipeline,
      coverage: {
        total_pairs: coverage.totalPairs,
        cached_pairs: coverage.cachedPairs,
        missing_pairs: coverage.missingPairs,
        stale_pairs: coverage.stalePairs,
        coverage_percent: coverage.coveragePercent,
        stale_percent: coverage.staleShare,
        last_recompute_at:
          termsResult.pipeline?.pairs_recomputed && termsResult.pipeline.pairs_recomputed > 0
            ? termsResult.generated_at
            : coverage.latestCreatedAt,
      },
      confidence_distribution: confidenceDistribution,
      low_confidence_terms: lowConfidenceTerms,
      warnings: termsResult.pipeline?.warnings ?? [],
    })
  } catch (error) {
    console.error('Decomposition health fetch failed:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    )
  }
}
