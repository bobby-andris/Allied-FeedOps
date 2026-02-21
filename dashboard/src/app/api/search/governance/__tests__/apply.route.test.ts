import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/search/governance/apply/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  insertRowsSafe: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return {
    ...actual,
    insertRowsSafe: mocks.insertRowsSafe,
  }
})

function createSupabaseMock(existingActiveTerms: string[]) {
  const from = vi.fn((table: string) => {
    if (table === 'negative_registry') {
      const inFilter = vi.fn().mockResolvedValue({
        data: existingActiveTerms.map((term) => ({ term })),
        error: null,
      })
      const eqActive = vi.fn().mockReturnValue({ in: inFilter })
      const eqScope = vi.fn().mockReturnValue({ eq: eqActive })
      const select = vi.fn().mockReturnValue({ eq: eqScope })
      return { select }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('POST /api/search/governance/apply', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.insertRowsSafe.mockImplementation(async (_client: unknown, _table: string, rows: unknown[]) => ({
      inserted: rows.length,
    }))
  })

  it('dedupes active cross-channel negatives and reports skipped count', async () => {
    const supabase = createSupabaseMock(['brass robe hook'])
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/search/governance/apply', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        created_by: 'test:suite',
        candidates: [
          {
            search_term: 'brass robe hook',
            custom_label_0: 'MEDIUM',
            recommended_tier: 'exact',
            confidence: 0.81,
            reason_codes: ['exact_readiness_threshold_met'],
          },
          {
            search_term: 'brass towel ring',
            custom_label_0: 'MEDIUM',
            recommended_tier: 'phrase',
            confidence: 0.73,
            reason_codes: ['phrase_readiness_threshold_met'],
          },
        ],
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.applied_count).toBe(2)
    expect(body.deduped_negative_count).toBe(1)

    const negativeInsertCall = mocks.insertRowsSafe.mock.calls.find((call) => call[1] === 'negative_registry')
    expect(negativeInsertCall).toBeDefined()
    expect(negativeInsertCall?.[2]).toHaveLength(1)
    expect(negativeInsertCall?.[2]?.[0]).toMatchObject({
      term: 'brass towel ring',
      scope: 'cross_channel',
      active: true,
    })

    const operatorAuditInsertCall = mocks.insertRowsSafe.mock.calls.find(
      (call) => call[1] === 'operator_review_audit'
    )
    expect(operatorAuditInsertCall).toBeDefined()
    expect(operatorAuditInsertCall?.[2]).toHaveLength(2)
    expect(operatorAuditInsertCall?.[2]?.[0]).toMatchObject({
      queue_name: 'search_governance',
      entity_key: 'brass robe hook',
      action: 'approve_candidate',
      actor: 'test:suite',
    })
  })
})
