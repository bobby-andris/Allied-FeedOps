import type {
  QueryIntentFeatures,
  QueryRecommendation,
  QueryValueScore,
  SearchTermSourceAssignment,
} from '@/lib/shopping-funnel/types'
import type {
  QueryIntentFeatureRow,
  QueryValueScoreRow,
  RoutingRecommendationRow,
} from '@/lib/supabase/types'

export interface DecompositionVersions {
  parserVersion: string
  scoreVersion: string
  recommendationVersion: string
}

export interface DecompositionPairInput {
  searchTerm: string
  customLabel0: string
  assignment: SearchTermSourceAssignment
  labelCount: number
  valueScoringContext?: ValueScoringContext
}

export interface ValueMetricStats {
  impressions: number
  clicks: number
  conversions: number
  cost: number
  conversionValue: number
  ctr: number
  cvr: number
  cpc: number
  valuePerConversion: number
  valuePerClick: number
}

export interface ValueScoringContext {
  global: ValueMetricStats
  byTier: Partial<Record<string, ValueMetricStats>>
  byLabel: Map<string, ValueMetricStats>
  byLabelTier: Map<string, ValueMetricStats>
}

export interface PairValueScoreResult {
  value: QueryValueScore
  modelInputs: Record<string, unknown>
}

export interface DecompositionDiagnostics {
  normalized_search_term: string
  matched_tokens: {
    brand: string[]
    competitor: string[]
    product_object_candidates: string[]
    modifier: string[]
    use_case: string[]
    risk: string[]
  }
  selected_product_object: string | null
  ambiguity_flags: {
    multiple_product_objects: boolean
  }
  confidence_components: {
    base: number
    product_object_bonus: number
    modifier_or_use_case_bonus: number
    explicit_brand_or_competitor_bonus: number
    ambiguity_penalty: number
    final: number
  }
}

export interface DecompositionArtifact {
  searchTerm: string
  customLabel0: string
  parserVersion: string
  scoreVersion: string
  recommendationVersion: string
  intent: QueryIntentFeatures
  intentConfidence: number
  recommendation: QueryRecommendation
  value: QueryValueScore
  diagnostics: DecompositionDiagnostics
  modelInputs: Record<string, unknown>
  recommendationMetadata: Record<string, unknown>
}

export interface PairArtifacts {
  intentRow: QueryIntentFeatureRow | null
  valueRow: QueryValueScoreRow | null
  recommendationRow: RoutingRecommendationRow | null
}

export interface LatestArtifactsResult {
  byPair: Map<string, PairArtifacts>
  warnings: string[]
}

export interface PairCoverageDetail {
  pairKey: string
  hasIntent: boolean
  hasValue: boolean
  hasRecommendation: boolean
  allPresent: boolean
  isStale: boolean
}

export interface CoverageStats {
  totalPairs: number
  cachedPairs: number
  missingPairs: number
  stalePairs: number
  staleShare: number
  coveragePercent: number
  latestCreatedAt: string | null
  details: PairCoverageDetail[]
}

export interface InsertArtifactsResult {
  insertedPairs: number
  warnings: string[]
}

export interface PipelineRunResult {
  artifactsByPair: Map<string, DecompositionArtifact>
  pairsTotal: number
  pairsCached: number
  pairsRecomputed: number
  warnings: string[]
  versions: DecompositionVersions
  staleThresholdHours: number
  latestArtifactCreatedAt: string | null
}

export function pairKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}||${customLabel0}`
}
