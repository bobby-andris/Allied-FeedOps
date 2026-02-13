import { describe, expect, it } from 'vitest'

import {
  buildPlatformProgress,
  computePlatformReadinessForSku,
  latestProductionPublishSnapshots,
} from '../platform-progress'

describe('platform progress helpers', () => {
  it('computes readiness from stored approval and image state', () => {
    const readiness = computePlatformReadinessForSku({
      contentRecords: [
        { platform: 'google', content_type: 'title', approved_content: 'Google title' },
        { platform: 'google', content_type: 'description', approved_content: 'Google description' },
        { platform: 'shopify', content_type: 'title', approved_content: 'Shopify title' },
      ],
      variants: [{ finish: 'Antique Brass' }, { finish: 'Matte Black' }],
      variantApprovals: [
        {
          finish: 'Antique Brass',
          approval_status: 'approved',
          title_approved: 1,
          description_approved: 1,
        },
        {
          finish: 'Matte Black',
          approval_status: 'approved',
          title_approved: 1,
          description_approved: 1,
        },
      ],
      variantImages: [
        { finish: 'Antique Brass', approval_status: 'approved', user_selected: true },
        { finish: 'Matte Black', approval_status: 'approved', user_selected: true },
      ],
    })

    expect(readiness.google.ready).toBe(true)
    expect(readiness.bing.ready).toBe(false)
    expect(readiness.shopify.ready).toBe(false)
  })

  it('picks latest successful production snapshot per platform', () => {
    const snapshots = latestProductionPublishSnapshots([
      {
        platform: 'google',
        published_at: '2026-02-12T10:00:00.000Z',
        published_title: 'Old Google title',
        published_description: 'Old Google description',
        content_version: 1,
      },
      {
        platform: 'google',
        published_at: '2026-02-13T10:00:00.000Z',
        published_title: 'New Google title',
        published_description: 'New Google description',
        content_version: 2,
      },
      {
        platform: 'shopify',
        published_at: '2026-02-13T11:00:00.000Z',
        published_title: 'Shopify title',
        published_description: 'Shopify description',
        content_version: 3,
      },
    ])

    expect(snapshots.google?.publishedTitle).toBe('New Google title')
    expect(snapshots.google?.contentVersion).toBe(2)
    expect(snapshots.shopify?.publishedDescription).toBe('Shopify description')
  })

  it('builds progress state using readiness and publish snapshots', () => {
    const readiness = computePlatformReadinessForSku({
      contentRecords: [
        { platform: 'google', content_type: 'title', approved_content: 'Google title' },
        { platform: 'google', content_type: 'description', approved_content: 'Google description' },
        { platform: 'bing', content_type: 'title', approved_content: 'Bing title' },
        { platform: 'bing', content_type: 'description', approved_content: 'Bing description' },
        { platform: 'shopify', content_type: 'title', approved_content: 'Shopify title' },
        { platform: 'shopify', content_type: 'description', approved_content: 'Shopify description' },
      ],
      variants: [{ finish: 'Antique Brass' }],
      variantApprovals: [
        {
          finish: 'Antique Brass',
          approval_status: 'approved',
          title_approved: true,
          description_approved: true,
        },
      ],
      variantImages: [{ finish: 'Antique Brass', approval_status: 'approved', user_selected: true }],
    })

    const snapshots = latestProductionPublishSnapshots([
      {
        platform: 'google',
        published_at: '2026-02-13T10:00:00.000Z',
        published_title: 'Google title',
        published_description: 'Google description',
        content_version: 5,
      },
    ])

    const progress = buildPlatformProgress(readiness, snapshots)
    const google = progress.find((item) => item.platform === 'google')
    const bing = progress.find((item) => item.platform === 'bing')
    const shopify = progress.find((item) => item.platform === 'shopify')

    expect(google?.state).toBe('published')
    expect(google?.publishedSnapshot?.contentVersion).toBe(5)
    expect(bing?.state).toBe('ready')
    expect(shopify?.state).toBe('ready')
  })
})
