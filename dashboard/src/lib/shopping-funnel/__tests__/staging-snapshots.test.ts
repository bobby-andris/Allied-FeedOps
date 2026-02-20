import { describe, expect, it } from 'vitest'
import { buildStagedDecisionSnapshots } from '@/lib/shopping-funnel/staging-snapshots'

describe('buildStagedDecisionSnapshots', () => {
  it('builds one funnel decision with all custom_label_0 assignments', () => {
    const snapshots = buildStagedDecisionSnapshots([
      {
        search_term: 'soap dishes for shower',
        action_type: 'funnel',
        custom_label_0: 'soap dishes & holders',
        tier: 'high',
        created_at: '2026-02-20T01:00:00.000Z',
      },
      {
        search_term: 'soap dishes for shower',
        action_type: 'funnel',
        custom_label_0: 'baskets',
        tier: 'medium',
        created_at: '2026-02-20T01:00:00.000Z',
      },
    ])

    expect(snapshots).toEqual([
      {
        search_term: 'soap dishes for shower',
        action_type: 'funnel',
        assignments: [
          { custom_label_0: 'baskets', tier: 'medium' },
          { custom_label_0: 'soap dishes & holders', tier: 'high' },
        ],
        staged_at: '2026-02-20T01:00:00.000Z',
      },
    ])
  })

  it('prefers newest staged version for a search term when stale rows exist', () => {
    const snapshots = buildStagedDecisionSnapshots([
      {
        search_term: 'soap dishes for shower',
        action_type: 'funnel',
        custom_label_0: 'soap dishes & holders',
        tier: 'high',
        created_at: '2026-02-20T00:00:00.000Z',
      },
      {
        search_term: 'soap dishes for shower',
        action_type: 'global_block',
        custom_label_0: null,
        tier: null,
        created_at: '2026-02-20T02:00:00.000Z',
      },
    ])

    expect(snapshots).toEqual([
      {
        search_term: 'soap dishes for shower',
        action_type: 'global_block',
        assignments: undefined,
        staged_at: '2026-02-20T02:00:00.000Z',
      },
    ])
  })
})
