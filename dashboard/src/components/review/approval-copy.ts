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
  if (platform === 'shopify') {
    return 'Shopify publish readiness checks platform content approval and a selected Shopify master image.'
  }

  return `${platformDisplay(platform)} publish readiness checks platform content approval plus variant content and variant image readiness.`
}
