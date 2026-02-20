import { describe, expect, it } from 'vitest'
import { summarizeCampaignSetIntegrity } from '@/lib/shopping-funnel/service'

describe('summarizeCampaignSetIntegrity', () => {
  it('summarizes campaign pattern coverage and tier gaps', () => {
    const summary = summarizeCampaignSetIntegrity(
      [
        'AVD - Shopping - US - cabinet hardware - HIGH',
        'AVD - Shopping - US - cabinet hardware - MEDIUM',
        'AVD - Shopping - US - catchall - HIGH',
        'AVD - Shopping - BRANDED - US',
      ],
      [
        'AVD - Shopping - US - cabinet hardware - HIGH|AVD - Shopping - US - cabinet hardware - HIGH',
        'AVD - Shopping - US - cabinet hardware - MEDIUM|Mismatch Ad Group',
      ]
    )

    expect(summary.enabled_shopping_campaigns).toBe(2)
    expect(summary.parsed_funnel_campaigns).toBe(2)
    expect(summary.non_pattern_campaign_count).toBe(0)
    expect(summary.non_pattern_campaigns).toEqual([])
    expect(summary.ad_group_name_mismatch_count).toBe(1)
    expect(summary.custom_label_0_count).toBe(1)
    expect(summary.labels_with_missing_tiers).toEqual([
      {
        custom_label_0: 'cabinet hardware',
        present_tiers: ['HIGH', 'MEDIUM'],
        missing_tiers: ['LOW'],
      },
    ])
  })

  it('returns no gaps for complete label tier sets', () => {
    const summary = summarizeCampaignSetIntegrity(
      [
        'AVD - Shopping - US - wall mounted towel bars - HIGH',
        'AVD - Shopping - US - wall mounted towel bars - MEDIUM',
        'AVD - Shopping - US - wall mounted towel bars - LOW',
      ],
      []
    )

    expect(summary.custom_label_0_count).toBe(1)
    expect(summary.labels_with_missing_tiers).toEqual([])
    expect(summary.non_pattern_campaign_count).toBe(0)
  })
})
