import { beforeEach, describe, expect, it } from 'vitest'
import { GET } from '@/app/api/monitoring/pilot-rollout/route'

describe('pilot rollout monitoring route', () => {
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

  it('returns canary snapshot payload', async () => {
    process.env.FEEDOPS_PILOT_CANARY_ENABLED = '1'
    process.env.FEEDOPS_PILOT_ALLOWED_SKUS = 'CL-55,1033'
    process.env.FEEDOPS_PILOT_FAIL_CLOSED = '1'

    const response = await GET()
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.success).toBe(true)
    expect(body.snapshot.enabled).toBe(true)
    expect(body.snapshot.allowlist_count).toBe(2)
  })
})
