import { describe, expect, it } from 'vitest'
import {
  mineNewQueries,
  buildCampaignDraft,
  generateCampaignDrafts,
} from '@/lib/intent/query-mining'

describe('mineNewQueries', () => {
  it('returns only novel terms not in existing set', () => {
    const existing = ['brass towel bar', 'chrome faucet']
    const candidates = ['brass towel bar', 'oil rubbed bronze shower head', 'chrome faucet']
    const result = mineNewQueries(existing, candidates)
    expect(result).toEqual(['oil rubbed bronze shower head'])
  })

  it('performs case-insensitive deduplication', () => {
    const existing = ['Brass Towel Bar']
    const candidates = ['brass towel bar', 'BRASS TOWEL BAR', 'new term']
    const result = mineNewQueries(existing, candidates)
    expect(result).toEqual(['new term'])
  })

  it('handles empty existing terms', () => {
    const result = mineNewQueries([], ['term1', 'term2'])
    expect(result).toEqual(['term1', 'term2'])
  })

  it('handles empty candidate terms', () => {
    const result = mineNewQueries(['existing'], [])
    expect(result).toEqual([])
  })

  it('handles both empty', () => {
    const result = mineNewQueries([], [])
    expect(result).toEqual([])
  })

  it('filters out empty/whitespace-only candidates', () => {
    const result = mineNewQueries([], ['valid', '', '   ', 'also valid'])
    expect(result).toEqual(['valid', 'also valid'])
  })

  it('trims whitespace when comparing', () => {
    const existing = ['brass towel bar']
    const candidates = ['  brass towel bar  ']
    const result = mineNewQueries(existing, candidates)
    expect(result).toEqual([])
  })
})

describe('buildCampaignDraft', () => {
  it('generates a campaign draft from a query cluster', () => {
    const draft = buildCampaignDraft({
      terms: ['brass towel bar 24 inch', 'brass towel rack'],
      intentClass: 'PRODUCT_HIGH',
      recommendedTier: 'exact',
      avgConfidence: 0.85,
    })

    expect(draft.campaignName).toContain('Product High-Intent')
    expect(draft.adGroupName).toContain('PRODUCT_HIGH')
    expect(draft.matchType).toBe('exact')
    expect(draft.keywords).toEqual(['brass towel bar 24 inch', 'brass towel rack'])
    expect(draft.estimatedVolume).toBe(2)
  })

  it('maps broad tier to broad match type', () => {
    const draft = buildCampaignDraft({
      terms: ['bathroom accessories'],
      intentClass: 'DISCOVERY_LOW',
      recommendedTier: 'broad',
      avgConfidence: 0.5,
    })
    expect(draft.matchType).toBe('broad')
  })

  it('maps phrase tier to phrase match type', () => {
    const draft = buildCampaignDraft({
      terms: ['towel bar'],
      intentClass: 'CATEGORY_MID',
      recommendedTier: 'phrase',
      avgConfidence: 0.7,
    })
    expect(draft.matchType).toBe('phrase')
  })
})

describe('generateCampaignDrafts', () => {
  it('returns empty array for empty input', () => {
    const result = generateCampaignDrafts([])
    expect(result).toEqual([])
  })

  it('groups briefs by intent class and generates one draft per group', () => {
    const briefs = [
      {
        intent_class: 'PRODUCT_HIGH',
        terms: ['brass towel bar'],
        recommended_tier: 'exact',
        avg_confidence: 0.9,
      },
      {
        intent_class: 'PRODUCT_HIGH',
        terms: ['brass shower head'],
        recommended_tier: 'exact',
        avg_confidence: 0.85,
      },
      {
        intent_class: 'CATEGORY_MID',
        terms: ['bathroom accessories'],
        recommended_tier: 'phrase',
        avg_confidence: 0.7,
      },
    ]

    const drafts = generateCampaignDrafts(briefs)
    expect(drafts).toHaveLength(2)

    const productDraft = drafts.find((d) => d.campaignName.includes('Product'))
    expect(productDraft).toBeDefined()
    expect(productDraft!.keywords).toContain('brass towel bar')
    expect(productDraft!.keywords).toContain('brass shower head')
    expect(productDraft!.matchType).toBe('exact')

    const categoryDraft = drafts.find((d) => d.campaignName.includes('Category'))
    expect(categoryDraft).toBeDefined()
    expect(categoryDraft!.keywords).toContain('bathroom accessories')
  })

  it('deduplicates terms within a group', () => {
    const briefs = [
      {
        intent_class: 'PRODUCT_HIGH',
        terms: ['brass towel bar'],
        recommended_tier: 'exact',
        avg_confidence: 0.9,
      },
      {
        intent_class: 'PRODUCT_HIGH',
        terms: ['brass towel bar', 'new term'],
        recommended_tier: 'exact',
        avg_confidence: 0.85,
      },
    ]

    const drafts = generateCampaignDrafts(briefs)
    expect(drafts).toHaveLength(1)
    expect(drafts[0].keywords).toEqual(['brass towel bar', 'new term'])
  })
})
