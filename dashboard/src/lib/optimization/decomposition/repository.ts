import { DECOMPOSITION_BATCH_SIZE, DECOMPOSITION_VERSIONS, DEFAULT_STALE_THRESHOLD_HOURS } from '@/lib/optimization/decomposition/config'
import type {
  CoverageStats,
  DecompositionArtifact,
  DecompositionPairInput,
  InsertArtifactsResult,
  LatestArtifactsResult,
  PairArtifacts,
} from '@/lib/optimization/decomposition/types'
import { pairKey } from '@/lib/optimization/decomposition/types'
import type { QueryIntentFeatures, QueryRecommendation, QueryValueScore } from '@/lib/shopping-funnel/types'
import { createAdminClient } from '@/lib/supabase/admin'
import type {
  QueryIntentFeatureRow,
  QueryValueScoreRow,
  RoutingRecommendationRow,
} from '@/lib/supabase/types'

interface ArtifactVersionFilter {
  parserVersion: string
  scoreVersion: string
  recommendationVersion: string
}

type PairIdentifier = Pick<DecompositionPairInput, 'searchTerm' | 'customLabel0'>

interface CoverageSummaryOptions {
  staleThresholdHours: number
  versions: ArtifactVersionFilter
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = []
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size))
  }
  return chunks
}

function normalizeNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return fallback
  }
  return numeric
}

function isFresh(createdAt: string, staleThresholdHours: number): boolean {
  const createdTime = Date.parse(createdAt)
  if (Number.isNaN(createdTime)) {
    return false
  }

  const staleCutoff = Date.now() - staleThresholdHours * 60 * 60 * 1000
  return createdTime >= staleCutoff
}

function latestByPair<T extends { search_term: string; custom_label_0: string; created_at: string }>(
  rows: T[],
  pairSet: Set<string>
): Map<string, T> {
  const byPair = new Map<string, T>()

  for (const row of rows) {
    const key = pairKey(row.search_term, row.custom_label_0)
    if (!pairSet.has(key) || byPair.has(key)) {
      continue
    }
    byPair.set(key, row)
  }

  return byPair
}

function summarizeCoverage(
  pairs: PairIdentifier[],
  artifactsByPair: Map<string, PairArtifacts>,
  options: CoverageSummaryOptions
): CoverageStats {
  const uniquePairKeys = new Set(pairs.map((pair) => pairKey(pair.searchTerm, pair.customLabel0)))

  if (uniquePairKeys.size === 0) {
    return {
      totalPairs: 0,
      cachedPairs: 0,
      missingPairs: 0,
      stalePairs: 0,
      staleShare: 0,
      coveragePercent: 0,
      latestCreatedAt: null,
      details: [],
    }
  }

  let cachedPairs = 0
  let stalePairs = 0
  let missingPairs = 0
  let latestCreatedAt: string | null = null

  const details: CoverageStats['details'] = []

  for (const pair of pairs) {
    const key = pairKey(pair.searchTerm, pair.customLabel0)
    const artifact = artifactsByPair.get(key)

    const intentRow = artifact?.intentRow
    const valueRow = artifact?.valueRow
    const recommendationRow = artifact?.recommendationRow

    const intentVersionOk = intentRow?.parser_version === options.versions.parserVersion
    const valueVersionOk = valueRow?.score_version === options.versions.scoreVersion
    const recommendationVersionOk =
      recommendationRow?.metadata &&
      typeof recommendationRow.metadata === 'object' &&
      (recommendationRow.metadata as Record<string, unknown>).recommendation_version ===
        options.versions.recommendationVersion

    const hasIntent = Boolean(intentRow && intentVersionOk)
    const hasValue = Boolean(valueRow && valueVersionOk)
    const hasRecommendation = Boolean(recommendationRow && recommendationVersionOk)

    const createdCandidates = [intentRow?.created_at, valueRow?.created_at, recommendationRow?.created_at].filter(
      (value): value is string => Boolean(value)
    )

    for (const candidate of createdCandidates) {
      if (!latestCreatedAt || Date.parse(candidate) > Date.parse(latestCreatedAt)) {
        latestCreatedAt = candidate
      }
    }

    const staleFlags = [intentRow?.created_at, valueRow?.created_at, recommendationRow?.created_at]
      .filter((value): value is string => Boolean(value))
      .map((value) => !isFresh(value, options.staleThresholdHours))

    const isStale = staleFlags.length > 0 && staleFlags.some(Boolean)
    const allPresent = hasIntent && hasValue && hasRecommendation && !isStale

    if (allPresent) {
      cachedPairs += 1
    } else if (hasIntent || hasValue || hasRecommendation) {
      stalePairs += 1
    } else {
      missingPairs += 1
    }

    details.push({
      pairKey: key,
      hasIntent,
      hasValue,
      hasRecommendation,
      allPresent,
      isStale,
    })
  }

  const totalPairs = uniquePairKeys.size
  return {
    totalPairs,
    cachedPairs,
    stalePairs,
    missingPairs,
    staleShare: Number(((stalePairs / totalPairs) * 100).toFixed(2)),
    coveragePercent: Number(((cachedPairs / totalPairs) * 100).toFixed(2)),
    latestCreatedAt,
    details,
  }
}

