import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/search/governance/movements/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  classifyIntent: vi.fn(),
  evaluateSearchGovernance: vi.fn(),
  evaluateGuardrails: vi.fn(),
  insertRowsSafe: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/intent/taxonomy', () => ({
  classifyIntent: mocks.classifyIntent,
}))

vi.mock('@/lib/intent/policy', () => ({
  evaluateSearchGovernance: mocks.evaluateSearchGovernance,
  evaluateGuardrails: mocks.evaluateGuardrails,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return {
    ...actual,
    insertRowsSafe: mocks.insertRowsSafe,
  }
})

function createSupabaseMock(options?: {
  approvedRows?: Array<{
    search_term: string
    custom_label_0: string | null
    confidence: number
    metadata: {
      current_tier?: 'broad' | 'phrase' | 'exact'
      metrics?: {
        impressions?: number
        clicks?: number
        conversions?: number
        conversionsValue?: number
        costMicros?: number
      }
    }
  }>
  guardrailRows?: Array<{ severity: 'low' | 'medium' | 'high' | 'critical' }>
  latestValueScoreCreatedAt?: string | null
}) {
  const approvedRows = options?.approvedRows ?? []
  const guardrailRows = options?.guardrailRows ?? []
  const latestValueScoreCreatedAt = options?.latestValueScoreCreatedAt ?? null

  const from = vi.fn((table: string) => {
    if (table === 'search_buildout_recommendations') {
      const limit = vi.fn().mockResolvedValue({ data: approvedRows, error: null })
      const order = vi.fn().mockReturnValue({ limit })
      const eq = vi.fn().mockReturnValue({ order })
      const select = vi.fn().mockReturnValue({ eq })
      return { select }
    }

    if (table === 'guardrail_incidents') {
      const limit = vi.fn().mockResolvedValue({ data: guardrailRows, error: null })
      const order = vi.fn().mockReturnValue({ limit })
      const inFilter = vi.fn().mockReturnValue({ order })
      const select = vi.fn().mockReturnValue({ in: inFilter })
      return { select }
    }

    if (table === 'query_value_scores') {
      const maybeSingle = vi.fn().mockResolvedValue({
        data: latestValueScoreCreatedAt ? { created_at: latestValueScoreCreatedAt } : null,
        error: null,
      })
      const limit = vi.fn().mockReturnValue({ maybeSingle })
      const order = vi.fn().mockReturnValue({ limit })
      const select = vi.fn().mockReturnValue({ order })
      return { select }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('POST /api/search/governance/movements', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.classifyIntent.mockReturnValue({
      normalizedQuery: 'brass robe hook',
      intentClass: 'CATEGORY_MID',
      subclasses: ['category_with_modifier'],
      reasonCodes: ['intent_mid_category'],
      matchedTokens: ['brass', 'robe', 'hook'],
      isBranded: false,
      isCompetitor: false,
      hasMismatchRisk: false,
    })

    mocks.evaluateSearchGovernance.mockReturnValue({
      searchTerm: 'brass robe hook',
      action: 'promote_to_exact',
      recommendedTier: 'exact',
      confidence: 0.81,
      reasonCodes: ['exact_readiness_threshold_met'],
      policyVersion: 'intent_v1',
    })

    mocks.evaluateGuardrails.mockReturnValue({
      status: 'go',
      reasonCodes: ['guardrails_clear'],
      incidents: [],
      policyVersion: 'intent_v1',
    })

    mocks.insertRowsSafe.mockImplementation(async (_client: unknown, _table: string, rows: unknown[]) => ({
      inserted: rows.length,
    }))
  })

  it('auto-loads approved recommendations when terms are omitted', async () => {
    const supabase = createSupabaseMock({
      approvedRows: [
        {
          search_term: 'brass robe hook',
          custom_label_0: 'MEDIUM',
          confidence: 0.81,
          metadata: {
            current_tier: 'phrase',
            metrics: {
              impressions: 240,
              clicks: 26,
              conversions: 5,
              conversionsValue: 144,
              costMicros: 18_000_000,
            },
          },
        },
      ],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/search/governance/movements', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        created_by: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.generated_count).toBe(1)
    expect(body.staged_count).toBe(1)
    expect(body.cancelled_count).toBe(0)
    expect(body.rollout_safety.status).toBe('go')
    expect(body.decisions[0].search_term).toBe('brass robe hook')
    expect(mocks.evaluateSearchGovernance).toHaveBeenCalledTimes(1)
    expect(mocks.insertRowsSafe.mock.calls.some((call) => call[1] === 'policy_decision_log')).toBe(
      true
    )
  })

  it('cancels movement actions when rollout safety is blocked', async () => {
    const supabase = createSupabaseMock({
      guardrailRows: [{ severity: 'critical' }],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    mocks.evaluateGuardrails.mockReturnValue({
      status: 'blocked',
      reasonCodes: ['critical_incident_open'],
      incidents: [
        {
          ruleId: 'critical_incident_open',
          severity: 'critical',
          message: 'Critical guardrail incidents are still open.',
          suggestedAction: 'Block automated execution and run rollback protocol.',
        },
      ],
      policyVersion: 'intent_v1',
    })

    const request = new NextRequest('http://localhost/api/search/governance/movements', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        terms: [
          {
            search_term: 'brass robe hook',
            custom_label_0: 'MEDIUM',
            current_tier: 'phrase',
            metrics: {
              impressions: 260,
              clicks: 28,
              conversions: 5,
              conversionsValue: 150,
              costMicros: 19_000_000,
            },
            confidence: 0.82,
          },
        ],
        created_by: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.generated_count).toBe(1)
    expect(body.staged_count).toBe(0)
    expect(body.cancelled_count).toBe(1)
    expect(body.rollout_safety.status).toBe('blocked')

    const actionInsertCall = mocks.insertRowsSafe.mock.calls.find(
      (call) => call[1] === 'policy_action_execution_log'
    )
    expect(actionInsertCall).toBeDefined()
    expect(actionInsertCall?.[2]?.[0]?.status).toBe('cancelled')
    expect(actionInsertCall?.[2]?.[0]?.reason_codes).toContain('rollout_safety_blocked')

    const operatorAuditInsertCall = mocks.insertRowsSafe.mock.calls.find(
      (call) => call[1] === 'operator_review_audit'
    )
    expect(operatorAuditInsertCall).toBeDefined()
    expect(operatorAuditInsertCall?.[2]).toHaveLength(1)
    expect(operatorAuditInsertCall?.[2]?.[0]).toMatchObject({
      queue_name: 'search_governance_movements',
      entity_key: 'brass robe hook',
      action: 'promote_to_exact',
      actor: 'test:suite',
    })
  })
})
