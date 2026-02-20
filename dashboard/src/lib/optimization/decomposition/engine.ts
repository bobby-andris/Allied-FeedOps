import type {
  AssignmentTier,
  QueryIntentFeatures,
  QueryRecommendation,
  QueryValueScore,
  SearchTermSourceAssignment,
} from '@/lib/shopping-funnel/types'
import {
  BASE_FUNNEL_CONFIDENCE,
  BASE_INTENT_CONFIDENCE,
  BASELINE_TARGET_ROAS_BY_TIER,
  BRAND_TOKENS,
  COMPETITOR_TOKENS,
  DECOMPOSITION_VERSIONS,
  HIGH_INTENT_TOKENS,
  INTENT_CONFIDENCE_BONUS,
  MODIFIER_HINTS,
  NEGATIVE_RISK_TOKENS,
  PRODUCT_OBJECT_HINTS,
  USE_CASE_HINTS,
} from '@/lib/optimization/decomposition/config'
import {
  createValueScoringContext,
  scorePairValueWithContext,
} from '@/lib/optimization/decomposition/value-scoring'
import type {
  DecompositionArtifact,
  DecompositionDiagnostics,
  DecompositionPairInput,
  ValueScoringContext,
} from '@/lib/optimization/decomposition/types'

function tokenizePhraseSet(searchTerm: string, candidates: string[]): string[] {
  return candidates.filter((candidate) => searchTerm.includes(candidate))
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min
  }
  return Math.max(min, Math.min(max, value))
}

export function normalizeSearchTermValue(value: string): string {
  return value.toLowerCase().trim().replace(/\s+/g, ' ')
}

function selectProductObject(productCandidates: string[]): string | null {
  if (productCandidates.length === 0) {
    return null
  }

  const ordered = [...productCandidates].sort(
    (a, b) => PRODUCT_OBJECT_HINTS.indexOf(a) - PRODUCT_OBJECT_HINTS.indexOf(b)
  )

  return ordered[0] ?? null
}

export function decomposeSearchTermIntent(searchTerm: string): {
  intent: QueryIntentFeatures
  intentConfidence: number
  diagnostics: DecompositionDiagnostics
} {
  const normalized = normalizeSearchTermValue(searchTerm)

  const productCandidates = tokenizePhraseSet(normalized, PRODUCT_OBJECT_HINTS)
  const modifierMatches = tokenizePhraseSet(normalized, MODIFIER_HINTS)
  const useCaseMatches = tokenizePhraseSet(normalized, USE_CASE_HINTS)
  const brandMatches = tokenizePhraseSet(normalized, BRAND_TOKENS)
  const competitorMatches = tokenizePhraseSet(normalized, COMPETITOR_TOKENS)
  const riskMatches = tokenizePhraseSet(normalized, NEGATIVE_RISK_TOKENS)

  const selectedProductObject = selectProductObject(productCandidates)

  const isBranded = brandMatches.length > 0
  const isCompetitor = competitorMatches.length > 0
  const hasMismatchRisk = riskMatches.length > 0
  const hasModifierOrUseCase = modifierMatches.length > 0 || useCaseMatches.length > 0
  const hasExplicitBrandOrCompetitor = isBranded || isCompetitor
  const hasAmbiguousObject = productCandidates.length > 1

  const confidenceComponents = {
    base: BASE_INTENT_CONFIDENCE,
    product_object_bonus: selectedProductObject ? INTENT_CONFIDENCE_BONUS.productObject : 0,
    modifier_or_use_case_bonus: hasModifierOrUseCase ? INTENT_CONFIDENCE_BONUS.modifierOrUseCase : 0,
    explicit_brand_or_competitor_bonus: hasExplicitBrandOrCompetitor
      ? INTENT_CONFIDENCE_BONUS.explicitBrandOrCompetitor
      : 0,
    ambiguity_penalty: hasAmbiguousObject ? INTENT_CONFIDENCE_BONUS.ambiguityPenalty : 0,
    final: 0,
  }

  const intentConfidence = clamp(
    confidenceComponents.base +
      confidenceComponents.product_object_bonus +
      confidenceComponents.modifier_or_use_case_bonus +
      confidenceComponents.explicit_brand_or_competitor_bonus -
      confidenceComponents.ambiguity_penalty,
    0.05,
    0.99
  )

  confidenceComponents.final = Number(intentConfidence.toFixed(4))

  const intent: QueryIntentFeatures = {
    product_object: selectedProductObject,
    modifier_tokens: modifierMatches,
    use_case_tokens: useCaseMatches,
    is_branded: isBranded,
    is_competitor: isCompetitor,
    has_mismatch_risk: hasMismatchRisk,
  }

  const diagnostics: DecompositionDiagnostics = {
    normalized_search_term: normalized,
    matched_tokens: {
      brand: brandMatches,
      competitor: competitorMatches,
      product_object_candidates: productCandidates,
      modifier: modifierMatches,
      use_case: useCaseMatches,
      risk: riskMatches,
    },
    selected_product_object: selectedProductObject,
    ambiguity_flags: {
      multiple_product_objects: hasAmbiguousObject,
    },
    confidence_components: confidenceComponents,
  }

  return {
    intent,
    intentConfidence: Number(intentConfidence.toFixed(4)),
    diagnostics,
  }
}

