import { describe, expect, it } from 'vitest'

import {
  computePlatformReadiness,
  validateRequestedPlatformsReady,
  type PlatformReadinessState,
} from '../platform-readiness'

function makeState(overrides: Partial<PlatformReadinessState> = {}): PlatformReadinessState {
  return {
    content: {
      google: { titleApproved: false, descriptionApproved: false },
      bing: { titleApproved: false, descriptionApproved: false },
      shopify: { titleApproved: false, descriptionApproved: false },
    },
    variantApprovalsReady: false,
    variantImagesReady: false,
    shopifyMasterImageReady: false,
    ...overrides,
  }
}

describe('computePlatformReadiness + validateRequestedPlatformsReady', () => {
  it('acceptance matrix: google ready only', () => {
    const readiness = computePlatformReadiness(
      makeState({
        content: {
          google: { titleApproved: true, descriptionApproved: true },
          bing: { titleApproved: false, descriptionApproved: false },
          shopify: { titleApproved: false, descriptionApproved: false },
        },
        variantApprovalsReady: true,
        variantImagesReady: false,
        shopifyMasterImageReady: false,
      }),
    )

    expect(validateRequestedPlatformsReady(['google'], readiness).ok).toBe(true)
    expect(validateRequestedPlatformsReady(['bing'], readiness).ok).toBe(false)
    expect(validateRequestedPlatformsReady(['shopify'], readiness).ok).toBe(false)
  })

  it('acceptance matrix: shopify ready only', () => {
    const readiness = computePlatformReadiness(
      makeState({
        content: {
          google: { titleApproved: false, descriptionApproved: false },
          bing: { titleApproved: false, descriptionApproved: false },
          shopify: { titleApproved: true, descriptionApproved: true },
        },
        shopifyMasterImageReady: true,
      }),
    )

    expect(validateRequestedPlatformsReady(['shopify'], readiness).ok).toBe(true)
    expect(validateRequestedPlatformsReady(['google'], readiness).ok).toBe(false)
    expect(validateRequestedPlatformsReady(['bing'], readiness).ok).toBe(false)
  })

  it('acceptance matrix: google and bing ready, shopify content approved without master image', () => {
    const readiness = computePlatformReadiness(
      makeState({
        content: {
          google: { titleApproved: true, descriptionApproved: true },
          bing: { titleApproved: true, descriptionApproved: true },
          shopify: { titleApproved: true, descriptionApproved: true },
        },
        variantApprovalsReady: true,
        variantImagesReady: true,
        shopifyMasterImageReady: false,
      }),
    )

    expect(validateRequestedPlatformsReady(['google'], readiness).ok).toBe(true)
    expect(validateRequestedPlatformsReady(['bing'], readiness).ok).toBe(true)
    expect(validateRequestedPlatformsReady(['google', 'bing'], readiness).ok).toBe(true)

    const shopifyGate = validateRequestedPlatformsReady(['shopify'], readiness)
    expect(shopifyGate.ok).toBe(true)
    expect(shopifyGate.errors.length).toBe(0)
  })

  it('acceptance matrix: none ready fails closed with actionable errors', () => {
    const readiness = computePlatformReadiness(makeState())

    const gate = validateRequestedPlatformsReady(['google', 'bing', 'shopify'], readiness)
    expect(gate.ok).toBe(false)
    expect(gate.errors.length).toBeGreaterThanOrEqual(3)
    expect(gate.errors.every((error) => error.actionableMessage.length > 0)).toBe(true)
  })

  it('bing still requires variant image readiness', () => {
    const readiness = computePlatformReadiness(
      makeState({
        content: {
          google: { titleApproved: true, descriptionApproved: true },
          bing: { titleApproved: true, descriptionApproved: true },
          shopify: { titleApproved: false, descriptionApproved: false },
        },
        variantApprovalsReady: true,
        variantImagesReady: false,
      }),
    )

    expect(readiness.google.ready).toBe(true)
    expect(readiness.bing.ready).toBe(false)
    expect(readiness.bing.blockers.some((blocker) => blocker.code === 'bing_variant_image_not_selected')).toBe(true)
  })

  it('shopify readiness does not require a selected master image', () => {
    const readiness = computePlatformReadiness(
      makeState({
        content: {
          google: { titleApproved: false, descriptionApproved: false },
          bing: { titleApproved: false, descriptionApproved: false },
          shopify: { titleApproved: true, descriptionApproved: true },
        },
        variantApprovalsReady: true,
        variantImagesReady: true,
        shopifyMasterImageReady: false,
      }),
    )

    expect(readiness.shopify.ready).toBe(true)
    expect(
      readiness.shopify.blockers.some((blocker) => blocker.code === 'shopify_master_image_not_selected'),
    ).toBe(false)
  })
})
