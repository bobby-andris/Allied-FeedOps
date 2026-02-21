import type { AssignmentTier } from '@/lib/shopping-funnel/types'
import {
  type BidPolicyDecision,
  type BidPolicyInput,
  type GuardrailDecision,
  type GuardrailInput,
  INTENT_POLICY_VERSION,
  type IntentDecisionInput,
  type IntentRouteDecision,
  type PromotionDemotionDecision,
  type PromotionDemotionInput,
  type ShoppingToSearchGraduationDecision,
  type ShoppingToSearchGraduationInput,
  type SearchGovernanceDecision,
  type SearchGovernanceInput,
} from '@/lib/intent/types'
import { classifyIntent } from '@/lib/intent/taxonomy'
import { sanitizeTermMetrics, validateDecisionInput, validateBidPolicyInput } from '@/lib/intent/input-validation'

const PROMOTION_THRESHOLDS = {
  lowToMedium: {
    minClicks: 80,
    minConversions: 3,
    marginRoasFloor: 3.1 * 1.1,
    confidence: 0.6,
  },
  mediumToHigh: {
    minClicks: 120,
    minConversions: 6,
    marginRoasFloor: 3.6 * 1.15,
    confidence: 0.7,
  },
  demotionFloorMultiplier: 0.85,
  demotionConfidenceFloor: 0.5,
}

const TARGET_ROAS_BY_TIER: Record<Exclude<AssignmentTier, 'campaign_negative'>, number> = {
  high: 3.6,
  medium: 3.1,
  low: 2.6,
}

function normalizeConfidence(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.min(1, value))
}

function resolveValueSignalScore(value: number | undefined): number {
  if (value == null) {
    return 0.65
  }
  return normalizeConfidence(value)
}

function applyValueSignalToConfidence(baseConfidence: number, valueSignalScore: number | undefined): number {
  const score = resolveValueSignalScore(valueSignalScore)
  const multiplier = 0.75 + score * 0.25
  return normalizeConfidence(baseConfidence * multiplier)
}

function safeObservedRoas(costMicros: number, conversionValue: number): number {
  if (costMicros <= 0) return 0
  return conversionValue / (costMicros / 1_000_000)
}

function boundedRoasRecommendation(current: number, next: number): number {
  const lower = current * 0.9
  const upper = current * 1.1
  return Math.max(lower, Math.min(upper, next))
}

function boundedCpaRecommendation(current: number, next: number): number {
  const lower = current * 0.9
  const upper = current * 1.1
  return Math.max(lower, Math.min(upper, next))
}

function inferConfidence(input: IntentDecisionInput): number {
  const clickConfidence = Math.min(input.metrics.clicks / 200, 1)
  const conversionConfidence = Math.min(input.metrics.conversions / 10, 1)
  const attributionConfidence =
    input.attributionQualityScore == null
      ? 0.7
      : Math.max(0.2, Math.min(1, input.attributionQualityScore))
  const valueSignalScore = resolveValueSignalScore(input.valueSignalScore)

  return normalizeConfidence(
    clickConfidence * 0.4 +
      conversionConfidence * 0.3 +
      attributionConfidence * 0.2 +
      valueSignalScore * 0.1
  )
}

