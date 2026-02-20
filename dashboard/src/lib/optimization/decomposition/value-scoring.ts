import type { QueryValueScore, SearchTermSourceAssignment } from '@/lib/shopping-funnel/types'
import type {
  PairValueScoreResult,
  ValueMetricStats,
  ValueScoringContext,
} from '@/lib/optimization/decomposition/types'

const MIN_BASE_CTR = 0.005
const MIN_BASE_CVR = 0.002
const MIN_BASE_CPC = 0.25
const MIN_BASE_VALUE_PER_CONVERSION = 20

const PRIOR_SAMPLES = {
  ctr: 180,
  cvr: 80,
  cpc: 75,
  valuePerConversion: 30,
} as const

function toNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function safeDivide(numerator: number, denominator: number, fallback = 0): number {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0) {
    return fallback
  }
  return numerator / denominator
}

function round(value: number, precision: number): number {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min
  }
  return Math.max(min, Math.min(max, value))
}

function emptyStats(): ValueMetricStats {
  return {
    impressions: 0,
    clicks: 0,
    conversions: 0,
    cost: 0,
    conversionValue: 0,
    ctr: MIN_BASE_CTR,
    cvr: MIN_BASE_CVR,
    cpc: MIN_BASE_CPC,
    valuePerConversion: MIN_BASE_VALUE_PER_CONVERSION,
    valuePerClick: MIN_BASE_CTR * MIN_BASE_CVR * MIN_BASE_VALUE_PER_CONVERSION,
  }
}

function aggregateStats(assignments: SearchTermSourceAssignment[]): ValueMetricStats {
  if (assignments.length === 0) {
    return emptyStats()
  }

  const totals = assignments.reduce(
    (acc, assignment) => {
      acc.impressions += toNumber(assignment.impressions)
      acc.clicks += toNumber(assignment.clicks)
      acc.conversions += toNumber(assignment.conversions)
      acc.cost += toNumber(assignment.cost_micros) / 1_000_000
      acc.conversionValue += toNumber(assignment.conversions_value)
      return acc
    },
    {
      impressions: 0,
      clicks: 0,
      conversions: 0,
      cost: 0,
      conversionValue: 0,
    }
  )

  const ctr = Math.max(safeDivide(totals.clicks, totals.impressions, MIN_BASE_CTR), MIN_BASE_CTR)
  const cvr = Math.max(safeDivide(totals.conversions, totals.clicks, MIN_BASE_CVR), MIN_BASE_CVR)
  const cpc = Math.max(safeDivide(totals.cost, totals.clicks, MIN_BASE_CPC), MIN_BASE_CPC)
  const valuePerConversion = Math.max(
    safeDivide(totals.conversionValue, totals.conversions, MIN_BASE_VALUE_PER_CONVERSION),
    MIN_BASE_VALUE_PER_CONVERSION
  )
  const valuePerClick = Math.max(
    safeDivide(totals.conversionValue, totals.clicks, ctr * cvr * valuePerConversion),
    MIN_BASE_CTR * MIN_BASE_CVR * MIN_BASE_VALUE_PER_CONVERSION
  )

  return {
    impressions: totals.impressions,
    clicks: totals.clicks,
    conversions: totals.conversions,
    cost: totals.cost,
    conversionValue: totals.conversionValue,
    ctr,
    cvr,
    cpc,
    valuePerConversion,
    valuePerClick,
  }
}

function blendPrior(
  observed: number,
  observedSamples: number,
  prior: number,
  priorSamples: number,
  minimum: number
): number {
  const obs = Number.isFinite(observed) ? observed : 0
  const pr = Number.isFinite(prior) ? prior : minimum
  const obsWeight = Math.max(observedSamples, 0)
  const priorWeight = Math.max(priorSamples, 1)
  const blended = safeDivide(obs * obsWeight + pr * priorWeight, obsWeight + priorWeight, pr)
  return Math.max(blended, minimum)
}

function weightedPrior(candidates: Array<{ value: number; weight: number }>, fallback: number): number {
  const valid = candidates.filter((candidate) => Number.isFinite(candidate.value) && candidate.weight > 0)
  if (valid.length === 0) {
    return fallback
  }
  const numerator = valid.reduce((sum, candidate) => sum + candidate.value * candidate.weight, 0)
  const denominator = valid.reduce((sum, candidate) => sum + candidate.weight, 0)
  return safeDivide(numerator, denominator, fallback)
}

