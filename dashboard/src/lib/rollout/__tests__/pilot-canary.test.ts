import { beforeEach, describe, expect, it } from 'vitest'
import { enforcePilotCanaryForSkus, getPilotCanarySnapshot } from '@/lib/rollout/pilot-canary'

describe('pilot canary guard', () => {
  const originalCanaryEnabled = process.env.FEEDOPS_PILOT_CANARY_ENABLED
  const originalAllowedSkus = process.env.FEEDOPS_PILOT_ALLOWED_SKUS
  const originalFailClosed = process.env.FEEDOPS_PILOT_FAIL_CLOSED

  beforeEach(() => {
    if (originalCanaryEnabled === undefined) {
      delete process.env.FEEDOPS_PILOT_CANARY_ENABLED
    } else {
      process.env.FEEDOPS_PILOT_CANARY_ENABLED = originalCanaryEnabled
    }
    if (originalAllowedSkus === undefined) {
      delete process.env.FEEDOPS_PILOT_ALLOWED_SKUS
    } else {
      process.env.FEEDOPS_PILOT_ALLOWED_SKUS = originalAllowedSkus
    }
    if (originalFailClosed === undefined) {
      delete process.env.FEEDOPS_PILOT_FAIL_CLOSED
    } else {
      process.env.FEEDOPS_PILOT_FAIL_CLOSED = originalFailClosed
    }
  })

  it('allows all traffic when canary is disabled', () => {
    process.env.FEEDOPS_PILOT_CANARY_ENABLED = '0'
    delete process.env.FEEDOPS_PILOT_ALLOWED_SKUS

    const result = enforcePilotCanaryForSkus(['CL-55'], 'regenerate')
    expect(result.allowed).toBe(true)
  })

  it('blocks requests when enabled and SKU is not allowlisted', async () => {
    process.env.FEEDOPS_PILOT_CANARY_ENABLED = '1'
    process.env.FEEDOPS_PILOT_ALLOWED_SKUS = 'CL-55,1033'
    process.env.FEEDOPS_PILOT_FAIL_CLOSED = '1'

    const result = enforcePilotCanaryForSkus(['CL-99'], 'publish-sku')
    expect(result.allowed).toBe(false)
    expect(result.blockedSkus).toEqual(['CL-99'])
    expect(result.response).toBeDefined()
    expect(result.response?.status).toBe(409)
  })

  it('returns config error when enabled, fail-closed, and allowlist is empty', () => {
    process.env.FEEDOPS_PILOT_CANARY_ENABLED = 'true'
    process.env.FEEDOPS_PILOT_ALLOWED_SKUS = ''
    process.env.FEEDOPS_PILOT_FAIL_CLOSED = 'true'

    const result = enforcePilotCanaryForSkus(['CL-55'], 'publish-batch')
    expect(result.allowed).toBe(false)
    expect(result.response?.status).toBe(503)
  })

  it('provides snapshot metadata for operational checks', () => {
    process.env.FEEDOPS_PILOT_CANARY_ENABLED = '1'
    process.env.FEEDOPS_PILOT_ALLOWED_SKUS = 'CL-55,1033,CL-66'
    process.env.FEEDOPS_PILOT_FAIL_CLOSED = '1'

    const snapshot = getPilotCanarySnapshot()
    expect(snapshot.enabled).toBe(true)
    expect(snapshot.allowlist_count).toBe(3)
    expect(snapshot.allowlist_preview).toContain('CL-55')
  })
})
