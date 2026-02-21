import { describe, expect, it } from 'vitest'
import { validateTierMovement } from '@/lib/intent/tier-movement'
import type { TierMovementRequest } from '@/lib/intent/types'

function makeRequest(overrides: Partial<TierMovementRequest> = {}): TierMovementRequest {
  return {
    searchTerm: 'brass towel bar 24 inch',
    customLabel0: 'Towel Bars - Low',
    currentTier: 'low',
    targetTier: 'medium',
    action: 'promote_to_medium',
    confidence: 0.8,
    reasonCodes: ['low_to_medium_threshold_met'],
    policyVersion: 'intent_v1',
    ...overrides,
  }
}

describe('validateTierMovement', () => {
  it('allows valid high-confidence promotion', () => {
    const result = validateTierMovement(makeRequest(), 'go')
    expect(result.valid).toBe(true)
    expect(result.reason).toBeUndefined()
  })

  it('blocks all movements when guardrails are blocked', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.95 }), 'blocked')
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('blocked')
  })

  it('blocks low-confidence movements when guardrails are on hold', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.6 }), 'hold')
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('hold')
  })

  it('allows high-confidence movements when guardrails are on hold', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.8 }), 'hold')
    expect(result.valid).toBe(true)
  })

  it('rejects observe-only confidence below 0.55', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.4 }), 'go')
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('observe-only')
  })

  it('rejects same tier movements', () => {
    const result = validateTierMovement(
      makeRequest({ currentTier: 'medium', targetTier: 'medium' }),
      'go'
    )
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('no movement needed')
  })

  it('rejects hold actions', () => {
    const result = validateTierMovement(makeRequest({ action: 'hold' }), 'go')
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('hold')
  })

  it('allows demotion with sufficient confidence', () => {
    const result = validateTierMovement(
      makeRequest({
        currentTier: 'high',
        targetTier: 'medium',
        action: 'demote_to_medium',
        confidence: 0.75,
      }),
      'go'
    )
    expect(result.valid).toBe(true)
  })

  it('allows negative action with high confidence', () => {
    const result = validateTierMovement(
      makeRequest({
        action: 'negative',
        targetTier: 'campaign_negative',
        confidence: 0.85,
      }),
      'go'
    )
    expect(result.valid).toBe(true)
  })

  it('allows confidence exactly at review threshold', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.55 }), 'go')
    expect(result.valid).toBe(true)
  })

  it('rejects confidence just below review threshold', () => {
    const result = validateTierMovement(makeRequest({ confidence: 0.54 }), 'go')
    expect(result.valid).toBe(false)
  })
})
