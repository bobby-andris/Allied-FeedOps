import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'
import { formatDollars } from '@/lib/formatting'

const tierRank: Record<FunnelTier, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }

const tierLabel: Record<FunnelTier, string> = {
  HIGH: 'premium',
  MEDIUM: 'mid-tier',
  LOW: 'budget',
}

/**
 * Generate a plain English verdict for a term score.
 * Designed for the business owner who has 2 minutes per week.
 * No z-scores, no MAD, no p-values — just what it means and what to do.
 */
export function generatePlainVerdict(term: TermScore): string {
  // Trigger-based verdicts take priority
  if (term.trigger && term.trigger !== 'observe') {
    const target = term.targetTier ?? term.recommendedTier
    const targetName = tierLabel[target]
    switch (term.trigger) {
      case 'wasted_spend':
        return `Wasting money — zero conversions with significant spend. ${target === 'HIGH' ? 'Block or restrict' : 'Demote'} to ${targetName}`
      case 'demote_underperform':
        return `Underperforming in current tier — demote to ${targetName} to restrict bidding`
      case 'promote_conversion':
        return `Converting well — promote to ${targetName} for more aggressive bidding`
      case 'promote_intent':
        return `High intent signal but no conversions yet — promote to ${targetName} to test with aggressive bidding`
      case 'under_invested':
        return `Impression gap detected — increase budget or promote to ${targetName}`
    }
  }

  // Well-placed terms (fallback for terms without triggers)
  if (!term.isMisplaced) {
    if (term.dataConfirmed) {
      return `Performing well in ${tierLabel[term.currentTier]} — data confirms this placement`
    }
    return `Appears correctly placed in ${tierLabel[term.currentTier]}`
  }

  // Misplaced terms — build the sentence in parts (legacy fallback)
  const goingUp = tierRank[term.recommendedTier] > tierRank[term.currentTier]

  const directionPhrase = goingUp
    ? `is outperforming its ${tierLabel[term.currentTier]} placement and could earn more in ${tierLabel[term.recommendedTier]}`
    : `is underperforming for ${tierLabel[term.currentTier]} and may belong in ${tierLabel[term.recommendedTier]}`

  const impactPhrase = term.impact
    ? ` — potential ${formatDollars(term.impact.low)}-${formatDollars(term.impact.high)}/mo improvement`
    : ''

  return `This term ${directionPhrase}${impactPhrase}`
}

/**
 * Generate a short one-line summary for table rows.
 * Max ~60 chars, no dollar amounts.
 */
export function generateShortVerdict(term: TermScore): string {
  // Trigger-based short verdicts take priority
  if (term.trigger && term.trigger !== 'observe') {
    const target = term.targetTier ?? term.recommendedTier
    switch (term.trigger) {
      case 'wasted_spend': return `Wasted spend — ${target}`
      case 'demote_underperform': return `Underperforming — demote to ${target}`
      case 'promote_conversion': return `Converting — promote to ${target}`
      case 'promote_intent': return `High intent — promote to ${target}`
      case 'under_invested': return `Under-invested — ${target}`
    }
  }

  // Fallback for terms without triggers
  if (!term.isMisplaced) {
    return term.dataConfirmed ? 'Data-confirmed placement' : 'Aligned with current tier'
  }

  const goingUp = tierRank[term.recommendedTier] > tierRank[term.currentTier]
  return goingUp
    ? `Outperforming — consider ${term.recommendedTier}`
    : `Underperforming — consider ${term.recommendedTier}`
}
