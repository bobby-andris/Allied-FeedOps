import { describe, expect, it } from 'vitest'

import { selectPreferredVariantImages } from '../expand-variants'

describe('selectPreferredVariantImages', () => {
  it('prefers user-selected image when multiple approved images exist for one offer', () => {
    const selected = selectPreferredVariantImages([
      {
        gmc_offer_id: 'offer-1',
        shopify_cdn_url: 'https://cdn.example.com/ai.png',
        user_selected: false,
        ai_selected: true,
        generation_timestamp: '2026-02-12T10:00:00Z',
        created_at: '2026-02-12T10:00:00Z',
      },
      {
        gmc_offer_id: 'offer-1',
        shopify_cdn_url: 'https://cdn.example.com/user.png',
        user_selected: true,
        ai_selected: false,
        generation_timestamp: '2026-02-11T10:00:00Z',
        created_at: '2026-02-11T10:00:00Z',
      },
    ])

    expect(selected.get('offer-1')).toBe('https://cdn.example.com/user.png')
  })

  it('falls back to AI-selected image when user has not selected one', () => {
    const selected = selectPreferredVariantImages([
      {
        gmc_offer_id: 'offer-2',
        shopify_cdn_url: 'https://cdn.example.com/older.png',
        user_selected: false,
        ai_selected: false,
        generation_timestamp: '2026-02-10T10:00:00Z',
        created_at: '2026-02-10T10:00:00Z',
      },
      {
        gmc_offer_id: 'offer-2',
        shopify_cdn_url: 'https://cdn.example.com/ai.png',
        user_selected: false,
        ai_selected: true,
        generation_timestamp: '2026-02-09T10:00:00Z',
        created_at: '2026-02-09T10:00:00Z',
      },
    ])

    expect(selected.get('offer-2')).toBe('https://cdn.example.com/ai.png')
  })

  it('falls back to newest generated image when no user or AI selection exists', () => {
    const selected = selectPreferredVariantImages([
      {
        gmc_offer_id: 'offer-3',
        shopify_cdn_url: 'https://cdn.example.com/older.png',
        user_selected: false,
        ai_selected: false,
        generation_timestamp: '2026-02-10T10:00:00Z',
        created_at: '2026-02-10T10:00:00Z',
      },
      {
        gmc_offer_id: 'offer-3',
        shopify_cdn_url: 'https://cdn.example.com/newer.png',
        user_selected: false,
        ai_selected: false,
        generation_timestamp: '2026-02-11T10:00:00Z',
        created_at: '2026-02-11T10:00:00Z',
      },
    ])

    expect(selected.get('offer-3')).toBe('https://cdn.example.com/newer.png')
  })
})
