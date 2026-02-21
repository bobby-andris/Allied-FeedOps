import { describe, expect, it } from 'vitest'
import {
  checkValueConsistency,
  type ValueConsistencyInput,
} from '@/lib/intent/value-consistency'

describe('checkValueConsistency', () => {
  it('returns high consistency when GA4 and Shopify values match closely', () => {
    const input: ValueConsistencyInput = {
      ga4ConversionValue: 1000,
      shopifyOrderValue: 1020,
    }
    const result = checkValueConsistency(input)
    expect(result.consistencyScore).toBeGreaterThanOrEqual(0.9)
    expect(result.divergenceFlag).toBe(false)
    expect(result.severity).toBe('none')
  })

  it('returns moderate consistency for moderate divergence', () => {
    const input: ValueConsistencyInput = {
      ga4ConversionValue: 1000,
      shopifyOrderValue: 1250,
    }
    const result = checkValueConsistency(input)
    expect(result.consistencyScore).toBeGreaterThanOrEqual(0.5)
    expect(result.consistencyScore).toBeLessThan(0.9)
    expect(result.divergenceFlag).toBe(true)
    expect(result.severity).toBe('warning')
  })

  it('flags critical divergence when values differ significantly', () => {
    const input: ValueConsistencyInput = {
      ga4ConversionValue: 1000,
      shopifyOrderValue: 2500,
    }
    const result = checkValueConsistency(input)
    expect(result.consistencyScore).toBeLessThan(0.5)
    expect(result.divergenceFlag).toBe(true)
    expect(result.severity).toBe('critical')
  })

  it('handles zero GA4 value with non-zero Shopify value', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: 0,
      shopifyOrderValue: 500,
    })
    expect(result.consistencyScore).toBe(0)
    expect(result.divergenceFlag).toBe(true)
    expect(result.severity).toBe('critical')
  })

  it('handles zero Shopify value with non-zero GA4 value', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: 500,
      shopifyOrderValue: 0,
    })
    expect(result.consistencyScore).toBe(0)
    expect(result.divergenceFlag).toBe(true)
    expect(result.severity).toBe('critical')
  })

  it('returns perfect consistency when both are zero', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: 0,
      shopifyOrderValue: 0,
    })
    expect(result.consistencyScore).toBe(1)
    expect(result.divergenceFlag).toBe(false)
    expect(result.severity).toBe('none')
  })

  it('handles missing optional fields gracefully', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: 1000,
      shopifyOrderValue: 1050,
    })
    expect(result.consistencyScore).toBeGreaterThanOrEqual(0.9)
  })

  it('includes period context when provided', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: 1000,
      shopifyOrderValue: 1300,
      periodDays: 7,
    })
    expect(result.periodDays).toBe(7)
    expect(result.divergenceFlag).toBe(true)
  })

  it('treats NaN inputs as zero', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: NaN,
      shopifyOrderValue: 500,
    })
    expect(result.consistencyScore).toBe(0)
    expect(result.divergenceFlag).toBe(true)
  })

  it('treats negative inputs as zero', () => {
    const result = checkValueConsistency({
      ga4ConversionValue: -100,
      shopifyOrderValue: 500,
    })
    expect(result.consistencyScore).toBe(0)
    expect(result.divergenceFlag).toBe(true)
  })

  it('is symmetric — order of sources does not matter for score', () => {
    const a = checkValueConsistency({
      ga4ConversionValue: 800,
      shopifyOrderValue: 1000,
    })
    const b = checkValueConsistency({
      ga4ConversionValue: 1000,
      shopifyOrderValue: 800,
    })
    expect(a.consistencyScore).toBeCloseTo(b.consistencyScore, 4)
  })
})
