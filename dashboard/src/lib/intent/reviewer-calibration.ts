/**
 * Reviewer Calibration Analytics + Workload Balancing
 *
 * Provides calibration scoring, workload balance assessment via Gini coefficient,
 * and outlier identification for operator review actors.
 */

export interface ActorStats {
  totalActions: number
  alignmentRate: number
  uniqueEntities: number
}

export interface ActorSummary {
  actor: string
  total_actions: number
  alignment_rate?: number
}

export interface WorkloadBalanceResult {
  giniCoefficient: number
  isBalanced: boolean
  recommendations: string[]
}

export interface CalibrationOutlier {
  actor: string
  alignment_rate: number
  deviation: number
  direction: 'above' | 'below'
}

/**
 * Calculate a 0-1 calibration score for a reviewer.
 *
 * Formula: alignmentRate * 0.6 + min(totalActions/100, 1) * 0.3 + min(uniqueEntities/50, 1) * 0.1
 */
export function calculateCalibrationScore(stats: ActorStats): number {
  const alignmentComponent = stats.alignmentRate * 0.6
  const volumeComponent = Math.min(stats.totalActions / 100, 1) * 0.3
  const breadthComponent = Math.min(stats.uniqueEntities / 50, 1) * 0.1
  return Number((alignmentComponent + volumeComponent + breadthComponent).toFixed(4))
}

/**
 * Calculate the Gini coefficient for an array of values.
 * Returns 0 for perfectly equal distribution, approaches 1 for maximum inequality.
 */
function giniCoefficient(values: number[]): number {
  if (values.length === 0) return 0
  if (values.length === 1) return 0

  const n = values.length
  const mean = values.reduce((sum, v) => sum + v, 0) / n

  if (mean === 0) return 0

  // Mean absolute difference formula: G = sum(|xi - xj|) / (2 * n^2 * mean)
  let sumAbsDiff = 0
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      sumAbsDiff += Math.abs(values[i] - values[j])
    }
  }

  const gini = sumAbsDiff / (2 * n * n * mean)
  return Number(Math.max(0, Math.min(1, gini)).toFixed(4))
}

/**
 * Assess workload balance across actors using the Gini coefficient.
 *
 * Balanced = Gini < 0.4.
 * Recommends redistribution if any actor has >2x the median workload.
 */
export function assessWorkloadBalance(actorSummaries: ActorSummary[]): WorkloadBalanceResult {
  if (actorSummaries.length === 0) {
    return { giniCoefficient: 0, isBalanced: true, recommendations: [] }
  }

  if (actorSummaries.length === 1) {
    return {
      giniCoefficient: 0,
      isBalanced: true,
      recommendations: ['Only one actor found. Consider adding more reviewers for redundancy.'],
    }
  }

  const actions = actorSummaries.map((a) => a.total_actions)
  const gini = giniCoefficient(actions)
  const isBalanced = gini < 0.4

  const recommendations: string[] = []

  const sorted = [...actions].sort((a, b) => a - b)
  const midIndex = Math.floor(sorted.length / 2)
  const median =
    sorted.length % 2 === 0 ? (sorted[midIndex - 1] + sorted[midIndex]) / 2 : sorted[midIndex]

  for (const summary of actorSummaries) {
    if (median > 0 && summary.total_actions > 2 * median) {
      recommendations.push(
        `Actor "${summary.actor}" has ${summary.total_actions} actions (>${Math.round(2 * median)} = 2x median). Consider redistributing workload.`
      )
    }
  }

  if (!isBalanced && recommendations.length === 0) {
    recommendations.push(
      `Workload distribution is uneven (Gini=${gini.toFixed(2)}). Consider rebalancing review assignments.`
    )
  }

  return { giniCoefficient: gini, isBalanced, recommendations }
}

/**
 * Identify actors whose alignment_rate differs from the mean by more than 1.5 standard deviations.
 */
export function identifyCalibrationOutliers(
  actorSummaries: Array<ActorSummary & { alignment_rate: number }>
): CalibrationOutlier[] {
  if (actorSummaries.length < 2) return []

  const rates = actorSummaries.map((a) => a.alignment_rate)
  const mean = rates.reduce((sum, r) => sum + r, 0) / rates.length
  const variance = rates.reduce((sum, r) => sum + (r - mean) ** 2, 0) / rates.length
  const stdDev = Math.sqrt(variance)

  if (stdDev === 0) return []

  const threshold = 1.5

  return actorSummaries
    .filter((a) => Math.abs(a.alignment_rate - mean) > threshold * stdDev)
    .map((a) => ({
      actor: a.actor,
      alignment_rate: a.alignment_rate,
      deviation: Number(((a.alignment_rate - mean) / stdDev).toFixed(2)),
      direction: a.alignment_rate > mean ? ('above' as const) : ('below' as const),
    }))
}