function estimateTierFromAssignment(
  assignment: SearchTermSourceAssignment,
  normalizedSearchTerm: string,
  intent: QueryIntentFeatures
): Extract<AssignmentTier, 'high' | 'medium' | 'low'> {
  const safeClicks = Math.max(assignment.clicks, 1)
  const cost = assignment.cost_micros / 1_000_000
  const cvr = assignment.conversions / safeClicks
  const roas = cost > 0 ? assignment.conversions_value / cost : 0
  const hasHighIntentToken = HIGH_INTENT_TOKENS.some((token) => normalizedSearchTerm.includes(token))

  if (roas >= BASELINE_TARGET_ROAS_BY_TIER.high || cvr >= 0.05 || hasHighIntentToken || intent.is_branded) {
    return 'low'
  }

  if (roas >= BASELINE_TARGET_ROAS_BY_TIER.medium || cvr >= 0.03) {
    return 'medium'
  }

  return 'high'
}

export function recommendActionForPair(
  searchTerm: string,
  assignment: SearchTermSourceAssignment,
  labelCount: number,
  intent: QueryIntentFeatures
): QueryRecommendation {
  const normalized = normalizeSearchTermValue(searchTerm)

  if (intent.is_branded) {
    return {
      action_type: 'branded',
      confidence: 0.96,
      reason_codes: ['brand_token_detected'],
    }
  }

  if (intent.is_competitor) {
    return {
      action_type: 'competitor',
      confidence: 0.9,
      reason_codes: ['competitor_token_detected'],
    }
  }

  if (intent.has_mismatch_risk) {
    return {
      action_type: 'global_block',
      confidence: 0.78,
      reason_codes: ['negative_risk_token_detected'],
    }
  }

  const defaultTier = estimateTierFromAssignment(assignment, normalized, intent)
  const confidence = clamp(
    BASE_FUNNEL_CONFIDENCE +
      Math.min(assignment.clicks, 200) / 2000 +
      Math.min(assignment.conversions, 20) / 100 +
      Math.min(labelCount, 5) * 0.03,
    0.05,
    0.99
  )

  return {
    action_type: 'funnel',
    default_tier: defaultTier,
    confidence: Number(confidence.toFixed(4)),
    reason_codes: ['performance_weighted_tiering', 'funnel_default'],
  }
}

export function scorePairValue(
  assignment: SearchTermSourceAssignment,
  customLabel0: string,
  context?: ValueScoringContext
): QueryValueScore {
  return scorePairValueWithContext(assignment, customLabel0, context).value
}

export function scoreTermAggregate(assignments: SearchTermSourceAssignment[]): QueryValueScore {
  const totals = assignments.reduce(
    (acc, assignment) => {
      acc.impressions += assignment.impressions
      acc.clicks += assignment.clicks
      acc.costMicros += assignment.cost_micros
      acc.conversions += assignment.conversions
      acc.conversionsValue += assignment.conversions_value
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

export function scoreTermFromPairValues(values: QueryValueScore[]): QueryValueScore {
  if (values.length === 0) {
    return {
      impact_score: 0,
      expected_clicks: 0,
      expected_cvr: 0,
      expected_conversion_value: 0,
      expected_profit_proxy: 0,
      uncertainty: 1,
    }
  }

  const totals = values.reduce(
    (acc, value) => {
      const clicks = Math.max(value.expected_clicks, 0)
      acc.expectedClicks += clicks
      acc.weightedCvr += clicks * Math.max(value.expected_cvr, 0)
      acc.expectedConversionValue += Math.max(value.expected_conversion_value, 0)
      acc.expectedProfitProxy += value.expected_profit_proxy
      acc.weightedUncertainty += clicks * clamp(value.uncertainty, 0, 1)
      acc.impactScore += value.impact_score
      return acc
    },
    {
      expectedClicks: 0,
      weightedCvr: 0,
      expectedConversionValue: 0,
      expectedProfitProxy: 0,
      weightedUncertainty: 0,
      impactScore: 0,
    }
  )

  const expectedClicks = totals.expectedClicks
  const expectedCvr = expectedClicks > 0 ? totals.weightedCvr / expectedClicks : 0
  const uncertainty = expectedClicks > 0 ? totals.weightedUncertainty / expectedClicks : 1

  return {
    impact_score: Number(totals.impactScore.toFixed(2)),
    expected_clicks: Number(expectedClicks.toFixed(2)),
    expected_cvr: Number(expectedCvr.toFixed(4)),
    expected_conversion_value: Number(totals.expectedConversionValue.toFixed(2)),
    expected_profit_proxy: Number(totals.expectedProfitProxy.toFixed(2)),
    uncertainty: Number(uncertainty.toFixed(4)),
  }
}

export function computeDecompositionArtifact(input: DecompositionPairInput): DecompositionArtifact {
  const { intent, intentConfidence, diagnostics } = decomposeSearchTermIntent(input.searchTerm)
  const recommendation = recommendActionForPair(
    input.searchTerm,
    input.assignment,
    input.labelCount,
    intent
  )
  const valueScoring = scorePairValueWithContext(
    input.assignment,
    input.customLabel0,
    input.valueScoringContext
  )

  return {
    searchTerm: input.searchTerm,
    customLabel0: input.customLabel0,
    parserVersion: DECOMPOSITION_VERSIONS.parserVersion,
    scoreVersion: DECOMPOSITION_VERSIONS.scoreVersion,
    recommendationVersion: DECOMPOSITION_VERSIONS.recommendationVersion,
    intent,
    intentConfidence,
    recommendation,
    value: valueScoring.value,
    diagnostics,
    modelInputs: {
      impressions: input.assignment.impressions,
      clicks: input.assignment.clicks,
      cost_micros: input.assignment.cost_micros,
      conversions: input.assignment.conversions,
      conversions_value: input.assignment.conversions_value,
      label_count: input.labelCount,
      ...valueScoring.modelInputs,
    },
    recommendationMetadata: {
      source_campaign: input.assignment.source_campaign,
      source_tier: input.assignment.source_tier,
      versions: DECOMPOSITION_VERSIONS,
    },
  }
}

export { createValueScoringContext }
