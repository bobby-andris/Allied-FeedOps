import type {
  AssignmentTier,
  NeedsDecisionTerm,
  QueryIntentFeatures,
  QueryRecommendation,
  QueryValueScore,
} from '@/lib/shopping-funnel/types'

const BRAND_TOKENS = ['allied brass', 'alliedbrass', 'avd']

const COMPETITOR_TOKENS = [
  'signature hardware',
  'kingston brass',
  'moen',
  'delta',
  'kohler',
  'pfister',
  'american standard',
  'brizo',
  'hansgrohe',
  'grohe',
  'rohl',
  'newport brass',
  'california faucets',
  'gatco',
  'elements of design',
]

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

const MODIFIER_HINTS = [
  'wall mount',
  'freestanding',
  'double',
  'single',
  'triple',
  'recessed',
  'reserve',
  'rollerless',
  'ada',
  'commercial',
  'solid brass',
  'heavy duty',
  'matte',
  'polished',
  'satin',
  'chrome',
  'nickel',
  'bronze',
]

const USE_CASE_HINTS = [
  'bathroom',
  'kitchen',
  'guest',
  'powder room',
  'shower',
  'vanity',
  'commercial',
  'hotel',
  'rv',
]

const HIGH_INTENT_TOKENS = ['buy', 'shop', 'best', 'for sale', 'near me', 'wall mounted']

const NEGATIVE_RISK_TOKENS = ['replacement part', 'repair', 'used', 'diy', 'free', 'cheap']

function tokenizePhraseSet(searchTerm: string, candidates: string[]): string[] {
  const term = searchTerm.toLowerCase()
  return candidates.filter((candidate) => term.includes(candidate))
}

function normalizeConfidence(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.min(1, value))
}

export function decomposeSearchTerm(searchTerm: string): QueryIntentFeatures {
  const normalized = searchTerm.toLowerCase().trim()
  const productMatches = tokenizePhraseSet(normalized, PRODUCT_OBJECT_HINTS)
  const modifierMatches = tokenizePhraseSet(normalized, MODIFIER_HINTS)
  const useCaseMatches = tokenizePhraseSet(normalized, USE_CASE_HINTS)
  const brandMatches = tokenizePhraseSet(normalized, BRAND_TOKENS)
  const competitorMatches = tokenizePhraseSet(normalized, COMPETITOR_TOKENS)
  const riskMatches = tokenizePhraseSet(normalized, NEGATIVE_RISK_TOKENS)

  return {
    product_object: productMatches[0] ?? null,
    modifier_tokens: modifierMatches,
    use_case_tokens: useCaseMatches,
    is_branded: brandMatches.length > 0,
    is_competitor: competitorMatches.length > 0,
    has_mismatch_risk: riskMatches.length > 0,
  }
}

function estimateTierFromMetrics({
  clicks,
  conversions,
  costMicros,
  conversionsValue,
  intentFeatures,
}: {
  clicks: number
  conversions: number
  costMicros: number
  conversionsValue: number
  intentFeatures: QueryIntentFeatures
}): AssignmentTier {
  const safeClicks = Math.max(clicks, 1)
  const cost = costMicros / 1_000_000
  const cvr = conversions / safeClicks
  const roas = cost > 0 ? conversionsValue / cost : 0

  const termHasHighIntentToken = HIGH_INTENT_TOKENS.some((token) =>
    `${intentFeatures.product_object ?? ''} ${intentFeatures.modifier_tokens.join(' ')}`.includes(token)
  )

  if (roas >= 3.6 || cvr >= 0.05 || termHasHighIntentToken) {
    return 'low'
  }
  if (roas >= 3.1 || cvr >= 0.03) {
    return 'medium'
  }
  return 'high'
}

function recommendActionForTerm(
  term: NeedsDecisionTerm,
  intentFeatures: QueryIntentFeatures
): QueryRecommendation {
  if (intentFeatures.is_branded) {
    return {
      action_type: 'branded',
      confidence: 0.96,
      reason_codes: ['brand_token_detected'],
    }
  }

  if (intentFeatures.is_competitor) {
    return {
      action_type: 'competitor',
      confidence: 0.9,
      reason_codes: ['competitor_token_detected'],
    }
  }

  if (intentFeatures.has_mismatch_risk) {
    return {
      action_type: 'global_block',
      confidence: 0.78,
      reason_codes: ['negative_risk_token_detected'],
    }
  }

  const aggregate = term.custom_label_0s.reduce(
    (acc, item) => {
      acc.clicks += item.clicks
      acc.conversions += item.conversions
      acc.costMicros += item.cost_micros
      acc.conversionsValue += item.conversions_value
      return acc
    },
    {
      clicks: 0,
      conversions: 0,
      costMicros: 0,
      conversionsValue: 0,
    }
  )

  const defaultTier = estimateTierFromMetrics({
    clicks: aggregate.clicks,
    conversions: aggregate.conversions,
    costMicros: aggregate.costMicros,
    conversionsValue: aggregate.conversionsValue,
    intentFeatures,
  })

  const confidenceBase =
    0.55 +
    Math.min(term.custom_label_0s.length, 5) * 0.03 +
    Math.min(aggregate.clicks, 200) / 2000 +
    Math.min(aggregate.conversions, 20) / 100

  return {
    action_type: 'funnel',
    default_tier: defaultTier,
    confidence: normalizeConfidence(confidenceBase),
    reason_codes: ['performance_weighted_tiering', 'funnel_default'],
  }
}

function scoreNeedsDecisionTerm(term: NeedsDecisionTerm): QueryValueScore {
  const totals = term.custom_label_0s.reduce(
    (acc, item) => {
      acc.impressions += item.impressions
      acc.clicks += item.clicks
      acc.costMicros += item.cost_micros
      acc.conversions += item.conversions
      acc.conversionsValue += item.conversions_value
      return acc
    },
    {
      impressions: 0,
      clicks: 0,
      costMicros: 0,
      conversions: 0,
      conversionsValue: 0,
    }
  )

  const safeClicks = Math.max(totals.clicks, 1)
  const cost = totals.costMicros / 1_000_000
  const cvr = totals.conversions / safeClicks
  const ctr = totals.impressions > 0 ? totals.clicks / totals.impressions : 0
  const conversionValuePerClick = totals.conversionsValue / safeClicks
  const expectedClicks = Math.max(totals.clicks, totals.impressions * Math.max(ctr, 0.01))
  const expectedConversionValue = expectedClicks * conversionValuePerClick
  const expectedProfitProxy = expectedConversionValue - cost
  const confidence = Math.min(totals.clicks / 50, 1)
  const uncertainty = 1 - confidence
  const impactScore = expectedProfitProxy * (1 - uncertainty * 0.5)

  return {
    impact_score: Number(impactScore.toFixed(2)),
    expected_clicks: Number(expectedClicks.toFixed(2)),
    expected_cvr: Number(cvr.toFixed(4)),
    expected_conversion_value: Number(expectedConversionValue.toFixed(2)),
    expected_profit_proxy: Number(expectedProfitProxy.toFixed(2)),
    uncertainty: Number(uncertainty.toFixed(4)),
  }
}

export function enrichNeedsDecisionTerm(term: NeedsDecisionTerm): NeedsDecisionTerm {
  const intentFeatures = decomposeSearchTerm(term.search_term)
  const recommendation = recommendActionForTerm(term, intentFeatures)
  const valueScore = scoreNeedsDecisionTerm(term)

  return {
    ...term,
    intent_features: intentFeatures,
    recommendation,
    value_score: valueScore,
  }
}