export function routeIntentDecision(raw: IntentDecisionInput): IntentRouteDecision {
  const validated = validateDecisionInput(raw)
  const input = validated.valid ? validated.value : raw
  const classification = classifyIntent(input.searchTerm)
  const confidence = inferConfidence(input)
  const requiresReview = confidence < 0.75

  const reasonCodes = [...classification.reasonCodes]

  switch (classification.intentClass) {
    case 'BRAND_CORE':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'branded',
        confidence,
        requiresReview,
        reasonCodes: [...reasonCodes, 'route_branded'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'COMPETITOR':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'competitor',
        confidence,
        requiresReview: true,
        reasonCodes: [...reasonCodes, 'route_competitor_isolated'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'MISMATCH':
    case 'RISK_POLICY':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'global_block',
        confidence,
        requiresReview: classification.intentClass === 'RISK_POLICY',
        reasonCodes: [...reasonCodes, 'route_global_block'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'INFO_ASSIST':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'search_discovery',
        confidence,
        requiresReview: true,
        reasonCodes: [...reasonCodes, 'route_info_to_search_discovery'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'PRODUCT_HIGH':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'funnel',
        recommendedTier: 'high',
        confidence,
        requiresReview,
        reasonCodes: [...reasonCodes, 'route_shopping_high'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'CATEGORY_MID':
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'funnel',
        recommendedTier: 'medium',
        confidence,
        requiresReview,
        reasonCodes: [...reasonCodes, 'route_shopping_medium'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    case 'DISCOVERY_LOW':
    default:
      return {
        searchTerm: input.searchTerm,
        classification,
        routeAction: 'funnel',
        recommendedTier: 'low',
        confidence,
        requiresReview,
        reasonCodes: [...reasonCodes, 'route_shopping_low'],
        policyVersion: INTENT_POLICY_VERSION,
      }
  }
}

export function evaluatePromotionDemotion(raw: PromotionDemotionInput): PromotionDemotionDecision {
  const metricsResult = sanitizeTermMetrics(raw.metrics)
  const input: PromotionDemotionInput = { ...raw, metrics: metricsResult.value }
  const observedRoas = input.marginRoas ?? safeObservedRoas(input.metrics.costMicros, input.metrics.conversionsValue)
  const confidence = applyValueSignalToConfidence(normalizeConfidence(input.confidence), input.valueSignalScore)
  const reasonCodes: string[] = ['promotion_policy_v1']

  if (input.metrics.costMicros >= 20_000_000 && input.metrics.conversions <= 0 && confidence >= 0.55) {
    return {
      searchTerm: input.searchTerm,
      action: 'negative',
      confidence,
      reasonCodes: [...reasonCodes, 'high_spend_zero_conversion'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (input.currentTier === 'low') {
    const threshold = PROMOTION_THRESHOLDS.lowToMedium
    if (
      input.metrics.clicks >= threshold.minClicks &&
      input.metrics.conversions >= threshold.minConversions &&
      observedRoas >= threshold.marginRoasFloor &&
      confidence >= threshold.confidence
    ) {
      return {
        searchTerm: input.searchTerm,
        action: 'promote_to_medium',
        confidence,
        reasonCodes: [...reasonCodes, 'low_to_medium_threshold_met'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }
  }

  if (input.currentTier === 'medium') {
    const threshold = PROMOTION_THRESHOLDS.mediumToHigh
    if (
      input.metrics.clicks >= threshold.minClicks &&
      input.metrics.conversions >= threshold.minConversions &&
      observedRoas >= threshold.marginRoasFloor &&
      confidence >= threshold.confidence
    ) {
      return {
        searchTerm: input.searchTerm,
        action: 'promote_to_high',
        confidence,
        reasonCodes: [...reasonCodes, 'medium_to_high_threshold_met'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }
  }

  if (input.currentTier === 'high') {
    const floor = TARGET_ROAS_BY_TIER.high * PROMOTION_THRESHOLDS.demotionFloorMultiplier
    if (observedRoas < floor || confidence < PROMOTION_THRESHOLDS.demotionConfidenceFloor) {
      return {
        searchTerm: input.searchTerm,
        action: 'demote_to_medium',
        confidence,
        reasonCodes: [...reasonCodes, 'high_tier_efficiency_decline'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }
  }

  if (input.currentTier === 'medium') {
    const floor = TARGET_ROAS_BY_TIER.medium * PROMOTION_THRESHOLDS.demotionFloorMultiplier
    if (observedRoas < floor || confidence < PROMOTION_THRESHOLDS.demotionConfidenceFloor) {
      return {
        searchTerm: input.searchTerm,
        action: 'demote_to_low',
        confidence,
        reasonCodes: [...reasonCodes, 'medium_tier_efficiency_decline'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }
  }

  return {
    searchTerm: input.searchTerm,
    action: 'hold',
    confidence,
    reasonCodes: [...reasonCodes, 'no_threshold_breach'],
    policyVersion: INTENT_POLICY_VERSION,
  }
}

export function evaluateSearchGovernance(raw: SearchGovernanceInput): SearchGovernanceDecision {
  const metricsResult = sanitizeTermMetrics(raw.metrics)
  const input: SearchGovernanceInput = { ...raw, metrics: metricsResult.value }
  const confidence = normalizeConfidence(input.confidence)
  const reasonCodes = [...input.classification.reasonCodes, 'search_governance_v1']
  const observedRoas = safeObservedRoas(input.metrics.costMicros, input.metrics.conversionsValue)

  if (input.classification.intentClass === 'MISMATCH' || input.classification.intentClass === 'RISK_POLICY') {
    return {
      searchTerm: input.searchTerm,
      action: 'exclude',
      recommendedTier: null,
      confidence,
      reasonCodes: [...reasonCodes, 'exclude_non_commercial_intent'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (input.currentTier === 'broad' && confidence >= 0.6 && input.metrics.conversions >= 2) {
    return {
      searchTerm: input.searchTerm,
      action: 'promote_to_phrase',
      recommendedTier: 'phrase',
      confidence,
      reasonCodes: [...reasonCodes, 'broad_to_phrase_threshold_met'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (
    (input.currentTier === 'phrase' || input.currentTier === 'broad') &&
    confidence >= 0.7 &&
    input.metrics.conversions >= 4 &&
    observedRoas >= 3.1
  ) {
    return {
      searchTerm: input.searchTerm,
      action: input.currentTier === 'broad' ? 'graduate_shopping_to_search' : 'promote_to_exact',
      recommendedTier: 'exact',
      confidence,
      reasonCodes: [...reasonCodes, 'exact_readiness_threshold_met'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (input.currentTier === 'exact' && input.metrics.clicks >= 100 && input.metrics.conversions <= 0) {
    return {
      searchTerm: input.searchTerm,
      action: 'demote_to_phrase',
      recommendedTier: 'phrase',
      confidence,
      reasonCodes: [...reasonCodes, 'exact_underperforming_demote'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  return {
    searchTerm: input.searchTerm,
    action: 'hold',
    recommendedTier: input.currentTier,
    confidence,
    reasonCodes: [...reasonCodes, 'search_tier_hold'],
    policyVersion: INTENT_POLICY_VERSION,
  }
}

export function recommendBidPolicy(raw: BidPolicyInput): BidPolicyDecision {
  const validated = validateBidPolicyInput(raw)
  const input = validated.valid ? validated.value : raw
  const confidence = applyValueSignalToConfidence(normalizeConfidence(input.confidence), input.valueSignalScore)
  const qualityScore = input.attributionQualityScore ?? 1
  const targetMode = input.targetMode ?? 'roas'

  if (confidence < 0.6 || qualityScore < 0.5) {
    return {
      key: input.key,
      action: 'hold',
      recommendedTargetRoas: input.currentTargetRoas,
      recommendedTargetCpa: input.currentTargetCpa,
      confidence,
      reasonCodes: ['confidence_or_quality_gate_hold'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (targetMode === 'cpa') {
    const currentTargetCpa = input.currentTargetCpa ?? 0
    const observedCpa = input.observedCpa ?? currentTargetCpa

    if (currentTargetCpa <= 0 || observedCpa <= 0) {
      return {
        key: input.key,
        action: 'hold',
        recommendedTargetCpa: currentTargetCpa,
        confidence,
        reasonCodes: ['invalid_cpa_inputs_hold'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }

    if (observedCpa <= currentTargetCpa * 0.8) {
      return {
        key: input.key,
        action: 'decrease_target',
        recommendedTargetCpa: Number(
          boundedCpaRecommendation(currentTargetCpa, currentTargetCpa * 0.95).toFixed(4)
        ),
        confidence,
        reasonCodes: ['observed_cpa_below_target'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }

    if (observedCpa >= currentTargetCpa * 1.2) {
      return {
        key: input.key,
        action: 'increase_target',
        recommendedTargetCpa: Number(
          boundedCpaRecommendation(currentTargetCpa, currentTargetCpa * 1.05).toFixed(4)
        ),
        confidence,
        reasonCodes: ['observed_cpa_above_target'],
        policyVersion: INTENT_POLICY_VERSION,
      }
    }

    return {
      key: input.key,
      action: 'hold',
      recommendedTargetCpa: currentTargetCpa,
      confidence,
      reasonCodes: ['cpa_near_target_hold'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  const currentTargetRoas = input.currentTargetRoas ?? 0
  const observedRoas = input.observedRoas ?? currentTargetRoas

  if (currentTargetRoas <= 0 || observedRoas < 0) {
    return {
      key: input.key,
      action: 'hold',
      recommendedTargetRoas: currentTargetRoas,
      confidence,
      reasonCodes: ['invalid_roas_inputs_hold'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (observedRoas >= currentTargetRoas * 1.2) {
    return {
      key: input.key,
      action: 'decrease_target',
      recommendedTargetRoas: Number(
        boundedRoasRecommendation(currentTargetRoas, currentTargetRoas * 0.95).toFixed(4)
      ),
      confidence,
      reasonCodes: ['observed_roas_above_target'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (observedRoas <= currentTargetRoas * 0.8) {
    return {
      key: input.key,
      action: 'increase_target',
      recommendedTargetRoas: Number(
        boundedRoasRecommendation(currentTargetRoas, currentTargetRoas * 1.05).toFixed(4)
      ),
      confidence,
      reasonCodes: ['observed_roas_below_target'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  return {
    key: input.key,
    action: 'hold',
    recommendedTargetRoas: currentTargetRoas,
    confidence,
    reasonCodes: ['roas_near_target_hold'],
    policyVersion: INTENT_POLICY_VERSION,
  }
}

export function evaluateShoppingToSearchGraduation(
  raw: ShoppingToSearchGraduationInput
): ShoppingToSearchGraduationDecision {
  const metricsResult = sanitizeTermMetrics(raw.metrics)
  const input: ShoppingToSearchGraduationInput = { ...raw, metrics: metricsResult.value }
  const confidence = normalizeConfidence(input.confidence)
  const reasonCodes = [...input.classification.reasonCodes, 'shopping_to_search_graduation_v1']
  const observedRoas = safeObservedRoas(input.metrics.costMicros, input.metrics.conversionsValue)

  const nonGraduatingClasses = new Set([
    'BRAND_CORE',
    'COMPETITOR',
    'MISMATCH',
    'RISK_POLICY',
    'INFO_ASSIST',
  ])

  if (input.alreadyCoveredInSearch) {
    return {
      searchTerm: input.searchTerm,
      eligible: false,
      suggestedTier: null,
      confidence,
      requiresReview: false,
      reasonCodes: [...reasonCodes, 'already_covered_in_search'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (nonGraduatingClasses.has(input.classification.intentClass)) {
    return {
      searchTerm: input.searchTerm,
      eligible: false,
      suggestedTier: null,
      confidence,
      requiresReview: false,
      reasonCodes: [...reasonCodes, 'intent_class_not_eligible'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (confidence < 0.6 || input.metrics.clicks < 80) {
    return {
      searchTerm: input.searchTerm,
      eligible: false,
      suggestedTier: null,
      confidence,
      requiresReview: true,
      reasonCodes: [...reasonCodes, 'insufficient_confidence_or_clicks'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (
    input.classification.intentClass === 'PRODUCT_HIGH' &&
    input.metrics.conversions >= 5 &&
    observedRoas >= 3.1
  ) {
    return {
      searchTerm: input.searchTerm,
      eligible: true,
      suggestedTier: 'exact',
      confidence,
      requiresReview: confidence < 0.75,
      reasonCodes: [...reasonCodes, 'exact_graduation_threshold_met'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  if (
    (input.classification.intentClass === 'PRODUCT_HIGH' ||
      input.classification.intentClass === 'CATEGORY_MID') &&
    input.metrics.conversions >= 3 &&
    observedRoas >= 2.6
  ) {
    return {
      searchTerm: input.searchTerm,
      eligible: true,
      suggestedTier: 'phrase',
      confidence,
      requiresReview: confidence < 0.7,
      reasonCodes: [...reasonCodes, 'phrase_graduation_threshold_met'],
      policyVersion: INTENT_POLICY_VERSION,
    }
  }

  return {
    searchTerm: input.searchTerm,
    eligible: false,
    suggestedTier: null,
    confidence,
    requiresReview: true,
    reasonCodes: [...reasonCodes, 'graduation_threshold_not_met'],
    policyVersion: INTENT_POLICY_VERSION,
  }
}

export function evaluateGuardrails(input: GuardrailInput): GuardrailDecision {
  const incidents: GuardrailDecision['incidents'] = []
  const reasonCodes: string[] = []

  const spendDeltaRatio =
    input.baselineSpend > 0 ? input.recentSpend / input.baselineSpend : input.recentSpend > 0 ? 2 : 1
  const revenueDeltaRatio =
    input.baselineRevenue > 0 ? input.recentRevenue / input.baselineRevenue : input.recentRevenue > 0 ? 1 : 0

  if (spendDeltaRatio >= 1.4 && revenueDeltaRatio <= 0.9) {
    incidents.push({
      ruleId: 'spend_spike_margin_drop',
      severity: 'high',
      message: 'Spend increased sharply while revenue lagged baseline.',
      suggestedAction: 'Hold automated promotions and review low-confidence terms.',
    })
    reasonCodes.push('spend_spike_margin_drop')
  }

  if ((input.attributionQualityScore ?? 1) < 0.5) {
    incidents.push({
      ruleId: 'attribution_quality_degraded',
      severity: 'high',
      message: 'Attribution quality score is below safe threshold.',
      suggestedAction: 'Pause aggressive target/bid changes and require manual approval.',
    })
    reasonCodes.push('attribution_quality_degraded')
  }

  if ((input.staleDataHours ?? 0) > 24) {
    incidents.push({
      ruleId: 'data_staleness',
      severity: 'medium',
      message: 'Optimization data is stale beyond 24 hours.',
      suggestedAction: 'Freeze promote/demote and bid policy updates until data refresh completes.',
    })
    reasonCodes.push('data_staleness')
  }

  if ((input.openCriticalIncidents ?? 0) > 0) {
    incidents.push({
      ruleId: 'critical_incident_open',
      severity: 'critical',
      message: 'Critical guardrail incidents are still open.',
      suggestedAction: 'Block automated execution and run rollback protocol.',
    })
    reasonCodes.push('critical_incident_open')
  }

  if ((input.openHighIncidents ?? 0) >= 3) {
    incidents.push({
      ruleId: 'high_incident_stack',
      severity: 'high',
      message: 'Multiple high-severity incidents are active.',
      suggestedAction: 'Switch to hold mode and drain review queue by impact.',
    })
    reasonCodes.push('high_incident_stack')
  }

  const hasCritical = incidents.some((incident) => incident.severity === 'critical')
  const hasHigh = incidents.some((incident) => incident.severity === 'high')

  const status = hasCritical ? 'blocked' : hasHigh ? 'hold' : 'go'

  if (reasonCodes.length === 0) {
    reasonCodes.push('guardrails_clear')
  }

  return {
    status,
    incidents,
    reasonCodes,
    policyVersion: INTENT_POLICY_VERSION,
  }
}