export async function getLatestArtifactsByPairs(
  pairs: PairIdentifier[],
  versions: ArtifactVersionFilter = DECOMPOSITION_VERSIONS
): Promise<LatestArtifactsResult> {
  const uniquePairs = Array.from(new Map(pairs.map((pair) => [pairKey(pair.searchTerm, pair.customLabel0), pair])).values())
  const pairSet = new Set(uniquePairs.map((pair) => pairKey(pair.searchTerm, pair.customLabel0)))
  const readChunkSize = 120

  if (uniquePairs.length === 0) {
    return { byPair: new Map<string, PairArtifacts>(), warnings: [] }
  }

  const supabase = createAdminClient()
  const warnings: string[] = []
  const intentRows: QueryIntentFeatureRow[] = []
  const valueRows: QueryValueScoreRow[] = []
  const recommendationRows: RoutingRecommendationRow[] = []

  const pairChunks = chunk(uniquePairs, readChunkSize)
  for (let index = 0; index < pairChunks.length; index += 1) {
    const pairChunk = pairChunks[index]
    const searchTerms = Array.from(new Set(pairChunk.map((pair) => pair.searchTerm)))
    const customLabels = Array.from(new Set(pairChunk.map((pair) => pair.customLabel0)))
    const maxRows = Math.max(pairChunk.length * 8, 250)

    const [intentResult, valueResult, recommendationResult] = await Promise.all([
      supabase
        .from('query_intent_features')
        .select('*')
        .in('search_term', searchTerms)
        .in('custom_label_0', customLabels)
        .order('created_at', { ascending: false })
        .limit(maxRows),
      supabase
        .from('query_value_scores')
        .select('*')
        .in('search_term', searchTerms)
        .in('custom_label_0', customLabels)
        .order('created_at', { ascending: false })
        .limit(maxRows),
      supabase
        .from('routing_recommendations')
        .select('*')
        .in('search_term', searchTerms)
        .in('custom_label_0', customLabels)
        .order('created_at', { ascending: false })
        .limit(maxRows),
    ])

    if (intentResult.error) {
      warnings.push(`query_intent_features lookup failed (chunk ${index + 1}/${pairChunks.length}): ${intentResult.error.message}`)
    } else {
      intentRows.push(...((intentResult.data ?? []) as QueryIntentFeatureRow[]))
    }

    if (valueResult.error) {
      warnings.push(`query_value_scores lookup failed (chunk ${index + 1}/${pairChunks.length}): ${valueResult.error.message}`)
    } else {
      valueRows.push(...((valueResult.data ?? []) as QueryValueScoreRow[]))
    }

    if (recommendationResult.error) {
      warnings.push(`routing_recommendations lookup failed (chunk ${index + 1}/${pairChunks.length}): ${recommendationResult.error.message}`)
    } else {
      recommendationRows.push(...((recommendationResult.data ?? []) as RoutingRecommendationRow[]))
    }
  }

  const intentByPair = latestByPair(intentRows, pairSet)
  const valueByPair = latestByPair(valueRows, pairSet)
  const recommendationByPair = latestByPair(recommendationRows, pairSet)

  const byPair = new Map<string, PairArtifacts>()
  for (const pair of uniquePairs) {
    const key = pairKey(pair.searchTerm, pair.customLabel0)
    byPair.set(key, {
      intentRow: intentByPair.get(key) ?? null,
      valueRow: valueByPair.get(key) ?? null,
      recommendationRow: recommendationByPair.get(key) ?? null,
    })
  }

  const coverage = summarizeCoverage(uniquePairs, byPair, {
    staleThresholdHours: DEFAULT_STALE_THRESHOLD_HOURS,
    versions,
  })

  if (coverage.cachedPairs < coverage.totalPairs && warnings.length === 0) {
    warnings.push(
      `Artifact cache incomplete for ${coverage.totalPairs - coverage.cachedPairs} of ${coverage.totalPairs} pairs.`
    )
  }

  return {
    byPair,
    warnings,
  }
}

