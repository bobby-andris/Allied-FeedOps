import { describe, expect, it } from 'vitest'
import type { NeedsDecisionTerm } from '@/lib/shopping-funnel/types'
import {
  buildDecisionItem,
  createDecisionSignature,
  getDecisionCompletion,
  type NeedsDecisionStateLike,
} from '@/lib/shopping-funnel/decision-staging'

function makeTerm(customLabels: string[]): NeedsDecisionTerm {
  return {
    search_term: 'soap dishes for shower',
    custom_label_0s: customLabels.map((label, index) => ({
      custom_label_0: label,
      source_campaign: `AVD - Shopping - US - ${label} - HIGH`,
      source_tier: 'HIGH',
      impressions: 10 + index,
      clicks: 1,
      cost_micros: 1000000,
      conversions: 0,
      conversions_value: 0,
    })),
  }
}

describe('shopping-funnel decision staging helpers', () => {
  it('marks funnel decisions incomplete until all custom_label_0 assignments are set', () => {
    const term = makeTerm(['soap dishes & holders', 'baskets'])
    const state: NeedsDecisionStateLike = {
      actionType: 'funnel',
      assignments: {
        'soap dishes & holders': 'high',
      },
    }

    const completion = getDecisionCompletion(term, state)
    expect(completion.complete).toBe(false)
    expect(completion.selectedCount).toBe(1)
    expect(completion.requiredCount).toBe(2)
  })

  it('marks non-funnel decisions complete without assignment requirements', () => {
    const term = makeTerm(['soap dishes & holders', 'baskets'])
    const state: NeedsDecisionStateLike = {
      actionType: 'global_block',
      assignments: {},
    }

    const completion = getDecisionCompletion(term, state)
    expect(completion.complete).toBe(true)
    expect(completion.selectedCount).toBe(0)
    expect(completion.requiredCount).toBe(0)
  })

  it('builds funnel decision payload with one assignment per custom_label_0', () => {
    const term = makeTerm(['soap dishes & holders', 'baskets'])
    const state: NeedsDecisionStateLike = {
      actionType: 'funnel',
      assignments: {
        'soap dishes & holders': 'high',
        baskets: 'medium',
      },
    }

    const item = buildDecisionItem(term, state)
    expect(item.action_type).toBe('funnel')
    expect(item.assignments).toEqual([
      { custom_label_0: 'soap dishes & holders', tier: 'high' },
      { custom_label_0: 'baskets', tier: 'medium' },
    ])
  })

  it('changes signature when assignment or action changes', () => {
    const term = makeTerm(['soap dishes & holders'])
    const baseState: NeedsDecisionStateLike = {
      actionType: 'funnel',
      assignments: {
        'soap dishes & holders': 'high',
      },
    }

    const baseline = createDecisionSignature(buildDecisionItem(term, baseState))
    const changedTier = createDecisionSignature(
      buildDecisionItem(term, {
        actionType: 'funnel',
        assignments: {
          'soap dishes & holders': 'medium',
        },
      })
    )
    const changedAction = createDecisionSignature(
      buildDecisionItem(term, {
        actionType: 'global_block',
        assignments: {},
      })
    )

    expect(changedTier).not.toBe(baseline)
    expect(changedAction).not.toBe(baseline)
  })
})
