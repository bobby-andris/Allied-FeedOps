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
// which uses the term-level threshold ($15 = 2x median converting term spend).
// Fallback uses same threshold for legacy paths without trigger data.
const WASTED_SPEND_FALLBACK_MICROS = 15_000_000

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

// ── Action Queue Grouping ──────────────────────────────────────────

export type ActionGroup = 'stop_wasting' | 'restrict_bidding' | 'bid_aggressive'

export interface ActionGroupData {
  key: ActionGroup
  label: string
  terms: ClassifiedTerm[]
  totalImpact: { low: number; mid: number; high: number }
  highConfidenceCount: number
}

const TRIGGER_TO_GROUP: Record<string, ActionGroup> = {
  wasted_spend: 'stop_wasting',
  demote_underperform: 'restrict_bidding',
  promote_conversion: 'bid_aggressive',
  promote_intent: 'bid_aggressive',
  under_invested: 'bid_aggressive',
}

const GROUP_ORDER: ActionGroup[] = ['stop_wasting', 'restrict_bidding', 'bid_aggressive']

const GROUP_LABELS: Record<ActionGroup, string> = {
  stop_wasting: 'Stop Wasting Money',
  restrict_bidding: 'Restrict Bidding',
  bid_aggressive: 'Bid More Aggressively',
}

export function groupActionableTerms(terms: ClassifiedTerm[]): ActionGroupData[] {
  const grouped = new Map<ActionGroup, ClassifiedTerm[]>()
  for (const g of GROUP_ORDER) grouped.set(g, [])

  for (const term of terms) {
    const group = TRIGGER_TO_GROUP[term.trigger ?? '']
    if (group) grouped.get(group)!.push(term)
  }

  return GROUP_ORDER.map(key => {
    const groupTerms = grouped.get(key)!
    // Sort: impact.mid desc, then confidence.score desc
    groupTerms.sort((a, b) => {
      const impactDiff = (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0)
      if (impactDiff !== 0) return impactDiff
      return b.confidence.score - a.confidence.score
    })

    const totalImpact = groupTerms.reduce(
      (acc, t) => ({
        low: acc.low + (t.impact?.low ?? 0),
        mid: acc.mid + (t.impact?.mid ?? 0),
        high: acc.high + (t.impact?.high ?? 0),
      }),
      { low: 0, mid: 0, high: 0 }
    )

    return {
      key,
      label: GROUP_LABELS[key],
      terms: groupTerms,
      totalImpact,
      highConfidenceCount: groupTerms.filter(t => t.confidence.score > 0.80).length,
    }
  }).filter(g => g.terms.length > 0)
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
