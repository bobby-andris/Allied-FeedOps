import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  resolveCanonicalMasterSkuList: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/master-sku', () => ({
  resolveCanonicalMasterSkuList: mocks.resolveCanonicalMasterSkuList,
}))

import { POST, maxDuration } from '@/app/api/regenerate/batch/route'

function createGeneratedContentSupabase(rows: Array<{ master_sku: string | null }>) {
  const range = vi.fn().mockResolvedValue({ data: rows, error: null })
  const order = vi.fn().mockReturnValue({ range })
  const not = vi.fn().mockReturnValue({ order })
  const select = vi.fn().mockReturnValue({ not })
  const from = vi.fn().mockReturnValue({ select })
  return { from }
}

function createBatchRequest(headers?: Record<string, string>) {
  return new NextRequest('http://localhost/api/regenerate/batch', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(headers ?? {}),
    },
    body: JSON.stringify({
      skus: ['PTH-1'],
      platforms: ['google'],
      content_types: ['title'],
    }),
  })
}

describe('POST /api/regenerate/batch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()

    const supabase = createGeneratedContentSupabase([{ master_sku: 'PTH-1' }])
    mocks.createAdminClient.mockReturnValue(supabase)
    mocks.resolveCanonicalMasterSkuList.mockImplementation(async (_client, skus: string[]) => skus)
  })

  it('forwards cookie and authorization headers to internal regenerate requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          state: 'completed',
          content: 'Regenerated content',
          version: 3,
        }),
        {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }
      )
    )
    vi.stubGlobal('fetch', fetchMock)

    const response = await POST(
      createBatchRequest({
        cookie: 'sb-access-token=abc123',
        authorization: 'Bearer test-token',
      })
    )
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.summary.successful).toBe(1)
    expect(body.summary.failed).toBe(0)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/regenerate'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          cookie: 'sb-access-token=abc123',
          authorization: 'Bearer test-token',
        }),
      })
    )
  })

  it('uses the maximum allowed hobby serverless duration budget', () => {
    expect(maxDuration).toBe(300)
  })

  it('processes batch operations concurrently to reduce end-to-end request time', async () => {
    let inFlight = 0
    let maxInFlight = 0
    const fetchMock = vi.fn().mockImplementation(async () => {
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      await new Promise((resolve) => setTimeout(resolve, 30))
      inFlight -= 1
      return new Response(
        JSON.stringify({
          state: 'completed',
          content: 'ok',
          version: 1,
        }),
        {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const request = new NextRequest('http://localhost/api/regenerate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        skus: ['PTH-1'],
        platforms: ['google', 'bing'],
        content_types: ['title'],
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.summary.total_operations).toBe(2)
    expect(body.summary.successful).toBe(2)
    expect(maxInFlight).toBeGreaterThanOrEqual(2)
  })

  it('returns a structured auth error when internal regenerate responds with redirect auth status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('<html>redirect</html>', {
        status: 307,
        headers: { 'content-type': 'text/html' },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const response = await POST(createBatchRequest())
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.summary.successful).toBe(0)
    expect(body.summary.failed).toBe(1)
    expect(body.results[0]).toEqual(
      expect.objectContaining({
        success: false,
        code: 'batch_regenerate_internal_auth_required',
        step: 'internal_regenerate_auth',
      })
    )
    expect(body.results[0].error).toContain('not authenticated')
  })

  it('preserves downstream non-auth error details when regenerate returns JSON errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: 'Validation failed',
          code: 'validation_failed',
          step: 'validation',
          actionable_message: 'Fix data and retry',
          validation_errors: ['title too short'],
        }),
        {
          status: 422,
          headers: { 'content-type': 'application/json' },
        }
      )
    )
    vi.stubGlobal('fetch', fetchMock)

    const response = await POST(createBatchRequest())
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.summary.failed).toBe(1)
    expect(body.results[0]).toEqual(
      expect.objectContaining({
        success: false,
        error: 'Validation failed',
        code: 'validation_failed',
        step: 'validation',
        actionable_message: 'Fix data and retry',
      })
    )
    expect(body.results[0].validation_errors).toEqual(['title too short'])
  })
})
