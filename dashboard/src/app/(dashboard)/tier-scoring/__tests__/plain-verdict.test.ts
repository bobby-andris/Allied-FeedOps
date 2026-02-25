import { describe, it, expect } from 'vitest'
import { generatePlainVerdict, generateShortVerdict } from '../lib/plain-verdict'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'

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
    verdict: 'original verdict',
    peerContext: 'ranks in top 15% of Towel Bar terms',
    ...overrides,
  }
}

describe('generatePlainVerdict', () => {
  it('returns data-confirmed message for well-placed terms with data confirmation', () => {
    const term = makeTermScore({ isMisplaced: false, dataConfirmed: true, currentTier: 'HIGH' })
    const result = generatePlainVerdict(term)
    expect(result).toContain('Performing well')
    expect(result).toContain('premium')
    expect(result).toContain('data confirms')
  })

  it('returns aligned message for well-placed terms without data confirmation', () => {
    const term = makeTermScore({ isMisplaced: false, dataConfirmed: false, currentTier: 'MEDIUM' })
    const result = generatePlainVerdict(term)
    expect(result).toContain('correctly placed')
    expect(result).toContain('mid-tier')
  })

  it('returns outperforming message for upward movements', () => {
    const term = makeTermScore({
      isMisplaced: true,
      currentTier: 'LOW',
      recommendedTier: 'MEDIUM',
    })
    const result = generatePlainVerdict(term)
    expect(result).toContain('outperforming')
    expect(result).toContain('budget')
    expect(result).toContain('mid-tier')
    expect(result).toContain('$50-$200/mo')
  })

  it('returns underperforming message for downward movements', () => {
    const term = makeTermScore({
      isMisplaced: true,
      currentTier: 'HIGH',
      recommendedTier: 'LOW',
      impact: { low: 100, mid: 250, high: 400, currency: 'USD', period: 'monthly', direction: 'downward' },
    })
    const result = generatePlainVerdict(term)
    expect(result).toContain('underperforming')
    expect(result).toContain('premium')
    expect(result).toContain('budget')
  })

  it('handles null impact gracefully', () => {
    const term = makeTermScore({ isMisplaced: true, impact: null })
    const result = generatePlainVerdict(term)
    expect(result).not.toContain('undefined')
    expect(result).not.toContain('null')
    expect(result).toContain('outperforming')
  })

  it('formats large dollar amounts with K suffix', () => {
    const term = makeTermScore({
      isMisplaced: true,
      impact: { low: 1200, mid: 2500, high: 4000, currency: 'USD', period: 'monthly', direction: 'upward' },
    })
    const result = generatePlainVerdict(term)
    expect(result).toContain('$1.2K')
    expect(result).toContain('$4.0K')
  })
})

describe('generateShortVerdict', () => {
  it('returns short message for data-confirmed terms', () => {
    const term = makeTermScore({ isMisplaced: false, dataConfirmed: true })
    expect(generateShortVerdict(term)).toBe('Data-confirmed placement')
  })

  it('returns short message for aligned terms', () => {
    const term = makeTermScore({ isMisplaced: false, dataConfirmed: false })
    expect(generateShortVerdict(term)).toBe('Aligned with current tier')
  })

  it('includes recommended tier for upward movement', () => {
    const term = makeTermScore({ isMisplaced: true, currentTier: 'LOW', recommendedTier: 'MEDIUM' })
    const result = generateShortVerdict(term)
    expect(result).toContain('Outperforming')
    expect(result).toContain('MEDIUM')
  })

  it('includes recommended tier for downward movement', () => {
    const term = makeTermScore({ isMisplaced: true, currentTier: 'HIGH', recommendedTier: 'LOW' })
    const result = generateShortVerdict(term)
    expect(result).toContain('Underperforming')
    expect(result).toContain('LOW')
  })
})
