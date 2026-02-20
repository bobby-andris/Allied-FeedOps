import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  computeCoverageStats,
  getLatestArtifactsByPairs,
  insertArtifactsBatch,
} from '@/lib/optimization/decomposition/repository'
import { pairKey } from '@/lib/optimization/decomposition/types'
import { DECOMPOSITION_VERSIONS } from '@/lib/optimization/decomposition/config'
import type { DecompositionArtifact } from '@/lib/optimization/decomposition/types'

const mocks = vi.hoisted(() => {
  return {
    from: vi.fn(),
    createAdminClient: vi.fn(() => ({
      from: vi.fn(),
    })),
  }
})

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createQueryTable(data: unknown[], error: { message: string } | null = null) {
  const chain = {
    select: vi.fn().mockReturnThis(),
    in: vi.fn().mockReturnThis(),
    order: vi.fn().mockReturnThis(),
    limit: vi.fn().mockResolvedValue({ data, error }),
    insert: vi.fn().mockResolvedValue({ error }),
  }
  return chain
}

function createInsertTable(error: { message: string } | null = null) {
  return {
    insert: vi.fn().mockResolvedValue({ error }),
    select: vi.fn(),
    in: vi.fn(),
    order: vi.fn(),
    limit: vi.fn(),
  }
}

