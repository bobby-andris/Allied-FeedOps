/**
 * Reason Code Classification — Categorizes scored terms into leakage types
 *
 * Three categories:
 *   - misplaced: tier mismatch (default)
 *   - wasted_spend: zero conversions with meaningful spend (LEAK-03)
 *   - under_invested: keyword data shows impression gap > 2x (LEAK-04)
 *
 * Priority: wasted_spend > under_invested > misplaced
 */

import type { TermScore } from '@/lib/optimization/tier-scoring.types'

export type ReasonCode = 'misplaced' | 'wasted_spend' | 'under_invested'

export interface KeywordData {
  avgMonthlySearches: number
}

export interface ClassifiedTerm extends TermScore {
  reasonCode: ReasonCode
  reasonLabel: string
}

// Wasted spend classification now driven by the trigger from determineAction()
// which uses the calibrated 1.5x avgCPA threshold ($96.33).
// Fallback: $5 minimum for legacy paths that don't have trigger data.
const WASTED_SPEND_FALLBACK_MICROS = 5_000_000

// Under-invested: market volume must be 2x+ actual impressions
const UNDER_INVESTED_MULTIPLIER = 2

/**
 * Classify a scored term into a leakage reason category.
 * Priority: wasted_spend > under_invested > misplaced
 */
export function classifyLeakageReason(
  term: TermScore,
  keywordData?: KeywordData
): ReasonCode {
  // Use the trigger from determineAction() as source of truth for wasted spend.
  // This uses the calibrated 1.5x avgCPA threshold instead of hardcoded $5.
  if (term.trigger === 'wasted_spend') {
    return 'wasted_spend'
  }
  // Fallback for terms without trigger data (legacy paths)
  if (!term.trigger && term.totalConversions === 0 && term.totalCostMicros > WASTED_SPEND_FALLBACK_MICROS) {
    return 'wasted_spend'
  }

  // Under-invested: high-converting term stuck in a restricted tier
  // In the waterfall, under-invested terms should move DOWN toward LOW (aggressive bidding).
  // direction === 'downward' means moving toward LOW (deeper in funnel = more aggressive).
  if (keywordData?.avgMonthlySearches && term.impact) {
    if (
      term.impact.direction === 'downward' &&
      keywordData.avgMonthlySearches > UNDER_INVESTED_MULTIPLIER * (term.totalImpressions ?? 0)
    ) {
      return 'under_invested'
    }
  }

  // Default: tier mismatch
  return 'misplaced'
}

export const REASON_LABELS: Record<ReasonCode, string> = {
  misplaced: 'Misplaced',
  wasted_spend: 'Wasted $',
  under_invested: 'Under-invested',
}

export const REASON_COLORS: Record<ReasonCode, string> = {
  misplaced: 'bg-amber-100 text-amber-800 border-amber-200',
  wasted_spend: 'bg-red-100 text-red-800 border-red-200',
  under_invested: 'bg-blue-100 text-blue-800 border-blue-200',
}

/**
 * Classify all misplaced terms and sort by impact (descending).
 */
export function classifyAllTerms(
  terms: TermScore[],
  keywordDataMap?: Map<string, KeywordData>
): ClassifiedTerm[] {
  // Include terms that are misplaced OR have an actionable trigger from determineAction()
  const actionableTriggers = ['wasted_spend', 'demote_underperform', 'promote_conversion', 'promote_intent', 'under_invested']
  return terms
    .filter(t => t.isMisplaced || (t.trigger && actionableTriggers.includes(t.trigger)))
    .map(t => {
      const reasonCode = classifyLeakageReason(t, keywordDataMap?.get(t.searchTerm))
      return {
        ...t,
        reasonCode,
        reasonLabel: REASON_LABELS[reasonCode],
      }
    })
    .sort((a, b) => (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0))
}
