import { describe, expect, it } from 'vitest'

import {
  getPlatformApprovalActionText,
  getVariantApprovalActionText,
  getPublishReadinessHelpText,
} from '../approval-copy'

describe('approval copy clarity', () => {
  it('platform approval action text is explicit and non-ambiguous', () => {
    expect(getPlatformApprovalActionText('google')).toBe('Approve Google Content for Publishing')
    expect(getPlatformApprovalActionText('bing')).toBe('Approve Bing Content for Publishing')
    expect(getPlatformApprovalActionText('shopify')).toBe('Approve Shopify Content for Publishing')
  })

  it('variant approval action text explicitly calls out variant scope', () => {
    const text = getVariantApprovalActionText('google')

    expect(text).toMatch(/variant/i)
    expect(text).toMatch(/google/i)
  })

  it('publish readiness help text distinguishes platform and variant scopes', () => {
    const googleHelpText = getPublishReadinessHelpText('google')
    const bingHelpText = getPublishReadinessHelpText('bing')

    expect(googleHelpText).toMatch(/platform/i)
    expect(googleHelpText).toMatch(/variant/i)
    expect(googleHelpText).toMatch(/google/i)
    expect(googleHelpText).not.toMatch(/image/i)

    expect(bingHelpText).toMatch(/platform/i)
    expect(bingHelpText).toMatch(/variant/i)
    expect(bingHelpText).toMatch(/image/i)
    expect(bingHelpText).toMatch(/bing/i)
  })
})
