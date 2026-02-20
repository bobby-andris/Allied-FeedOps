import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/optimization/decomposition/backfill/route'

const mocks = vi.hoisted(() => ({
  getNeedsDecisionTerms: vi.fn(),
  computeDecompositionArtifact: vi.fn(),
  insertArtifactsBatch: vi.fn(),
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: () => ({ startDate: '2026-02-01', endDate: '2026-02-20' }),
  sanitizeDateInput: (value: string | null | undefined) => value ?? undefined,
  sanitizeCustomLabel: (value: string | null | undefined) => value ?? undefined,
  sanitizeMinImpressions: () => 0,
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
}))

vi.mock('@/lib/optimization/decomposition/engine', () => ({
  computeDecompositionArtifact: mocks.computeDecompositionArtifact,
}))

vi.mock('@/lib/optimization/decomposition/repository', () => ({
  insertArtifactsBatch: mocks.insertArtifactsBatch,
}))

function buildRequest(url: string, body: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return new NextRequest(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  })
}

describe('POST /api/optimization/decomposition/backfill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.INTERNAL_API_TOKEN = 'test-token'

    mocks.getNeedsDecisionTerms.mockResolvedValue({
      terms: [
        {
          search_term: 'soap dishes for shower',
          custom_label_0s: [
            {
              custom_label_0: 'Soap Dishes & Holders',
              source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
              source_tier: 'HIGH',
              impressions: 56,
              clicks: 4,
              cost_micros: 19_260_000,
              conversions: 0,
              conversions_value: 0,
            },
          ],
        },
      ],
      date_window: {
        startDate: '2026-02-01',
        endDate: '2026-02-20',
      },
    })

    mocks.computeDecompositionArtifact.mockReturnValue({
      searchTerm: 'soap dishes for shower',
      customLabel0: 'Soap Dishes & Holders',
      parserVersion: 'decomp_v1',
      scoreVersion: 'score_v1',
      recommendationVersion: 'route_v1',
      intent: {
        product_object: 'soap dish',
        modifier_tokens: [],
        use_case_tokens: ['shower'],
        is_branded: false,
        is_competitor: false,
        has_mismatch_risk: false,
      },
      intentConfidence: 0.72,
      recommendation: {
        action_type: 'funnel',
        default_tier: 'high',
        confidence: 0.66,
        reason_codes: ['performance_weighted_tiering'],
      },
      value: {
        impact_score: 12,
        expected_clicks: 4,
        expected_cvr: 0,
        expected_conversion_value: 0,
        expected_profit_proxy: -19.26,
        uncertainty: 0.92,
      },
      diagnostics: {
        normalized_search_term: 'soap dishes for shower',
        matched_tokens: {
          brand: [],
          competitor: [],
          product_object_candidates: ['soap dish'],
          modifier: [],
          use_case: ['shower'],
          risk: [],
        },
        selected_product_object: 'soap dish',
        ambiguity_flags: {
          multiple_product_objects: false,
        },
        confidence_components: {
          base: 0.35,
          product_object_bonus: 0.2,
          modifier_or_use_case_bonus: 0.1,
          explicit_brand_or_competitor_bonus: 0,
          ambiguity_penalty: 0,
          final: 0.65,
        },
      },
      modelInputs: {},
      recommendationMetadata: {},
    })

    mocks.insertArtifactsBatch.mockResolvedValue({
      insertedPairs: 1,
      warnings: [],
    })
  })

  it('enforces token auth outside development', async () => {
    const request = buildRequest('http://localhost/api/optimization/decomposition/backfill', {
      dry_run: false,
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(401)
    expect(body.error).toBe('Unauthorized.')
  })

  it('supports dry-run mode without persisting rows', async () => {
    const request = buildRequest(
      'http://localhost/api/optimization/decomposition/backfill',
      { dry_run: true },
      { 'x-internal-token': 'test-token' }
    )

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.mode).toBe('dry_run')
    expect(body.inserted_pairs).toBe(0)
    expect(mocks.insertArtifactsBatch).not.toHaveBeenCalled()
  })

  it('persists artifacts when dry_run is false', async () => {
    const request = buildRequest(
      'http://localhost/api/optimization/decomposition/backfill',
      { dry_run: false },
      { 'x-internal-token': 'test-token' }
    )

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.mode).toBe('persist')
    expect(body.inserted_pairs).toBe(1)
    expect(mocks.insertArtifactsBatch).toHaveBeenCalledTimes(1)
  })
})
