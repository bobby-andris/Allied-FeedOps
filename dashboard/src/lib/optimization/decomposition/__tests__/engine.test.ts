import { describe, expect, it } from 'vitest'
import {
  computeDecompositionArtifact,
  decomposeSearchTermIntent,
  recommendActionForPair,
} from '@/lib/optimization/decomposition/engine'
import type { SearchTermSourceAssignment } from '@/lib/shopping-funnel/types'

function createAssignment(overrides: Partial<SearchTermSourceAssignment> = {}): SearchTermSourceAssignment {
  return {
    custom_label_0: 'Wall Mounted Towel Bars',
    source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - HIGH',
    source_tier: 'HIGH',
    impressions: 100,
    clicks: 10,
    cost_micros: 2_000_000,
    conversions: 1,
    conversions_value: 250,
    ...overrides,
  }
}

describe('decomposition engine', () => {
  it('prioritizes branded intent over other actions', () => {
    const assignment = createAssignment()
    const { intent } = decomposeSearchTermIntent('allied brass towel bar')
    const recommendation = recommendActionForPair('allied brass towel bar', assignment, 1, intent)

    expect(intent.is_branded).toBe(true)
    expect(recommendation.action_type).toBe('branded')
    expect(recommendation.confidence).toBe(0.96)
  })

  it('prioritizes competitor action over mismatch risk when both are present', () => {
    const assignment = createAssignment()
    const { intent } = decomposeSearchTermIntent('moen cheap towel ring')
    const recommendation = recommendActionForPair('moen cheap towel ring', assignment, 1, intent)

    expect(intent.is_competitor).toBe(true)
    expect(intent.has_mismatch_risk).toBe(true)
    expect(recommendation.action_type).toBe('competitor')
    expect(recommendation.confidence).toBe(0.9)
  })

  it('flags mismatch risk when negative risk tokens are present', () => {
    const assignment = createAssignment()
    const { intent } = decomposeSearchTermIntent('used replacement part for soap dispenser')
    const recommendation = recommendActionForPair(
      'used replacement part for soap dispenser',
      assignment,
      1,
      intent
    )

    expect(intent.has_mismatch_risk).toBe(true)
    expect(recommendation.action_type).toBe('global_block')
    expect(recommendation.reason_codes).toContain('negative_risk_token_detected')
  })

  it('records ambiguity diagnostics when multiple product objects are detected', () => {
    const artifact = computeDecompositionArtifact({
      searchTerm: 'glass shelf towel bar polished brass',
      customLabel0: 'Single Glass Shelf',
      assignment: createAssignment({ custom_label_0: 'Single Glass Shelf' }),
      labelCount: 2,
    })

    expect(artifact.intent.product_object).toBe('towel bar')
    expect(artifact.diagnostics.matched_tokens.product_object_candidates).toEqual(
      expect.arrayContaining(['towel bar', 'glass shelf', 'shelf'])
    )
    expect(artifact.diagnostics.ambiguity_flags.multiple_product_objects).toBe(true)
    expect(artifact.diagnostics.confidence_components.final).toBeCloseTo(0.5, 4)
  })

  it('applies deterministic funnel confidence formula', () => {
    const artifact = computeDecompositionArtifact({
      searchTerm: 'wall mounted towel bar matte black',
      customLabel0: 'Wall Mounted Towel Bars',
      assignment: createAssignment({ clicks: 80, conversions: 7, impressions: 700, conversions_value: 1450 }),
      labelCount: 3,
    })

    // 0.55 + (80/2000) + (7/100) + (3*0.03) = 0.75
    expect(artifact.recommendation.action_type).toBe('funnel')
    expect(artifact.recommendation.confidence).toBeCloseTo(0.75, 4)
  })
})
