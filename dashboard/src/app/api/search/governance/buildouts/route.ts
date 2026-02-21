import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeDateInput,
} from '@/lib/shopping-funnel/service'
import { routeIntentDecision, evaluateSearchGovernance } from '@/lib/intent/policy'
import {
  buildSearchBuildoutSuggestion,
  summarizeSearchBuildoutClusters,
} from '@/lib/intent/buildout-intelligence'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'
import type { IntentClass, SearchTier } from '@/lib/intent/types'

function sanitizeLimit(input: string | null, fallback = 150, max = 2000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function normalizeIntentClass(value: unknown): IntentClass {
  switch (value) {
    case 'BRAND_CORE':
    case 'PRODUCT_HIGH':
    case 'CATEGORY_MID':
    case 'DISCOVERY_LOW':
    case 'COMPETITOR':
    case 'INFO_ASSIST':
    case 'MISMATCH':
    case 'RISK_POLICY':
      return value
    default:
      return 'CATEGORY_MID'
  }
}

function normalizeTier(value: unknown): SearchTier {
  if (value === 'broad' || value === 'phrase' || value === 'exact') {
    return value
  }
  return 'phrase'
}

function normalizeConfidence(value: unknown): number {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(1, numeric))
}

function fallbackTierFromIntent(intentClass: IntentClass): SearchTier {
  if (intentClass === 'PRODUCT_HIGH') return 'exact'
  if (intentClass === 'CATEGORY_MID') return 'phrase'
  return 'broad'
}

type PersistedRecommendationRow = {
  search_term: string
  recommended_search_tier: SearchTier
  confidence: number | null
  metadata: {
    intent_class?: string
    reason_codes?: string[]
  } | null
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate
    const limit = sanitizeLimit(params.get('limit'))
    const supabase = createAdminClient()

    try {
      const { data, error } = await supabase
        .from('search_buildout_recommendations')
        .select('search_term, recommended_search_tier, confidence, metadata')
        .in('status', ['candidate', 'approved'])
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) throw error

      const rows = (data ?? []) as PersistedRecommendationRow[]
      if (rows.length > 0) {
        const suggestions = rows.map((row) => {
          const metadata = row.metadata ?? {}
          const reasonCodes = Array.isArray(metadata.reason_codes)
            ? metadata.reason_codes.filter((code): code is string => typeof code === 'string')
            : ['persisted_buildout_candidate']
          return buildSearchBuildoutSuggestion({
            searchTerm: row.search_term,
            intentClass: normalizeIntentClass(metadata.intent_class),
            recommendedTier: normalizeTier(row.recommended_search_tier),
            confidence: normalizeConfidence(row.confidence),
            reasonCodes,
          })
        })
        const buildoutBriefs = summarizeSearchBuildoutClusters(suggestions, limit)

        return NextResponse.json({
          generated_at: new Date().toISOString(),
          source: 'persisted',
          date_window: { startDate, endDate },
          brief_count: buildoutBriefs.length,
          buildout_briefs: buildoutBriefs,
          warnings,
        })
      }
    } catch (error) {
      if (isMissingRelationError(error, 'search_buildout_recommendations')) {
        warnings.push(
          'Table "search_buildout_recommendations" is missing. Falling back to computed query-mining buildouts.'
        )
      } else {
        warnings.push(`Persisted buildout queue unavailable: ${extractErrorMessage(error)}`)
      }
    }

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0: undefined,
      minImpressions: 0,
      limit: 5000,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const suggestions = termsResult.terms
      .map((term) => {
        const metrics = term.custom_label_0s.reduce(
          (acc, assignment) => {
            acc.impressions += assignment.impressions
            acc.clicks += assignment.clicks
            acc.conversions += assignment.conversions
            acc.conversionsValue += assignment.conversions_value
            acc.costMicros += assignment.cost_micros
            return acc
          },
          {
            impressions: 0,
            clicks: 0,
            conversions: 0,
            conversionsValue: 0,
            costMicros: 0,
          }
        )

        const routeDecision = routeIntentDecision({
          searchTerm: term.search_term,
          metrics,
          existingTerm: term,
        })
        const governance = evaluateSearchGovernance({
          searchTerm: term.search_term,
          currentTier: 'broad',
          metrics,
          confidence: routeDecision.confidence,
          classification: routeDecision.classification,
        })

        if (
          governance.action === 'exclude' ||
          routeDecision.classification.intentClass === 'MISMATCH' ||
          routeDecision.classification.intentClass === 'RISK_POLICY'
        ) {
          return null
        }

        const recommendedTier =
          governance.recommendedTier ?? fallbackTierFromIntent(routeDecision.classification.intentClass)

        return buildSearchBuildoutSuggestion({
          searchTerm: term.search_term,
          intentClass: routeDecision.classification.intentClass,
          recommendedTier,
          confidence: Math.max(governance.confidence, routeDecision.confidence),
          reasonCodes: [...governance.reasonCodes, 'query_mining_buildout_candidate'],
        })
      })
      .filter((item): item is ReturnType<typeof buildSearchBuildoutSuggestion> => item !== null)

    const buildoutBriefs = summarizeSearchBuildoutClusters(suggestions, limit)
    return NextResponse.json({
      generated_at: new Date().toISOString(),
      source: 'computed',
      date_window: termsResult.date_window,
      brief_count: buildoutBriefs.length,
      buildout_briefs: buildoutBriefs,
      warnings,
    })
  } catch (error) {
    console.error('Search buildout recommendation generation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error', warnings },
      { status: 500 }
    )
  }
}