export function createValueScoringContext(assignments: SearchTermSourceAssignment[]): ValueScoringContext {
  const global = aggregateStats(assignments)
  const byTier: Partial<Record<string, SearchTermSourceAssignment[]>> = {}
  const byLabel = new Map<string, SearchTermSourceAssignment[]>()
  const byLabelTier = new Map<string, SearchTermSourceAssignment[]>()

  for (const assignment of assignments) {
    const tierKey = assignment.source_tier?.toLowerCase()
    const labelKey = assignment.custom_label_0.toLowerCase().trim()
    const labelTierKey = `${labelKey}||${tierKey ?? 'unknown'}`

    byTier[tierKey] = [...(byTier[tierKey] ?? []), assignment]
    byLabel.set(labelKey, [...(byLabel.get(labelKey) ?? []), assignment])
    byLabelTier.set(labelTierKey, [...(byLabelTier.get(labelTierKey) ?? []), assignment])
  }

  const byTierStats: Partial<Record<string, ValueMetricStats>> = {}
  for (const [tier, tierAssignments] of Object.entries(byTier)) {
    byTierStats[tier] = aggregateStats(tierAssignments ?? [])
  }

  const byLabelStats = new Map<string, ValueMetricStats>()
  for (const [label, labelAssignments] of byLabel.entries()) {
    byLabelStats.set(label, aggregateStats(labelAssignments))
  }

  const byLabelTierStats = new Map<string, ValueMetricStats>()
  for (const [labelTier, labelTierAssignments] of byLabelTier.entries()) {
    byLabelTierStats.set(labelTier, aggregateStats(labelTierAssignments))
  }

  return {
    global,
    byTier: byTierStats,
    byLabel: byLabelStats,
    byLabelTier: byLabelTierStats,
  }
}

function resolvePriorStats(
  context: ValueScoringContext | undefined,
  assignment: SearchTermSourceAssignment,
  customLabel0: string
): {
  labelTier: ValueMetricStats | null
  label: ValueMetricStats | null
  tier: ValueMetricStats | null
  global: ValueMetricStats
} {
  const global = context?.global ?? emptyStats()
  if (!context) {
    return { labelTier: null, label: null, tier: null, global }
  }

  const labelKey = customLabel0.toLowerCase().trim()
  const tierKey = assignment.source_tier?.toLowerCase() ?? 'unknown'
  const labelTierKey = `${labelKey}||${tierKey}`

  return {
    labelTier: context.byLabelTier.get(labelTierKey) ?? null,
    label: context.byLabel.get(labelKey) ?? null,
    tier: context.byTier[tierKey] ?? null,
    global,
  }
}

