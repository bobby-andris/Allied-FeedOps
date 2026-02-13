import type { Platform } from '@/lib/publishing/types'

function platformDisplay(platform: Platform): string {
  if (platform === 'google') return 'Google'
  if (platform === 'bing') return 'Bing'
  return 'Shopify'
}

export function getPlatformApprovalActionText(platform: Platform): string {
  return `Approve ${platformDisplay(platform)} Content for Publishing`
}

export function getVariantApprovalActionText(platform: Extract<Platform, 'google' | 'bing'>): string {
  return `Approve All ${platformDisplay(platform)} Variant Content`
}

export function getPublishReadinessHelpText(platform: Platform): string {
  if (platform === 'google') {
    return 'Google publish readiness checks platform content approval plus variant content readiness. Variant image selection is optional.'
  }

  if (platform === 'bing') {
    return 'Bing publish readiness checks platform content approval plus variant content and variant image readiness.'
  }

  if (platform === 'shopify') {
    return 'Shopify publish readiness checks platform content approval. Shopify master image selection is optional.'
  }
  return `${platformDisplay(platform)} publish readiness checks platform content approval.`
}
