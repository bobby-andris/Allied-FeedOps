export interface ValueConsistencyInput {
  ga4ConversionValue: number
  shopifyOrderValue: number
  periodDays?: number
}

export type ConsistencySeverity = 'none' | 'warning' | 'critical'

export interface ValueConsistencyResult {
  consistencyScore: number
  divergenceFlag: boolean
  severity: ConsistencySeverity
  divergenceRatio: number
  periodDays?: number
  reasonCodes: string[]
}

/** Divergence thresholds (fraction of max value). */
const WARNING_THRESHOLD = 0.15
const CRITICAL_THRESHOLD = 0.50

function safeValue(value: number): number {
  if (!Number.isFinite(value) || value < 0) return 0
  return value
}

export function checkValueConsistency(input: ValueConsistencyInput): ValueConsistencyResult {
  const ga4 = safeValue(input.ga4ConversionValue)
  const shopify = safeValue(input.shopifyOrderValue)
  const reasonCodes: string[] = []

  // Both zero — perfectly consistent (no activity)
  if (ga4 === 0 && shopify === 0) {
    return {
      consistencyScore: 1,
      divergenceFlag: false,
      severity: 'none',
      divergenceRatio: 0,
      periodDays: input.periodDays,
      reasonCodes: ['both_zero_consistent'],
    }
  }

  // One zero, other non-zero — total divergence
  if (ga4 === 0 || shopify === 0) {
    reasonCodes.push(ga4 === 0 ? 'ga4_zero_shopify_nonzero' : 'shopify_zero_ga4_nonzero')
    return {
      consistencyScore: 0,
      divergenceFlag: true,
      severity: 'critical',
      divergenceRatio: 1,
      periodDays: input.periodDays,
      reasonCodes,
    }
  }

  // Symmetric divergence ratio: |a - b| / max(a, b)
  const maxVal = Math.max(ga4, shopify)
  const divergenceRatio = Math.abs(ga4 - shopify) / maxVal
  const consistencyScore = Math.max(0, 1 - divergenceRatio)

  let severity: ConsistencySeverity = 'none'
  let divergenceFlag = false

  if (divergenceRatio >= CRITICAL_THRESHOLD) {
    severity = 'critical'
    divergenceFlag = true
    reasonCodes.push('critical_value_divergence')
  } else if (divergenceRatio >= WARNING_THRESHOLD) {
    severity = 'warning'
    divergenceFlag = true
    reasonCodes.push('moderate_value_divergence')
  } else {
    reasonCodes.push('values_consistent')
  }

  return {
    consistencyScore,
    divergenceFlag,
    severity,
    divergenceRatio,
    periodDays: input.periodDays,
    reasonCodes,
  }
}
