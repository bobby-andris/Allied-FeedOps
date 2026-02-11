import { describe, expect, it } from 'vitest'

import { buildProductMasterImageFromVariant } from '../master-selection'

describe('master image selection semantics', () => {
  it('maps approved variant image to master product image payload', () => {
    const payload = buildProductMasterImageFromVariant(
      {
        id: 'variant-id-1',
        master_sku: '920D-6',
        variation_index: 2,
        image_url: 'https://example.com/variant.jpg',
        thumbnail_url: 'https://example.com/thumb.jpg',
        prompt: 'variant prompt',
        generation_model: 'gpt-image-1',
        generation_timestamp: '2026-02-11T10:00:00.000Z',
        score: 91,
        score_breakdown: { composition: 0.9 },
        approval_status: 'approved',
        approved_by: 'dashboard_user',
        approved_at: '2026-02-11T10:01:00.000Z',
      },
      'shopify-product-123',
    )

    expect(payload.master_sku).toBe('920D-6')
    expect(payload.shopify_product_id).toBe('shopify-product-123')
    expect(payload.variation_index).toBe(2)
    expect(payload.image_url).toBe('https://example.com/variant.jpg')
    expect(payload.user_selected).toBe(true)
    expect(payload.approval_status).toBe('approved')
  })

  it('keeps approved metadata when cloning variant image to master scope', () => {
    const payload = buildProductMasterImageFromVariant(
      {
        id: 'variant-id-2',
        master_sku: '920D-6',
        variation_index: 1,
        image_url: 'https://example.com/variant-2.jpg',
        thumbnail_url: null,
        prompt: null,
        generation_model: null,
        generation_timestamp: null,
        score: null,
        score_breakdown: null,
        approval_status: 'approved',
        approved_by: 'qa_user',
        approved_at: '2026-02-11T10:02:00.000Z',
      },
      'shopify-product-999',
    )

    expect(payload.approved_by).toBe('qa_user')
    expect(payload.approved_at).toBe('2026-02-11T10:02:00.000Z')
  })
})
