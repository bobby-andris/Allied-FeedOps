import { describe, expect, it } from 'vitest'
import {
  evaluateGraduationWithHoldout,
  buildGraduationBatch,
} from '@/lib/intent/graduation'
import type { IntentClassification, TermMetrics } from '@/lib/intent/types'

function makeClassification(intentClass: IntentClassification['intentClass']): IntentClassification {
  return {
    normalizedQuery: 'test query',
    intentClass,
    subclasses: [],
    reasonCodes: ['test'],
    matchedTokens: [],
    isBranded: false,
    isCompetitor: false,
    hasMismatchRisk: false,
  }
}

function makeMetrics(overrides?: Partial<TermMetrics>): TermMetrics {
  return {
    impressions: 500,
    clicks: 150,
    conversions: 8,
    conversionsValue: 2000,
    costMicros: 500_000_000,
    ...overrides,
  }
}

describe('evaluateGraduationWithHoldout', () => {
  it('passes through standard eligible graduation', () => {
    const result = evaluateGraduationWithHoldout({
      searchTerm: 'brass towel bar 24 inch',
      classification: makeClassification('PRODUCT_HIGH'),
      metrics: makeMetrics(),
      confidence: 0.8,
    })

    expect(result.eligible).toBe(true)
    expect(result.holdoutExcluded).toBe(false)
    expect(result.suggestedTier).toBeDefined()
  })

  it('excludes holdout terms with reason code', () => {
    const result = evaluateGraduationWithHoldout({
      searchTerm: 'brass towel bar 24 inch',
      classification: makeClassification('PRODUCT_HIGH'),
      metrics: makeMetrics(),
      confidence: 0.8,
      isHoldout: true,
      experimentKey: 'exp-2026-02',
    })

    expect(result.eligible).toBe(false)
    expect(result.holdoutExcluded).toBe(true)
    expect(result.experimentKey).toBe('exp-2026-02')
    expect(result.reasonCodes).toContain('holdout_experiment_active')
  })

  it('passes through ineligible terms without holdout flag', () => {
    const result = evaluateGraduationWithHoldout({
      searchTerm: 'brass towel bar 24 inch',
      classification: makeClassification('BRAND_CORE'),
      metrics: makeMetrics(),
      confidence: 0.8,
    })

    expect(result.eligible).toBe(false)
    expect(result.holdoutExcluded).toBe(false)
    // Should not have holdout reason — ineligible by base policy
    expect(result.reasonCodes).not.toContain('holdout_experiment_active')
  })

  it('does not holdout-exclude already-ineligible terms', () => {
    const result = evaluateGraduationWithHoldout({
      searchTerm: 'brass towel bar 24 inch',
      classification: makeClassification('MISMATCH'),
      metrics: makeMetrics(),
      confidence: 0.8,
      isHoldout: true,
    })

    expect(result.eligible).toBe(false)
    expect(result.holdoutExcluded).toBe(false)
  })
})

describe('buildGraduationBatch', () => {
  const eligibleTerm = {
    searchTerm: 'brass towel bar 24 inch',
    classification: makeClassification('PRODUCT_HIGH'),
    metrics: makeMetrics(),
    confidence: 0.8,
  }

  const ineligibleTerm = {
    searchTerm: 'bathroom contractor near me',
    classification: makeClassification('MISMATCH'),
    metrics: makeMetrics(),
    confidence: 0.8,
  }

  it('processes a batch and returns correct counts', () => {
    const result = buildGraduationBatch([eligibleTerm, ineligibleTerm])

    expect(result.results).toHaveLength(2)
    expect(result.eligibleCount + result.ineligibleCount + result.holdoutCount).toBe(2)
    expect(result.ineligibleCount).toBeGreaterThanOrEqual(1) // mismatch is always ineligible
  })

  it('assigns holdout when experimentKey is provided', () => {
    // Use a large batch with diverse names to ensure hash distribution
    const termNames = [
      'brass towel bar', 'chrome soap dish', 'nickel robe hook',
      'bronze toilet paper holder', 'gold shower curtain rod',
      'matte black faucet', 'polished towel ring', 'satin nickel shelf',
      'antique brass rail', 'oil rubbed grab bar',
      'venetian bronze hook', 'pewter tissue holder',
      'copper towel warmer', 'stainless steel rack',
      'brushed gold dispenser', 'crystal knob set',
      'porcelain towel stand', 'iron curtain bracket',
      'aluminum shower caddy', 'zinc alloy handle',
    ]
    const terms = termNames.map((name) => ({
      ...eligibleTerm,
      searchTerm: name,
    }))

    const result = buildGraduationBatch(terms, 'exp-test', 0.5)

    expect(result.experimentKey).toBe('exp-test')
    // With 50% holdout rate and 20 terms, we should have some in holdout
    expect(result.holdoutCount).toBeGreaterThan(0)
    expect(result.eligibleCount).toBeGreaterThan(0)
    expect(result.holdoutCount + result.eligibleCount + result.ineligibleCount).toBe(20)
  })

  it('does not assign holdout when no experimentKey', () => {
    const result = buildGraduationBatch([eligibleTerm])

    expect(result.holdoutCount).toBe(0)
    expect(result.eligibleCount).toBe(1)
  })

  it('respects explicit isHoldout on individual terms', () => {
    const holdoutTerm = {
      ...eligibleTerm,
      searchTerm: 'explicitly held out term',
      isHoldout: true,
    }
    const result = buildGraduationBatch([holdoutTerm])

    expect(result.holdoutCount).toBe(1)
    expect(result.eligibleCount).toBe(0)
  })

  it('handles empty batch', () => {
    const result = buildGraduationBatch([])

    expect(result.results).toHaveLength(0)
    expect(result.eligibleCount).toBe(0)
    expect(result.holdoutCount).toBe(0)
    expect(result.ineligibleCount).toBe(0)
  })
})
