import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET, POST } from '@/app/api/monitoring/cost-reconciliation/route'

const mocks = vi.hoisted(() => ({
  readCostReconciliationReport: vi.fn(),
  runCostReconciliationCapture: vi.fn(),
}))

vi.mock('@/lib/monitoring/cost-reconciliation', () => ({
  readCostReconciliationReport: mocks.readCostReconciliationReport,
  runCostReconciliationCapture: mocks.runCostReconciliationCapture,
}))

describe('cost reconciliation monitoring route', () => {
  const originalCronSecret = process.env.CRON_SECRET

  beforeEach(() => {
    vi.clearAllMocks()
    if (originalCronSecret === undefined) {
      delete process.env.CRON_SECRET
    } else {
      process.env.CRON_SECRET = originalCronSecret
    }
  })

  it('GET returns report payload', async () => {
    mocks.readCostReconciliationReport.mockResolvedValue({
      generated_at: '2026-02-28T00:00:00.000Z',
      lookback_days: 21,
      latest: null,
      windows: [],
      cost_outliers: [],
      latency_outliers: [],
    })

    const request = new NextRequest(
      'http://localhost/api/monitoring/cost-reconciliation?lookback_days=21'
    )

    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.success).toBe(true)
    expect(mocks.readCostReconciliationReport).toHaveBeenCalledWith({ lookbackDays: 21 })
  })

  it('POST rejects unauthorized capture requests when CRON_SECRET is configured', async () => {
    process.env.CRON_SECRET = 'secret-token'

    const request = new NextRequest('http://localhost/api/monitoring/cost-reconciliation', {
      method: 'POST',
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(401)
    expect(body.error).toBe('Unauthorized capture request')
    expect(mocks.runCostReconciliationCapture).not.toHaveBeenCalled()
  })

  it('POST allows capture with cron header', async () => {
    process.env.CRON_SECRET = 'secret-token'
    mocks.runCostReconciliationCapture.mockResolvedValue({
      generated_at: '2026-02-28T00:00:00.000Z',
      windows_processed: 2,
      capture_results: [],
      warning_count: 0,
    })

    const request = new NextRequest(
      'http://localhost/api/monitoring/cost-reconciliation?lookback_days=2',
      {
        method: 'POST',
        headers: {
          'x-vercel-cron': '1',
        },
      }
    )

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.success).toBe(true)
    expect(mocks.runCostReconciliationCapture).toHaveBeenCalledWith({ lookbackDays: 2 })
  })
})