export function scorePairValueWithContext(
  assignment: SearchTermSourceAssignment,
  customLabel0: string,
  context?: ValueScoringContext
): PairValueScoreResult {
  const impressions = Math.max(toNumber(assignment.impressions), 0)
  const clicks = Math.max(toNumber(assignment.clicks), 0)
  const conversions = Math.max(toNumber(assignment.conversions), 0)
  const cost = Math.max(toNumber(assignment.cost_micros) / 1_000_000, 0)
  const conversionValue = Math.max(toNumber(assignment.conversions_value), 0)

  const observedCtr = safeDivide(clicks, impressions, MIN_BASE_CTR)
  const observedCvr = safeDivide(conversions, clicks, MIN_BASE_CVR)
  const observedCpc = safeDivide(cost, clicks, MIN_BASE_CPC)
  const observedValuePerConversion = safeDivide(
    conversionValue,
    conversions,
    Math.max(MIN_BASE_VALUE_PER_CONVERSION, safeDivide(conversionValue, Math.max(clicks, 1), MIN_BASE_VALUE_PER_CONVERSION))
  )

  const priors = resolvePriorStats(context, assignment, customLabel0)
  const priorCtr = weightedPrior(
    [
      { value: priors.labelTier?.ctr ?? NaN, weight: 0.45 },
      { value: priors.label?.ctr ?? NaN, weight: 0.3 },
      { value: priors.tier?.ctr ?? NaN, weight: 0.15 },
      { value: priors.global.ctr, weight: 0.1 },
    ],
    priors.global.ctr
  )
  const priorCvr = weightedPrior(
    [
      { value: priors.labelTier?.cvr ?? NaN, weight: 0.45 },
      { value: priors.label?.cvr ?? NaN, weight: 0.3 },
      { value: priors.tier?.cvr ?? NaN, weight: 0.15 },
      { value: priors.global.cvr, weight: 0.1 },
    ],
    priors.global.cvr
  )
  const priorCpc = weightedPrior(
    [
      { value: priors.labelTier?.cpc ?? NaN, weight: 0.4 },
      { value: priors.label?.cpc ?? NaN, weight: 0.3 },
      { value: priors.tier?.cpc ?? NaN, weight: 0.2 },
      { value: priors.global.cpc, weight: 0.1 },
    ],
    priors.global.cpc
  )
  const priorValuePerConversion = weightedPrior(
    [
      { value: priors.labelTier?.valuePerConversion ?? NaN, weight: 0.5 },
      { value: priors.label?.valuePerConversion ?? NaN, weight: 0.3 },
      { value: priors.tier?.valuePerConversion ?? NaN, weight: 0.1 },
      { value: priors.global.valuePerConversion, weight: 0.1 },
    ],
    priors.global.valuePerConversion
  )

  const blendedCtr = blendPrior(observedCtr, impressions, priorCtr, PRIOR_SAMPLES.ctr, MIN_BASE_CTR)
  const blendedCvr = blendPrior(observedCvr, clicks, priorCvr, PRIOR_SAMPLES.cvr, MIN_BASE_CVR)
  const blendedCpc = blendPrior(observedCpc, clicks, priorCpc, PRIOR_SAMPLES.cpc, MIN_BASE_CPC)
  const blendedValuePerConversion = blendPrior(
    observedValuePerConversion,
    conversions,
    priorValuePerConversion,
    PRIOR_SAMPLES.valuePerConversion,
    MIN_BASE_VALUE_PER_CONVERSION
  )

  const expectedClicks = Math.max(clicks, impressions * blendedCtr)
  const expectedConversions = expectedClicks * blendedCvr
  const expectedConversionValue = expectedConversions * blendedValuePerConversion
  const expectedCost = expectedClicks * blendedCpc
  const expectedProfitProxy = expectedConversionValue - expectedCost

  const clickConfidence = Math.min(clicks / 60, 1)
  const conversionConfidence = Math.min(conversions / 15, 1)
  const priorSampleSignal = clamp(
    safeDivide((priors.labelTier?.clicks ?? 0) + (priors.label?.clicks ?? 0), 250, 0),
    0,
    1
  )
  const uncertainty = clamp(
    1 - (0.55 * clickConfidence + 0.3 * conversionConfidence + 0.15 * priorSampleSignal),
    0,
    1
  )

  const impactScore = expectedProfitProxy * (1 - uncertainty * 0.4)

  const value: QueryValueScore = {
    impact_score: round(impactScore, 2),
    expected_clicks: round(expectedClicks, 2),
    expected_cvr: round(blendedCvr, 4),
    expected_conversion_value: round(expectedConversionValue, 2),
    expected_profit_proxy: round(expectedProfitProxy, 2),
    uncertainty: round(uncertainty, 4),
  }

  return {
    value,
    modelInputs: {
      observed: {
        impressions,
        clicks,
        conversions,
        cost,
        conversion_value: conversionValue,
        ctr: round(observedCtr, 6),
        cvr: round(observedCvr, 6),
        cpc: round(observedCpc, 6),
        value_per_conversion: round(observedValuePerConversion, 6),
      },
      priors: {
        ctr: round(priorCtr, 6),
        cvr: round(priorCvr, 6),
        cpc: round(priorCpc, 6),
        value_per_conversion: round(priorValuePerConversion, 6),
      },
      blended: {
        ctr: round(blendedCtr, 6),
        cvr: round(blendedCvr, 6),
        cpc: round(blendedCpc, 6),
        value_per_conversion: round(blendedValuePerConversion, 6),
      },
      expected: {
        clicks: round(expectedClicks, 4),
        conversions: round(expectedConversions, 4),
        conversion_value: round(expectedConversionValue, 4),
        cost: round(expectedCost, 4),
        profit_proxy: round(expectedProfitProxy, 4),
      },
      uncertainty_components: {
        click_confidence: round(clickConfidence, 4),
        conversion_confidence: round(conversionConfidence, 4),
        prior_sample_signal: round(priorSampleSignal, 4),
      },
      scoring_model: 'score_v1_calibrated',
    },
  }
}

