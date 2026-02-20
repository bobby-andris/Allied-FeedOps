import { describe, expect, it, vi } from 'vitest'
import {
  GoogleAdsRetryError,
  classifyGoogleAdsError,
  getRetryDelayMs,
  runWithGoogleAdsRetry,
} from '@/lib/shopping-funnel/retry'

describe('shopping-funnel retry helpers', () => {
  it('classifies rate-limit errors as retryable', () => {
    const error = new Error('RESOURCE_TEMPORARILY_EXHAUSTED: Too many requests')
    const result = classifyGoogleAdsError(error)

    expect(result.code).toBe('RESOURCE_TEMPORARILY_EXHAUSTED')
    expect(result.retryable).toBe(true)
    expect(result.rateLimited).toBe(true)
  })

  it('uses long backoff for rate-limit retries', () => {
    const delay = getRetryDelayMs(2, {
      code: 'RESOURCE_TEMPORARILY_EXHAUSTED',
      retryable: true,
      rateLimited: true,
      message: 'rate limited',
    })

    expect(delay).toBe(60000)
  })

  it('retries transient errors and returns retry count', async () => {
    let attempts = 0
    const sleep = vi.fn(async () => undefined)

    const result = await runWithGoogleAdsRetry(
      async () => {
        attempts += 1
        if (attempts < 3) {
          throw new Error('TRANSIENT_ERROR')
        }
        return 'ok'
      },
      { sleep, baseDelayMs: 10 }
    )

    expect(result.value).toBe('ok')
    expect(result.retryCount).toBe(2)
    expect(sleep).toHaveBeenCalledTimes(2)
  })

  it('throws typed retry error when retries are exhausted', async () => {
    const sleep = vi.fn(async () => undefined)

    await expect(
      runWithGoogleAdsRetry(
        async () => {
          throw new Error('INTERNAL_ERROR: backend unavailable')
        },
        { sleep, maxRetries: 2, baseDelayMs: 10 }
      )
    ).rejects.toBeInstanceOf(GoogleAdsRetryError)

    await expect(
      runWithGoogleAdsRetry(
        async () => {
          throw new Error('INTERNAL_ERROR: backend unavailable')
        },
        { sleep, maxRetries: 2, baseDelayMs: 10 }
      )
    ).rejects.toMatchObject({ code: 'INTERNAL_ERROR', retryCount: 2 })
  })
})
