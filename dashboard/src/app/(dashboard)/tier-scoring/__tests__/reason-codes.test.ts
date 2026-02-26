import { describe, it, expect } from 'vitest'
import {
  classifyLeakageReason,
  classifyAllTerms,
  REASON_LABELS,
  REASON_COLORS,
} from '../lib/reason-codes'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { KeywordData } from '../lib/reason-codes'

// ---------------------------------------------------------------------------
// Test helper: minimal valid TermScore mock
// ---------------------------------------------------------------------------

function makeTermScore(overrides: Partial<TermScore> = {}): TermScore {
  return {
    searchTerm: 'brass towel bar',
    customLabel0: 'Towel Bar',
    currentTier: 'LOW',
    recommendedTier: 'MEDIUM',
    isMisplaced: true,
    tierFitScores: { HIGH: 0.1, MEDIUM: 0.8, LOW: 0.3 },
    fitScoreDelta: 0.5,
    dataConfirmed: false,
    confidence: {
      score: 0.75,
      level: 'High',
      factors: { dataVolume: 0.8, consistency: 0.7, significance: 0.6, intentAlignment: 0.9 },
    },
    impact: { low: 50, mid: 120, high: 200, currency: 'USD', period: 'monthly', direction: 'upward' },
    fallbackLevel: 'per_group',
    totalConversions: 5,
    totalCostMicros: 3_000_000,
    verdict: 'test verdict',
    peerContext: 'ranks in top 15% of Towel Bar terms',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// classifyLeakageReason
// ---------------------------------------------------------------------------

describe('classifyLeakageReason', () => {
  it('returns wasted_spend for zero conversions with meaningful spend', () => {
    const term = makeTermScore({
      totalConversions: 0,
      totalCostMicros: 10_000_000, // $10 > $5 threshold
    })
    expect(classifyLeakageReason(term)).toBe('wasted_spend')
  })

  it('returns under_invested when keyword data shows search gap and direction is upward', () => {
    const term = makeTermScore({
      totalConversions: 5,
      totalCostMicros: 3_000_000,
      impact: { low: 50, mid: 120, high: 200, currency: 'USD', period: 'monthly', direction: 'upward' },
    })
    const keywordData: KeywordData = { avgMonthlySearches: 5000 }
    expect(classifyLeakageReason(term, keywordData)).toBe('under_invested')
  })

  it('returns misplaced as default for non-zero conversions and no keyword data', () => {
    const term = makeTermScore({
      totalConversions: 3,
      totalCostMicros: 2_000_000,
    })
    expect(classifyLeakageReason(term)).toBe('misplaced')
  })

  it('wasted_spend takes priority over under_invested', () => {
    const term = makeTermScore({
      totalConversions: 0,
      totalCostMicros: 8_000_000, // > $5 threshold
      impact: { low: 50, mid: 120, high: 200, currency: 'USD', period: 'monthly', direction: 'upward' },
    })
    const keywordData: KeywordData = { avgMonthlySearches: 10000 }
    expect(classifyLeakageReason(term, keywordData)).toBe('wasted_spend')
  })

  it('returns misplaced for zero conversions with zero cost (no money actually wasted)', () => {
    const term = makeTermScore({
      totalConversions: 0,
      totalCostMicros: 0,
    })
    expect(classifyLeakageReason(term)).toBe('misplaced')
  })

  it('returns misplaced for zero conversions with cost below threshold', () => {
    const term = makeTermScore({
      totalConversions: 0,
      totalCostMicros: 4_000_000, // $4 < $5 threshold
    })
    expect(classifyLeakageReason(term)).toBe('misplaced')
  })

  it('returns misplaced when keyword data exists but direction is downward', () => {
    const term = makeTermScore({
      totalConversions: 5,
      totalCostMicros: 3_000_000,
      impact: { low: 50, mid: 120, high: 200, currency: 'USD', period: 'monthly', direction: 'downward' },
    })
    const keywordData: KeywordData = { avgMonthlySearches: 5000 }
    expect(classifyLeakageReason(term, keywordData)).toBe('misplaced')
  })
})

// ---------------------------------------------------------------------------
// classifyAllTerms
// ---------------------------------------------------------------------------

describe('classifyAllTerms', () => {
  it('sorts classified terms by impact.mid descending', () => {
    const terms = [
      makeTermScore({ searchTerm: 'low-impact', impact: { low: 10, mid: 30, high: 50, currency: 'USD', period: 'monthly', direction: 'upward' } }),
      makeTermScore({ searchTerm: 'high-impact', impact: { low: 100, mid: 500, high: 800, currency: 'USD', period: 'monthly', direction: 'upward' } }),
      makeTermScore({ searchTerm: 'mid-impact', impact: { low: 50, mid: 200, high: 350, currency: 'USD', period: 'monthly', direction: 'upward' } }),
    ]
    const result = classifyAllTerms(terms)
    expect(result.map(t => t.searchTerm)).toEqual(['high-impact', 'mid-impact', 'low-impact'])
  })

  it('filters to misplaced terms only', () => {
    const terms = [
      makeTermScore({ searchTerm: 'misplaced-one', isMisplaced: true }),
      makeTermScore({ searchTerm: 'well-placed', isMisplaced: false }),
      makeTermScore({ searchTerm: 'misplaced-two', isMisplaced: true }),
    ]
    const result = classifyAllTerms(terms)
    expect(result).toHaveLength(2)
    expect(result.map(t => t.searchTerm)).not.toContain('well-placed')
  })

  it('attaches reasonCode and reasonLabel to each term', () => {
    const terms = [makeTermScore({ isMisplaced: true })]
    const result = classifyAllTerms(terms)
    expect(result[0].reasonCode).toBe('misplaced')
    expect(result[0].reasonLabel).toBe('Misplaced')
  })

  it('uses keywordDataMap for under_invested classification', () => {
    const terms = [
      makeTermScore({
        searchTerm: 'under-invested-term',
        isMisplaced: true,
        totalConversions: 5,
        totalCostMicros: 3_000_000,
        impact: { low: 50, mid: 120, high: 200, currency: 'USD', period: 'monthly', direction: 'upward' },
      }),
    ]
    const kwMap = new Map<string, KeywordData>([
      ['under-invested-term', { avgMonthlySearches: 10000 }],
    ])
    const result = classifyAllTerms(terms, kwMap)
    expect(result[0].reasonCode).toBe('under_invested')
    expect(result[0].reasonLabel).toBe('Under-invested')
  })
})

// ---------------------------------------------------------------------------
// REASON_LABELS & REASON_COLORS
// ---------------------------------------------------------------------------

describe('REASON_LABELS', () => {
  it('maps each code to expected label', () => {
    expect(REASON_LABELS.misplaced).toBe('Misplaced')
    expect(REASON_LABELS.wasted_spend).toBe('Wasted $')
    expect(REASON_LABELS.under_invested).toBe('Under-invested')
  })
})

describe('REASON_COLORS', () => {
  it('maps each code to a non-empty class string', () => {
    expect(REASON_COLORS.misplaced).toBeTruthy()
    expect(REASON_COLORS.misplaced.length).toBeGreaterThan(0)
    expect(REASON_COLORS.wasted_spend).toBeTruthy()
    expect(REASON_COLORS.wasted_spend.length).toBeGreaterThan(0)
    expect(REASON_COLORS.under_invested).toBeTruthy()
    expect(REASON_COLORS.under_invested.length).toBeGreaterThan(0)
  })

  it('contains expected color prefixes', () => {
    expect(REASON_COLORS.misplaced).toContain('bg-amber')
    expect(REASON_COLORS.wasted_spend).toContain('bg-red')
    expect(REASON_COLORS.under_invested).toContain('bg-blue')
  })
})
