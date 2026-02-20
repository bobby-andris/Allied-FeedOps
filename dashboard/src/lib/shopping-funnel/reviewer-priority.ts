import type { QueryValueScore } from '@/lib/shopping-funnel/types'

export interface HighImpactThresholds {
  minPriorityScore: number
  maxUncertainty: number
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min
  return Math.max(min, Math.min(max, value))
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

export function computeReviewerPriorityScore(valueScore?: QueryValueScore | null): number {
  if (!valueScore) return 0

  const expectedProfitProxy = Math.max(toFiniteNumber(valueScore.expected_profit_proxy), 0)
  const uncertainty = clamp(toFiniteNumber(valueScore.uncertainty, 1), 0, 1)
  const certainty = 1 - uncertainty

  return Number((expectedProfitProxy * certainty).toFixed(4))
}

export function isHighImpactValueScore(
  valueScore: QueryValueScore | null | undefined,
  thresholds: HighImpactThresholds
): boolean {
  if (!valueScore) return false

  const priorityScore = computeReviewerPriorityScore(valueScore)
  const uncertainty = clamp(toFiniteNumber(valueScore.uncertainty, 1), 0, 1)

  return priorityScore >= thresholds.minPriorityScore && uncertainty <= thresholds.maxUncertainty
}
