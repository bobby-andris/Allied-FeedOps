/**
 * Multi-Cell Experiments + Automated Winner Rollout
 *
 * Create experiments with multiple cells, deterministically assign entities,
 * evaluate winners with significance checks, and build rollout plans.
 */

export interface ExperimentCell {
  name: string
  allocationPct: number
}

export interface ExperimentConfig {
  experimentKey: string
  name: string
  cells: ExperimentCell[]
  hypothesis: string
  successMetric: string
  minSampleSize: number
}

export interface ExperimentDefinition extends ExperimentConfig {
  createdAt: string
  status: 'active'
}

export interface CellResult {
  cellName: string
  metricValue: number
  sampleSize: number
}

export interface WinnerEvaluation {
  winner: string
  isSignificant: boolean
  liftVsControl: number
}

export interface RolloutPlan {
  experimentKey: string
  winningCell: string
  action: 'apply_winner_to_all_traffic'
  steps: string[]
}

/**
 * Create a multi-cell experiment definition.
 * Validates that cell allocations sum to 100.
 */
export function createMultiCellExperiment(config: ExperimentConfig): ExperimentDefinition {
  if (config.cells.length < 2) {
    throw new Error('Experiment must have at least 2 cells')
  }

  const totalAllocation = config.cells.reduce((sum, cell) => sum + cell.allocationPct, 0)
  if (Math.abs(totalAllocation - 100) > 0.01) {
    throw new Error(
      `Cell allocations must sum to 100, got ${totalAllocation}`
    )
  }

  return {
    ...config,
    createdAt: new Date().toISOString(),
    status: 'active',
  }
}

/**
 * Deterministic assignment using a simple hash of the entityKey.
 * Selects a cell proportionally by allocation percentage.
 */
export function assignToCell(entityKey: string, cells: ExperimentCell[]): string {
  if (cells.length === 0) {
    throw new Error('No cells provided for assignment')
  }

  // Simple string hash (djb2)
  let hash = 5381
  for (let i = 0; i < entityKey.length; i++) {
    hash = ((hash << 5) + hash + entityKey.charCodeAt(i)) >>> 0
  }

  const bucket = hash % 10000
  const threshold = bucket / 100 // 0-99.99

  let cumulative = 0
  for (const cell of cells) {
    cumulative += cell.allocationPct
    if (threshold < cumulative) {
      return cell.name
    }
  }

  // Fallback to last cell (rounding edge case)
  return cells[cells.length - 1].name
}

/**
 * Evaluate which cell wins a multi-cell experiment.
 *
 * Winner = cell with highest metricValue AND sampleSize >= minSampleSize.
 * Significance = lift > 5% vs control (first cell).
 * Returns null if no valid winner can be determined.
 */
export function evaluateMultiCellWinner(
  cells: CellResult[],
  minSampleSize: number
): WinnerEvaluation | null {
  if (cells.length < 2) return null

  const eligible = cells.filter((c) => c.sampleSize >= minSampleSize)
  if (eligible.length === 0) return null

  const control = cells[0]
  const controlEligible = control.sampleSize >= minSampleSize

  // Find best performer among eligible cells
  const best = eligible.reduce((prev, curr) =>
    curr.metricValue > prev.metricValue ? curr : prev
  )

  // If control is not eligible, the best eligible cell wins but we can't compute lift
  if (!controlEligible) {
    return {
      winner: best.cellName,
      isSignificant: false,
      liftVsControl: 0,
    }
  }

  if (control.metricValue === 0) {
    // Avoid division by zero — any positive metric is a win
    const lift = best.metricValue > 0 ? 1 : 0
    return {
      winner: best.cellName,
      isSignificant: lift > 0.05,
      liftVsControl: Number(lift.toFixed(4)),
    }
  }

  const lift = (best.metricValue - control.metricValue) / control.metricValue
  const isSignificant = lift > 0.05

  return {
    winner: best.cellName,
    isSignificant,
    liftVsControl: Number(lift.toFixed(4)),
  }
}

/**
 * Build a rollout plan for applying the winning cell's configuration to all traffic.
 */
export function buildRolloutPlan(winner: string, experimentKey: string): RolloutPlan {
  return {
    experimentKey,
    winningCell: winner,
    action: 'apply_winner_to_all_traffic',
    steps: [
      `Validate winning cell "${winner}" results for experiment "${experimentKey}"`,
      `Gradually shift traffic allocation to "${winner}" (25% -> 50% -> 100%)`,
      `Monitor key metrics during rollout for regressions`,
      `Archive experiment "${experimentKey}" after full rollout`,
      `Update default configuration to match "${winner}" settings`,
    ],
  }
}