export function hydrateArtifactFromRows(
  searchTerm: string,
  customLabel0: string,
  artifacts: PairArtifacts,
  versions: ArtifactVersionFilter = DECOMPOSITION_VERSIONS
): DecompositionArtifact | null {
  const { intentRow, valueRow, recommendationRow } = artifacts

  if (!intentRow || !valueRow || !recommendationRow) {
    return null
  }

  if (
    intentRow.parser_version !== versions.parserVersion ||
    valueRow.score_version !== versions.scoreVersion ||
    (recommendationRow.metadata as Record<string, unknown> | null)?.recommendation_version !==
      versions.recommendationVersion
  ) {
    return null
  }

  const intent: QueryIntentFeatures = {
    product_object: intentRow.product_object,
    modifier_tokens: intentRow.modifier_tokens ?? [],
    use_case_tokens: intentRow.use_case_tokens ?? [],
    is_branded: Boolean(intentRow.is_branded),
    is_competitor: Boolean(intentRow.is_competitor),
    has_mismatch_risk: Boolean(intentRow.has_mismatch_risk),
  }

  const recommendation: QueryRecommendation = {
    action_type: recommendationRow.recommended_action,
    default_tier: recommendationRow.recommended_tier ?? undefined,
    confidence: normalizeNumber(recommendationRow.confidence),
    reason_codes: recommendationRow.reason_codes ?? [],
  }

  const value: QueryValueScore = {
    impact_score: normalizeNumber(valueRow.impact_score),
    expected_clicks: normalizeNumber(valueRow.expected_clicks),
    expected_cvr: normalizeNumber(valueRow.expected_cvr),
    expected_conversion_value: normalizeNumber(valueRow.expected_conversion_value),
    expected_profit_proxy: normalizeNumber(valueRow.expected_profit_proxy),
    uncertainty: normalizeNumber(valueRow.uncertainty, 1),
  }

  const diagnostics = (intentRow.extracted as unknown as DecompositionArtifact['diagnostics'] | null) ?? {
    normalized_search_term: searchTerm,
    matched_tokens: {
      brand: [],
      competitor: [],
      product_object_candidates: [],
      modifier: [],
      use_case: [],
      risk: [],
    },
    selected_product_object: intent.product_object,
    ambiguity_flags: {
      multiple_product_objects: false,
    },
    confidence_components: {
      base: 0,
      product_object_bonus: 0,
      modifier_or_use_case_bonus: 0,
      explicit_brand_or_competitor_bonus: 0,
      ambiguity_penalty: 0,
      final: normalizeNumber(intentRow.confidence),
    },
  }

  return {
    searchTerm,
    customLabel0,
    parserVersion: intentRow.parser_version,
    scoreVersion: valueRow.score_version,
    recommendationVersion:
      String((recommendationRow.metadata as Record<string, unknown> | null)?.recommendation_version ??
        versions.recommendationVersion),
    intent,
    intentConfidence: normalizeNumber(intentRow.confidence),
    recommendation,
    value,
    diagnostics,
    modelInputs: (valueRow.model_inputs as Record<string, unknown>) ?? {},
    recommendationMetadata: (recommendationRow.metadata as Record<string, unknown>) ?? {},
  }
}

