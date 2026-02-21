import type { TermMetrics, IntentDecisionInput, BidPolicyInput } from '@/lib/intent/types'

export interface ValidationResult<T> {
  valid: boolean
  value: T
  warnings: string[]
}

function safeNonNegative(value: number, fieldName: string, warnings: string[]): number {
  if (!Number.isFinite(value)) {
    warnings.push(`${fieldName}: non-finite value replaced with 0`)
    return 0
  }
  if (value < 0) {
    warnings.push(`${fieldName}: negative value clamped to 0`)
    return 0
  }
  return value
}

function safeClamp01(value: number | undefined, fieldName: string, warnings: string[]): number | undefined {
  if (value == null) return undefined
  if (!Number.isFinite(value)) {
    warnings.push(`${fieldName}: non-finite value dropped`)
    return undefined
  }
  if (value < 0) {
    warnings.push(`${fieldName}: clamped from ${value} to 0`)
    return 0
  }
  if (value > 1) {
    warnings.push(`${fieldName}: clamped from ${value} to 1`)
    return 1
  }
  return value
}

function floorCount(value: number): number {
  return Math.floor(value)
}

export function sanitizeTermMetrics(metrics: TermMetrics): ValidationResult<TermMetrics> {
  const warnings: string[] = []

  const impressions = floorCount(safeNonNegative(metrics.impressions, 'impressions', warnings))
  const clicks = floorCount(safeNonNegative(metrics.clicks, 'clicks', warnings))
  const conversions = floorCount(safeNonNegative(metrics.conversions, 'conversions', warnings))
  const conversionsValue = safeNonNegative(metrics.conversionsValue, 'conversionsValue', warnings)
  const costMicros = safeNonNegative(metrics.costMicros, 'costMicros', warnings)

  return {
    valid: true,
    value: { impressions, clicks, conversions, conversionsValue, costMicros },
    warnings,
  }
}

export function validateDecisionInput(input: IntentDecisionInput): ValidationResult<IntentDecisionInput> {
  const warnings: string[] = []
  const trimmed = input.searchTerm?.trim() ?? ''

  if (trimmed.length === 0) {
    return {
      valid: false,
      value: input,
      warnings: ['searchTerm is empty or whitespace-only'],
    }
  }

  const metricsResult = sanitizeTermMetrics(input.metrics)
  warnings.push(...metricsResult.warnings)

  const attributionQualityScore = safeClamp01(
    input.attributionQualityScore,
    'attributionQualityScore',
    warnings
  )
  const valueSignalScore = safeClamp01(input.valueSignalScore, 'valueSignalScore', warnings)

  return {
    valid: true,
    value: {
      searchTerm: trimmed,
      metrics: metricsResult.value,
      attributionQualityScore,
      valueSignalScore,
      existingTerm: input.existingTerm,
    },
    warnings,
  }
}

export function validateBidPolicyInput(input: BidPolicyInput): ValidationResult<BidPolicyInput> {
  const warnings: string[] = []
  const trimmedKey = input.key?.trim() ?? ''

  if (trimmedKey.length === 0) {
    return {
      valid: false,
      value: input,
      warnings: ['key is empty'],
    }
  }

  const confidence = safeClamp01(input.confidence, 'confidence', warnings) ?? 0
  const attributionQualityScore = safeClamp01(
    input.attributionQualityScore,
    'attributionQualityScore',
    warnings
  )
  const valueSignalScore = safeClamp01(input.valueSignalScore, 'valueSignalScore', warnings)

  const currentTargetRoas =
    input.currentTargetRoas != null
      ? safeNonNegative(input.currentTargetRoas, 'currentTargetRoas', warnings)
      : undefined
  const observedRoas =
    input.observedRoas != null
      ? safeNonNegative(input.observedRoas, 'observedRoas', warnings)
      : undefined
  const currentTargetCpa =
    input.currentTargetCpa != null
      ? safeNonNegative(input.currentTargetCpa, 'currentTargetCpa', warnings)
      : undefined
  const observedCpa =
    input.observedCpa != null
      ? safeNonNegative(input.observedCpa, 'observedCpa', warnings)
      : undefined

  return {
    valid: true,
    value: {
      key: trimmedKey,
      channel: input.channel,
      intentClass: input.intentClass,
      targetMode: input.targetMode,
      currentTargetRoas,
      observedRoas,
      currentTargetCpa,
      observedCpa,
      confidence,
      attributionQualityScore,
      valueSignalScore,
    },
    warnings,
  }
}
