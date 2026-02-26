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

// Wasted spend threshold: $5 in cost_micros (5,000,000 micros = $5)
const WASTED_SPEND_THRESHOLD_MICROS = 5_000_000

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
  // Check for wasted spend: zero conversions with meaningful spend
  if (term.totalConversions === 0 && term.totalCostMicros > WASTED_SPEND_THRESHOLD_MICROS) {
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
  return terms
    .filter(t => t.isMisplaced)
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