export async function insertArtifactsBatch(
  artifacts: DecompositionArtifact[],
  batchSize = DECOMPOSITION_BATCH_SIZE
): Promise<InsertArtifactsResult> {
  if (artifacts.length === 0) {
    return { insertedPairs: 0, warnings: [] }
  }

  const supabase = createAdminClient()
  const warnings: string[] = []
  let insertedPairs = 0

  for (const artifactBatch of chunk(artifacts, batchSize)) {
    const intentRows = artifactBatch.map((artifact) => ({
      search_term: artifact.searchTerm,
      custom_label_0: artifact.customLabel0,
      parser_version: artifact.parserVersion,
      product_object: artifact.intent.product_object,
      modifier_tokens: artifact.intent.modifier_tokens,
      use_case_tokens: artifact.intent.use_case_tokens,
      is_branded: artifact.intent.is_branded,
      is_competitor: artifact.intent.is_competitor,
      has_mismatch_risk: artifact.intent.has_mismatch_risk,
      confidence: artifact.intentConfidence,
      extracted: artifact.diagnostics,
    }))

    const valueRows = artifactBatch.map((artifact) => ({
      search_term: artifact.searchTerm,
      custom_label_0: artifact.customLabel0,
      score_version: artifact.scoreVersion,
      expected_clicks: artifact.value.expected_clicks,
      expected_cvr: artifact.value.expected_cvr,
      expected_conversion_value: artifact.value.expected_conversion_value,
      expected_profit_proxy: artifact.value.expected_profit_proxy,
      uncertainty: artifact.value.uncertainty,
      impact_score: artifact.value.impact_score,
      model_inputs: artifact.modelInputs,
    }))

    const recommendationRows = artifactBatch.map((artifact) => ({
      search_term: artifact.searchTerm,
      custom_label_0: artifact.customLabel0,
      recommended_action: artifact.recommendation.action_type,
      recommended_tier: artifact.recommendation.default_tier ?? null,
      reason_codes: artifact.recommendation.reason_codes,
      confidence: artifact.recommendation.confidence,
      review_status: 'pending',
      metadata: {
        ...artifact.recommendationMetadata,
        parser_version: artifact.parserVersion,
        score_version: artifact.scoreVersion,
        recommendation_version: artifact.recommendationVersion,
      },
    }))

    const [intentInsert, valueInsert, recommendationInsert] = await Promise.all([
      supabase.from('query_intent_features').insert(intentRows),
      supabase.from('query_value_scores').insert(valueRows),
      supabase.from('routing_recommendations').insert(recommendationRows),
    ])

    const batchErrors = [
      intentInsert.error
        ? `query_intent_features insert failed for ${artifactBatch.length} rows: ${intentInsert.error.message}`
        : null,
      valueInsert.error
        ? `query_value_scores insert failed for ${artifactBatch.length} rows: ${valueInsert.error.message}`
        : null,
      recommendationInsert.error
        ? `routing_recommendations insert failed for ${artifactBatch.length} rows: ${recommendationInsert.error.message}`
        : null,
    ].filter((value): value is string => Boolean(value))

    if (batchErrors.length > 0) {
      warnings.push(...batchErrors)
      continue
    }

    insertedPairs += artifactBatch.length
  }

  return {
    insertedPairs,
    warnings,
  }
}

export async function computeCoverageStats(
  pairs: PairIdentifier[],
  staleThresholdHours = DEFAULT_STALE_THRESHOLD_HOURS,
  versions: ArtifactVersionFilter = DECOMPOSITION_VERSIONS
): Promise<CoverageStats> {
  const latest = await getLatestArtifactsByPairs(pairs, versions)
  return summarizeCoverage(pairs, latest.byPair, {
    staleThresholdHours,
    versions,
  })
}
