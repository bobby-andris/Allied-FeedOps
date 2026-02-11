import type { Platform } from '@/lib/publishing/types'

export interface PlatformApprovalState {
  titleApproved: boolean
  descriptionApproved: boolean
}

export interface PlatformReadinessState {
  content: Record<Platform, PlatformApprovalState>
  variantApprovalsReady: boolean
  variantImagesReady: boolean
  shopifyMasterImageReady: boolean
}

export interface PlatformReadinessBlocker {
  code: string
  reason: string
  actionableMessage: string
}

export interface PlatformReadinessResult {
  ready: boolean
  blockers: PlatformReadinessBlocker[]
}

export type PlatformReadinessByPlatform = Record<Platform, PlatformReadinessResult>

export interface PlatformReadinessError extends PlatformReadinessBlocker {
  platform: Platform
}

export interface PlatformReadinessValidation {
  ok: boolean
  errors: PlatformReadinessError[]
}

function contentBlockers(platform: Platform, state: PlatformApprovalState): PlatformReadinessBlocker[] {
  const blockers: PlatformReadinessBlocker[] = []

  if (!state.titleApproved) {
    blockers.push({
      code: `${platform}_title_not_approved`,
      reason: `${platform} title is not approved`,
      actionableMessage: `Approve ${platform} title content before publishing.`,
    })
  }
  if (!state.descriptionApproved) {
    blockers.push({
      code: `${platform}_description_not_approved`,
      reason: `${platform} description is not approved`,
      actionableMessage: `Approve ${platform} description content before publishing.`,
    })
  }

  return blockers
}

function withPlatformSpecificBlockers(
  platform: Platform,
  state: PlatformReadinessState,
  baseBlockers: PlatformReadinessBlocker[],
): PlatformReadinessBlocker[] {
  if (platform === 'google' || platform === 'bing') {
    if (!state.variantApprovalsReady) {
      baseBlockers.push({
        code: `${platform}_variant_content_not_approved`,
        reason: `${platform} variant content is not fully approved`,
        actionableMessage: `Approve all ${platform} variant content before publishing ${platform}.`,
      })
    }
  }

  if (platform === 'bing') {
    if (!state.variantImagesReady) {
      baseBlockers.push({
        code: 'bing_variant_image_not_selected',
        reason: 'bing variant image selection is incomplete',
        actionableMessage: 'Select and approve one variant image per finish before publishing bing.',
      })
    }
  }

  if (platform === 'shopify' && !state.shopifyMasterImageReady) {
    baseBlockers.push({
      code: 'shopify_master_image_not_selected',
      reason: 'Shopify master image is not selected',
      actionableMessage: 'Select an approved Shopify master image before publishing Shopify.',
    })
  }

  return baseBlockers
}

export function computePlatformReadiness(state: PlatformReadinessState): PlatformReadinessByPlatform {
  const platforms: Platform[] = ['google', 'bing', 'shopify']
  const readiness = {} as PlatformReadinessByPlatform

  for (const platform of platforms) {
    const blockers = withPlatformSpecificBlockers(
      platform,
      state,
      contentBlockers(platform, state.content[platform]),
    )

    readiness[platform] = {
      ready: blockers.length === 0,
      blockers,
    }
  }

  return readiness
}

export function validateRequestedPlatformsReady(
  requestedPlatforms: Platform[],
  readiness: PlatformReadinessByPlatform,
): PlatformReadinessValidation {
  const errors: PlatformReadinessError[] = []

  for (const platform of requestedPlatforms) {
    const platformReadiness = readiness[platform]
    if (!platformReadiness || platformReadiness.ready) {
      continue
    }

    for (const blocker of platformReadiness.blockers) {
      errors.push({
        platform,
        ...blocker,
      })
    }
  }

  return {
    ok: errors.length === 0,
    errors,
  }
}
