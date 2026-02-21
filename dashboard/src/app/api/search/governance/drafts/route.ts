import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { evaluateShoppingToSearchGraduation, routeIntentDecision } from '@/lib/intent/policy'
import {
  buildSearchBuildoutSuggestion,
  summarizeSearchBuildoutClusters,
} from '@/lib/intent/buildout-intelligence'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

function sanitizeLimit(input: string | null, fallback = 400, max = 5000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json().catch(() => ({}))) as {
      range?: string
      start_date?: string
      end_date?: string
      custom_label_0?: string | null
      min_impressions?: number
      limit?: number
      created_by?: string
      attribution_quality_score?: number
    }

    const range = body.range ?? null
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(body.start_date ?? null) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(body.end_date ?? null) ?? fallbackWindow.endDate
    const customLabel0 = sanitizeCustomLabel(body.custom_label_0 ?? null)
    const minImpressions = sanitizeMinImpressions(
      body.min_impressions == null ? null : String(body.min_impressions)
    )
    const limit = sanitizeLimit(body.limit == null ? null : String(body.limit))

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const evaluated = termsResult.terms.map((term) => {
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
        attributionQualityScore: body.attribution_quality_score,
        existingTerm: term,
      })

      const graduation = evaluateShoppingToSearchGraduation({
        searchTerm: term.search_term,
        classification: routeDecision.classification,
        metrics,
        confidence: routeDecision.confidence,
        alreadyCoveredInSearch: false,
        attributionQualityScore: body.attribution_quality_score,
      })

      return {
        search_term: term.search_term,
        custom_label_0: term.custom_label_0s[0]?.custom_label_0 ?? null,
        metrics,
        routeDecision,
        graduation,
      }
    })

    const eligible = evaluated.filter(
      (item) => item.graduation.eligible && item.graduation.suggestedTier !== null
    )

    const buildoutSuggestions = eligible.map((item) =>
      buildSearchBuildoutSuggestion({
        searchTerm: item.search_term,
        intentClass: item.routeDecision.classification.intentClass,
        recommendedTier: item.graduation.suggestedTier ?? 'phrase',
        confidence: item.graduation.confidence,
        reasonCodes: item.graduation.reasonCodes,
      })
    )
    const buildoutSuggestionByTerm = new Map(
      buildoutSuggestions.map((suggestion) => [suggestion.top_term, suggestion])
    )
    const buildoutBriefs = summarizeSearchBuildoutClusters(buildoutSuggestions)

    const supabase = createAdminClient()
    let existingTerms = new Set<string>()
    if (eligible.length > 0) {
      try {
        const { data, error } = await supabase
          .from('search_buildout_recommendations')
          .select('search_term')
          .in(
            'search_term',
            eligible.map((item) => item.search_term)
          )
          .in('status', ['candidate', 'approved', 'applied'])

        if (error) throw error
        existingTerms = new Set((data ?? []).map((row) => row.search_term as string))
      } catch (error) {
        if (isMissingRelationError(error, 'search_buildout_recommendations')) {
          warnings.push(
            'Table "search_buildout_recommendations" is missing. Draft candidates were generated but not persisted.'
          )
        } else {
          warnings.push(`Unable to deduplicate draft candidates: ${extractErrorMessage(error)}`)
        }
      }
    }

    const draftRows = eligible
      .filter((item) => !existingTerms.has(item.search_term))
      .map((item) => ({
        search_term: item.search_term,
        custom_label_0: item.custom_label_0,
        recommended_search_tier: item.graduation.suggestedTier,
        status: 'candidate',
        confidence: item.graduation.confidence,
        metadata: {
          source: 'shopping_to_search_graduation',
          intent_class: item.routeDecision.classification.intentClass,
          route_action: item.routeDecision.routeAction,
          reason_codes: item.graduation.reasonCodes,
          current_tier: 'broad',
          buildout: buildoutSuggestionByTerm.get(item.search_term),
        },
      }))

    const decisionRows = eligible.map((item) => ({
      search_term: item.search_term,
      custom_label_0: item.custom_label_0,
      decision_type: 'shopping_to_search_graduation',
      channel: 'cross_channel',
      policy_version: item.graduation.policyVersion,
      decision_payload: {
        suggested_tier: item.graduation.suggestedTier,
        eligible: item.graduation.eligible,
        reason_codes: item.graduation.reasonCodes,
      },
      confidence: item.graduation.confidence,
      requires_review: item.graduation.requiresReview,
      created_by: body.created_by ?? null,
    }))

    const recommendationInsert = await insertRowsSafe(
      supabase,
      'search_buildout_recommendations',
      draftRows
    )
    if (recommendationInsert.warning) warnings.push(recommendationInsert.warning)

    const decisionInsert = await insertRowsSafe(supabase, 'policy_decision_log', decisionRows)
    if (decisionInsert.warning) warnings.push(decisionInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      evaluated_count: evaluated.length,
      eligible_count: eligible.length,
      drafted_count: draftRows.length,
      skipped_existing_count: eligible.length - draftRows.length,
      buildout_brief_count: buildoutBriefs.length,
      buildout_briefs: buildoutBriefs,
      persisted: {
        search_buildout_recommendations: recommendationInsert.inserted,
        policy_decision_log: decisionInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Search governance draft generation failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error), warnings },
      { status: 500 }
    )
  }
}
