import type { IntentClass, SearchTier } from '@/lib/intent/types'

const PRODUCT_OBJECT_HINTS = [
  'towel bar',
  'towel ring',
  'soap dish',
  'soap dispenser',
  'toothbrush holder',
  'toilet paper holder',
  'tp holder',
  'grab bar',
  'glass shelf',
  'robe hook',
  'mirror',
  'paper towel holder',
  'shower door pull',
  'shower squeegee',
  'basket',
  'shelf',
]

const INTENT_CAMPAIGN_SEGMENT: Record<IntentClass, string> = {
  BRAND_CORE: 'Brand',
  PRODUCT_HIGH: 'Product High',
  CATEGORY_MID: 'Category Mid',
  DISCOVERY_LOW: 'Discovery',
  COMPETITOR: 'Competitor',
  INFO_ASSIST: 'Info Assist',
  MISMATCH: 'Risk Holdout',
  RISK_POLICY: 'Risk Holdout',
}

const INTENT_PRIORITY_BONUS: Record<IntentClass, number> = {
  BRAND_CORE: 8,
  PRODUCT_HIGH: 14,
  CATEGORY_MID: 9,
  DISCOVERY_LOW: 3,
  COMPETITOR: 5,
  INFO_ASSIST: 2,
  MISMATCH: -12,
  RISK_POLICY: -10,
}

const TIER_PRIORITY_BONUS: Record<SearchTier, number> = {
  exact: 18,
  phrase: 10,
  broad: 4,
}

const TIER_LABEL: Record<SearchTier, string> = {
  broad: 'Broad',
  phrase: 'Phrase',
  exact: 'Exact',
}

export interface SearchBuildoutSuggestion {
  cluster_key: string
  suggested_campaign: string
  suggested_ad_group: string
  recommended_tier: SearchTier
  confidence: number
  priority_score: number
  intent_class: IntentClass
  reason_codes: string[]
  top_term: string
  seed_negatives: string[]
}

export interface SearchBuildoutClusterSummary {
  cluster_key: string
  suggested_campaign: string
  suggested_ad_group: string
  recommended_tier: SearchTier
  candidate_count: number
  avg_confidence: number
  avg_priority_score: number
  intent_classes: IntentClass[]
  top_terms: string[]
}

export interface SearchBuildoutInput {
  searchTerm: string
  intentClass: IntentClass
  recommendedTier: SearchTier
  confidence: number
  reasonCodes: string[]
}

function normalizeConfidence(value: number): number {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(1, numeric))
}

function toTitleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => token.slice(0, 1).toUpperCase() + token.slice(1))
    .join(' ')
}

function normalizeQuery(value: string): string {
  return value.toLowerCase().trim().replace(/\s+/g, ' ')
}

function deriveClusterKey(searchTerm: string): string {
  const normalized = normalizeQuery(searchTerm)
  const directMatch = PRODUCT_OBJECT_HINTS.find((hint) => normalized.includes(hint))
  if (directMatch) {
    return directMatch
  }

  const tokens = normalized.split(' ').filter(Boolean)
  if (tokens.length === 0) {
    return 'uncategorized'
  }

  return tokens.slice(0, Math.min(2, tokens.length)).join(' ')
}

function deriveSeedNegatives(clusterKey: string, term: string): string[] {
  const normalizedCluster = clusterKey.trim()
  const normalizedTerm = normalizeQuery(term)
  return [
    `${normalizedCluster} broad`,
    `${normalizedCluster} phrase`,
    `${normalizedTerm} broad`,
  ]
}

export function buildSearchBuildoutSuggestion(input: SearchBuildoutInput): SearchBuildoutSuggestion {
  const clusterKey = deriveClusterKey(input.searchTerm)
  const clusterTitle = toTitleCase(clusterKey)
  const campaignSegment = INTENT_CAMPAIGN_SEGMENT[input.intentClass] ?? 'Mixed Intent'
  const safeConfidence = normalizeConfidence(input.confidence)

  const basePriority = safeConfidence * 70
  const priorityScore = Math.max(
    0,
    Number(
      (
        basePriority +
        TIER_PRIORITY_BONUS[input.recommendedTier] +
        INTENT_PRIORITY_BONUS[input.intentClass]
      ).toFixed(2)
    )
  )

  return {
    cluster_key: clusterKey,
    suggested_campaign: `Search | ${campaignSegment} | ${clusterTitle}`,
    suggested_ad_group: `${clusterTitle} | ${TIER_LABEL[input.recommendedTier]}`,
    recommended_tier: input.recommendedTier,
    confidence: safeConfidence,
    priority_score: priorityScore,
    intent_class: input.intentClass,
    reason_codes: input.reasonCodes,
    top_term: input.searchTerm,
    seed_negatives: deriveSeedNegatives(clusterKey, input.searchTerm),
  }
}

export function summarizeSearchBuildoutClusters(
  suggestions: SearchBuildoutSuggestion[],
  limit = 20
): SearchBuildoutClusterSummary[] {
  const byCluster = new Map<
    string,
    {
      campaign: string
      adGroup: string
      tier: SearchTier
      confidences: number[]
      priorities: number[]
      intents: Set<IntentClass>
      topTerms: string[]
    }
  >()

  for (const suggestion of suggestions) {
    const current = byCluster.get(suggestion.cluster_key) ?? {
      campaign: suggestion.suggested_campaign,
      adGroup: suggestion.suggested_ad_group,
      tier: suggestion.recommended_tier,
      confidences: [],
      priorities: [],
      intents: new Set<IntentClass>(),
      topTerms: [],
    }

    current.confidences.push(suggestion.confidence)
    current.priorities.push(suggestion.priority_score)
    current.intents.add(suggestion.intent_class)
    if (!current.topTerms.includes(suggestion.top_term)) {
      current.topTerms.push(suggestion.top_term)
    }
    byCluster.set(suggestion.cluster_key, current)
  }

  return Array.from(byCluster.entries())
    .map(([clusterKey, value]) => ({
      cluster_key: clusterKey,
      suggested_campaign: value.campaign,
      suggested_ad_group: value.adGroup,
      recommended_tier: value.tier,
      candidate_count: value.priorities.length,
      avg_confidence: Number(
        (
          value.confidences.reduce((acc, confidence) => acc + confidence, 0) /
          Math.max(value.confidences.length, 1)
        ).toFixed(4)
      ),
      avg_priority_score: Number(
        (
          value.priorities.reduce((acc, priority) => acc + priority, 0) /
          Math.max(value.priorities.length, 1)
        ).toFixed(2)
      ),
      intent_classes: Array.from(value.intents),
      top_terms: value.topTerms.slice(0, 10),
    }))
    .sort((a, b) => b.avg_priority_score - a.avg_priority_score)
    .slice(0, Math.max(1, limit))
}
