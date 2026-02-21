import { describe, expect, it } from 'vitest'
import {
  sanitizeTermMetrics,
  validateDecisionInput,
  validateBidPolicyInput,
} from '@/lib/intent/input-validation'
import type { TermMetrics, IntentDecisionInput, BidPolicyInput } from '@/lib/intent/types'

describe('sanitizeTermMetrics', () => {
  it('passes through valid metrics unchanged', () => {
    const metrics: TermMetrics = {
      impressions: 1000,
      clicks: 100,
      conversions: 5,
      conversionsValue: 800,
      costMicros: 200000000,
    }
    const result = sanitizeTermMetrics(metrics)
    expect(result.value).toEqual(metrics)
    expect(result.warnings).toHaveLength(0)
  })

  it('clamps negative values to zero with warnings', () => {
    const metrics: TermMetrics = {
      impressions: -10,
      clicks: 50,
      conversions: -1,
      conversionsValue: 200,
      costMicros: 100000000,
    }
    const result = sanitizeTermMetrics(metrics)
    expect(result.value.impressions).toBe(0)
    expect(result.value.conversions).toBe(0)
    expect(result.value.clicks).toBe(50)
    expect(result.warnings.length).toBeGreaterThanOrEqual(2)
  })

  it('replaces NaN with zero and warns', () => {
    const metrics: TermMetrics = {
      impressions: NaN,
      clicks: 100,
      conversions: 5,
      conversionsValue: NaN,
      costMicros: 200000000,
    }
    const result = sanitizeTermMetrics(metrics)
    expect(result.value.impressions).toBe(0)
    expect(result.value.conversionsValue).toBe(0)
    expect(result.warnings.length).toBeGreaterThanOrEqual(2)
  })

  it('replaces Infinity with zero and warns', () => {
    const metrics: TermMetrics = {
      impressions: Infinity,
      clicks: 100,
      conversions: 5,
      conversionsValue: 800,
      costMicros: -Infinity,
    }
    const result = sanitizeTermMetrics(metrics)
    expect(result.value.impressions).toBe(0)
    expect(result.value.costMicros).toBe(0)
    expect(result.warnings.length).toBeGreaterThanOrEqual(2)
  })

  it('floors fractional counts to integers', () => {
    const metrics: TermMetrics = {
      impressions: 100.7,
      clicks: 50.3,
      conversions: 3.9,
      conversionsValue: 800.55,
      costMicros: 200000000.1,
    }
    const result = sanitizeTermMetrics(metrics)
    expect(result.value.impressions).toBe(100)
    expect(result.value.clicks).toBe(50)
    expect(result.value.conversions).toBe(3)
    // conversionsValue and costMicros keep precision (monetary)
    expect(result.value.conversionsValue).toBe(800.55)
    expect(result.value.costMicros).toBe(200000000.1)
  })
})

describe('validateDecisionInput', () => {
  const validInput: IntentDecisionInput = {
    searchTerm: 'brass towel bar 24 inch',
    metrics: {
      impressions: 500,
      clicks: 80,
      conversions: 4,
      conversionsValue: 700,
      costMicros: 160000000,
    },
    attributionQualityScore: 0.85,
    valueSignalScore: 0.7,
  }

  it('passes valid input unchanged', () => {
    const result = validateDecisionInput(validInput)
    expect(result.valid).toBe(true)
    expect(result.value.searchTerm).toBe(validInput.searchTerm)
    expect(result.warnings).toHaveLength(0)
  })

  it('rejects empty search term', () => {
    const result = validateDecisionInput({ ...validInput, searchTerm: '' })
    expect(result.valid).toBe(false)
  })

  it('rejects whitespace-only search term', () => {
    const result = validateDecisionInput({ ...validInput, searchTerm: '   ' })
    expect(result.valid).toBe(false)
  })

  it('clamps attributionQualityScore to 0-1 range', () => {
    const result = validateDecisionInput({
      ...validInput,
      attributionQualityScore: 1.5,
    })
    expect(result.valid).toBe(true)
    expect(result.value.attributionQualityScore).toBe(1)
    expect(result.warnings.length).toBeGreaterThanOrEqual(1)
  })

  it('clamps negative attributionQualityScore to 0', () => {
    const result = validateDecisionInput({
      ...validInput,
      attributionQualityScore: -0.3,
    })
    expect(result.valid).toBe(true)
    expect(result.value.attributionQualityScore).toBe(0)
  })

  it('clamps valueSignalScore to 0-1 range', () => {
    const result = validateDecisionInput({
      ...validInput,
      valueSignalScore: 2,
    })
    expect(result.valid).toBe(true)
    expect(result.value.valueSignalScore).toBe(1)
  })

  it('sanitizes metrics within the input', () => {
    const result = validateDecisionInput({
      ...validInput,
      metrics: { ...validInput.metrics, clicks: -5 },
    })
    expect(result.valid).toBe(true)
    expect(result.value.metrics.clicks).toBe(0)
    expect(result.warnings.length).toBeGreaterThanOrEqual(1)
  })
})

describe('validateBidPolicyInput', () => {
  const validInput: BidPolicyInput = {
    key: 'Towel Bars|high',
    channel: 'shopping',
    intentClass: 'PRODUCT_HIGH',
    targetMode: 'roas',
    currentTargetRoas: 3.6,
    observedRoas: 4.1,
    confidence: 0.8,
    attributionQualityScore: 0.9,
    valueSignalScore: 0.75,
  }

  it('passes valid input unchanged', () => {
    const result = validateBidPolicyInput(validInput)
    expect(result.valid).toBe(true)
    expect(result.warnings).toHaveLength(0)
  })

  it('rejects empty key', () => {
    const result = validateBidPolicyInput({ ...validInput, key: '' })
    expect(result.valid).toBe(false)
  })

  it('clamps confidence to 0-1', () => {
    const result = validateBidPolicyInput({ ...validInput, confidence: 1.5 })
    expect(result.valid).toBe(true)
    expect(result.value.confidence).toBe(1)
  })

  it('clamps negative ROAS values to 0', () => {
    const result = validateBidPolicyInput({
      ...validInput,
      currentTargetRoas: -2,
      observedRoas: -1,
    })
    expect(result.valid).toBe(true)
    expect(result.value.currentTargetRoas).toBe(0)
    expect(result.value.observedRoas).toBe(0)
  })

  it('clamps negative CPA values to 0', () => {
    const result = validateBidPolicyInput({
      ...validInput,
      targetMode: 'cpa',
      currentTargetCpa: -10,
      observedCpa: -5,
    })
    expect(result.valid).toBe(true)
    expect(result.value.currentTargetCpa).toBe(0)
    expect(result.value.observedCpa).toBe(0)
  })

  it('replaces NaN scores with undefined', () => {
    const result = validateBidPolicyInput({
      ...validInput,
      attributionQualityScore: NaN,
      valueSignalScore: NaN,
    })
    expect(result.valid).toBe(true)
    expect(result.value.attributionQualityScore).toBeUndefined()
    expect(result.value.valueSignalScore).toBeUndefined()
  })
})