function createArtifact(overrides: Partial<DecompositionArtifact> = {}): DecompositionArtifact {
  return {
    searchTerm: 'soap dishes for shower',
    customLabel0: 'Soap Dishes & Holders',
    parserVersion: DECOMPOSITION_VERSIONS.parserVersion,
    scoreVersion: DECOMPOSITION_VERSIONS.scoreVersion,
    recommendationVersion: DECOMPOSITION_VERSIONS.recommendationVersion,
    intent: {
      product_object: 'soap dish',
      modifier_tokens: ['wall mounted'],
      use_case_tokens: ['shower'],
      is_branded: false,
      is_competitor: false,
      has_mismatch_risk: false,
    },
    intentConfidence: 0.75,
    recommendation: {
      action_type: 'funnel',
      default_tier: 'high',
      confidence: 0.74,
      reason_codes: ['performance_weighted_tiering'],
    },
    value: {
      impact_score: 22.4,
      expected_clicks: 14,
      expected_cvr: 0.08,
      expected_conversion_value: 87,
      expected_profit_proxy: 53,
      uncertainty: 0.3,
    },
    diagnostics: {
      normalized_search_term: 'soap dishes for shower',
      matched_tokens: {
        brand: [],
        competitor: [],
        product_object_candidates: ['soap dish'],
        modifier: ['wall mounted'],
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
    modelInputs: {
      impressions: 120,
      clicks: 14,
      conversions: 1,
      cost_micros: 2_000_000,
      conversions_value: 87,
      label_count: 1,
    },
    recommendationMetadata: {
      source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
      source_tier: 'HIGH',
      recommendation_version: DECOMPOSITION_VERSIONS.recommendationVersion,
    },
    ...overrides,
  }
}

describe('decomposition repository', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('selects latest artifact rows per pair key', async () => {
    const pair = { searchTerm: 'soap dishes for shower', customLabel0: 'Soap Dishes & Holders' }

    const oldTs = '2026-02-20T00:00:00.000Z'
    const newTs = '2026-02-21T00:00:00.000Z'

    const intentTable = createQueryTable([
      {
        search_term: pair.searchTerm,
        custom_label_0: pair.customLabel0,
        parser_version: DECOMPOSITION_VERSIONS.parserVersion,
        confidence: 0.5,
        created_at: newTs,
      },
      {
        search_term: pair.searchTerm,
        custom_label_0: pair.customLabel0,
        parser_version: DECOMPOSITION_VERSIONS.parserVersion,
        confidence: 0.4,
        created_at: oldTs,
      },
    ])

    const valueTable = createQueryTable([
      {
        search_term: pair.searchTerm,
        custom_label_0: pair.customLabel0,
        score_version: DECOMPOSITION_VERSIONS.scoreVersion,
        impact_score: 10,
        created_at: newTs,
      },
    ])

    const recommendationTable = createQueryTable([
      {
        search_term: pair.searchTerm,
        custom_label_0: pair.customLabel0,
        recommended_action: 'funnel',
        recommended_tier: 'high',
        confidence: 0.7,
        reason_codes: [],
        metadata: {
          recommendation_version: DECOMPOSITION_VERSIONS.recommendationVersion,
        },
        created_at: newTs,
      },
    ])

    const from = vi.fn((table: string) => {
      if (table === 'query_intent_features') return intentTable
      if (table === 'query_value_scores') return valueTable
      if (table === 'routing_recommendations') return recommendationTable
      throw new Error(`Unexpected table ${table}`)
    })

    mocks.createAdminClient.mockReturnValue({ from })

    const result = await getLatestArtifactsByPairs([pair])
    const key = pairKey(pair.searchTerm, pair.customLabel0)
    const artifacts = result.byPair.get(key)

    expect(artifacts?.intentRow?.created_at).toBe(newTs)
    expect(artifacts?.valueRow?.created_at).toBe(newTs)
    expect(artifacts?.recommendationRow?.created_at).toBe(newTs)
  })

  it('marks stale coverage when latest rows are outside threshold', async () => {
    const pair = { searchTerm: 'soap dishes for shower', customLabel0: 'Soap Dishes & Holders' }
    const staleTimestamp = new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString()

    const tableFactory = (payload: Record<string, unknown>) =>
      createQueryTable([
        {
          search_term: pair.searchTerm,
          custom_label_0: pair.customLabel0,
          created_at: staleTimestamp,
          ...payload,
        },
      ])

    const from = vi.fn((table: string) => {
      if (table === 'query_intent_features') {
        return tableFactory({ parser_version: DECOMPOSITION_VERSIONS.parserVersion, confidence: 0.6 })
      }
      if (table === 'query_value_scores') {
        return tableFactory({ score_version: DECOMPOSITION_VERSIONS.scoreVersion, impact_score: 5 })
      }
      if (table === 'routing_recommendations') {
        return tableFactory({
          recommended_action: 'funnel',
          recommended_tier: 'high',
          confidence: 0.6,
          reason_codes: [],
          metadata: { recommendation_version: DECOMPOSITION_VERSIONS.recommendationVersion },
        })
      }
      throw new Error(`Unexpected table ${table}`)
    })

    mocks.createAdminClient.mockReturnValue({ from })

    const coverage = await computeCoverageStats([pair], 24)

    expect(coverage.totalPairs).toBe(1)
    expect(coverage.cachedPairs).toBe(0)
    expect(coverage.stalePairs).toBe(1)
    expect(coverage.staleShare).toBe(100)
  })

  it('inserts artifacts in batches', async () => {
    const artifactA = createArtifact()
    const artifactB = createArtifact({
      searchTerm: 'soap dispenser brushed brass',
      recommendation: {
        action_type: 'funnel',
        default_tier: 'medium',
        confidence: 0.68,
        reason_codes: ['performance_weighted_tiering'],
      },
    })

    const intentTable = createInsertTable()
    const valueTable = createInsertTable()
    const recommendationTable = createInsertTable()

    const from = vi.fn((table: string) => {
      if (table === 'query_intent_features') return intentTable
      if (table === 'query_value_scores') return valueTable
      if (table === 'routing_recommendations') return recommendationTable
      throw new Error(`Unexpected table ${table}`)
    })

    mocks.createAdminClient.mockReturnValue({ from })

    const result = await insertArtifactsBatch([artifactA, artifactB], 1)

    expect(result.insertedPairs).toBe(2)
    expect(intentTable.insert).toHaveBeenCalledTimes(2)
    expect(valueTable.insert).toHaveBeenCalledTimes(2)
    expect(recommendationTable.insert).toHaveBeenCalledTimes(2)
  })

  it('returns warnings and continues when inserts fail', async () => {
    const artifact = createArtifact()

    const intentTable = createInsertTable({ message: 'intent write failed' })
    const valueTable = createInsertTable()
    const recommendationTable = createInsertTable()

    const from = vi.fn((table: string) => {
      if (table === 'query_intent_features') return intentTable
      if (table === 'query_value_scores') return valueTable
      if (table === 'routing_recommendations') return recommendationTable
      throw new Error(`Unexpected table ${table}`)
    })

    mocks.createAdminClient.mockReturnValue({ from })

    const result = await insertArtifactsBatch([artifact])

    expect(result.insertedPairs).toBe(0)
    expect(result.warnings).toEqual(expect.arrayContaining([expect.stringContaining('intent write failed')]))
  })
})
