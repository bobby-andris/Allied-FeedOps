import { describe, expect, it } from 'vitest'
import { computeDecompositionArtifact } from '@/lib/optimization/decomposition/engine'
import { buildNeedsDecisionExplainability } from '@/lib/shopping-funnel/explainability'
import type { SearchTermSourceAssignment } from '@/lib/shopping-funnel/types'

function createAssignment(overrides: Partial<SearchTermSourceAssignment> = {}): SearchTermSourceAssignment {
  return {
    custom_label_0: 'Soap Dishes & Holders',
    source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
    source_tier: 'HIGH',
    impressions: 120,
    clicks: 16,
    cost_micros: 2_400_000,
    conversions: 2,
    conversions_value: 390,
    ...overrides,
  }
}

describe('buildNeedsDecisionExplainability', () => {
  it('maps decomposition artifact reason codes, confidence components, and diagnostics', () => {
    const assignment = createAssignment()
    const artifact = computeDecompositionArtifact({
      searchTerm: 'soap dishes for shower',
      customLabel0: assignment.custom_label_0,
      assignment,
      labelCount: 2,
    })

    const explainability = buildNeedsDecisionExplainability({
      artifact,
      primaryCustomLabel0: assignment.custom_label_0,
    })

    expect(explainability.primary_custom_label_0).toBe('Soap Dishes & Holders')
    expect(explainability.reason_codes).toEqual(expect.arrayContaining(['performance_weighted_tiering']))
    expect(explainability.intent_confidence_components).toBeDefined()
    expect(explainability.recommendation_confidence_components).toMatchObject({
      final: artifact.recommendation.confidence,
    })
    expect(explainability.diagnostics?.normalized_search_term).toBe('soap dishes for shower')
    expect(explainability.diagnostics?.use_case_tokens).toEqual(expect.arrayContaining(['shower']))
  })
})
