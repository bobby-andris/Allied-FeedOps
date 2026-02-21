import { describe, expect, it } from 'vitest'
import {
  createMultiCellExperiment,
  assignToCell,
  evaluateMultiCellWinner,
  buildRolloutPlan,
} from '@/lib/intent/multi-cell-experiment'

describe('createMultiCellExperiment', () => {
  it('creates an experiment when allocations sum to 100', () => {
    const experiment = createMultiCellExperiment({
      experimentKey: 'test-exp-1',
      name: 'Title Length Test',
      cells: [
        { name: 'control', allocationPct: 50 },
        { name: 'variant_a', allocationPct: 50 },
      ],
      hypothesis: 'Longer titles improve CTR',
      successMetric: 'ctr',
      minSampleSize: 100,
    })

    expect(experiment.experimentKey).toBe('test-exp-1')
    expect(experiment.status).toBe('active')
    expect(experiment.createdAt).toBeDefined()
    expect(experiment.cells).toHaveLength(2)
  })

  it('throws when allocations do not sum to 100', () => {
    expect(() =>
      createMultiCellExperiment({
        experimentKey: 'test-exp-2',
        name: 'Bad Allocation',
        cells: [
          { name: 'control', allocationPct: 50 },
          { name: 'variant_a', allocationPct: 30 },
        ],
        hypothesis: 'Test',
        successMetric: 'ctr',
        minSampleSize: 100,
      })
    ).toThrow('must sum to 100')
  })

  it('throws when fewer than 2 cells provided', () => {
    expect(() =>
      createMultiCellExperiment({
        experimentKey: 'test-exp-3',
        name: 'Single Cell',
        cells: [{ name: 'control', allocationPct: 100 }],
        hypothesis: 'Test',
        successMetric: 'ctr',
        minSampleSize: 100,
      })
    ).toThrow('at least 2 cells')
  })

  it('supports three or more cells', () => {
    const experiment = createMultiCellExperiment({
      experimentKey: 'test-exp-4',
      name: 'Three Cell Test',
      cells: [
        { name: 'control', allocationPct: 34 },
        { name: 'variant_a', allocationPct: 33 },
        { name: 'variant_b', allocationPct: 33 },
      ],
      hypothesis: 'Test',
      successMetric: 'ctr',
      minSampleSize: 50,
    })
    expect(experiment.cells).toHaveLength(3)
  })
})

describe('assignToCell', () => {
  const cells = [
    { name: 'control', allocationPct: 50 },
    { name: 'variant_a', allocationPct: 50 },
  ]

  it('returns deterministic results for the same entity key', () => {
    const first = assignToCell('sku-12345', cells)
    const second = assignToCell('sku-12345', cells)
    expect(first).toBe(second)
  })

  it('assigns different entities to different cells (statistical)', () => {
    const assignments = new Map<string, number>()
    for (let i = 0; i < 1000; i++) {
      const cell = assignToCell(`entity-${i}`, cells)
      assignments.set(cell, (assignments.get(cell) ?? 0) + 1)
    }
    // With 50/50 split and 1000 samples, each cell should get roughly 400-600
    const controlCount = assignments.get('control') ?? 0
    const variantCount = assignments.get('variant_a') ?? 0
    expect(controlCount).toBeGreaterThan(200)
    expect(variantCount).toBeGreaterThan(200)
  })

  it('respects uneven allocation ratios', () => {
    const unevenCells = [
      { name: 'control', allocationPct: 90 },
      { name: 'variant_a', allocationPct: 10 },
    ]
    const assignments = new Map<string, number>()
    for (let i = 0; i < 1000; i++) {
      const cell = assignToCell(`entity-${i}`, unevenCells)
      assignments.set(cell, (assignments.get(cell) ?? 0) + 1)
    }
    const controlCount = assignments.get('control') ?? 0
    expect(controlCount).toBeGreaterThan(700)
  })

  it('always returns a valid cell name', () => {
    for (let i = 0; i < 100; i++) {
      const cell = assignToCell(`key-${i}`, cells)
      expect(['control', 'variant_a']).toContain(cell)
    }
  })
})

describe('evaluateMultiCellWinner', () => {
  it('identifies the cell with highest metric value as winner', () => {
    const result = evaluateMultiCellWinner(
      [
        { cellName: 'control', metricValue: 0.05, sampleSize: 200 },
        { cellName: 'variant_a', metricValue: 0.08, sampleSize: 200 },
      ],
      100
    )
    expect(result).not.toBeNull()
    expect(result!.winner).toBe('variant_a')
    expect(result!.isSignificant).toBe(true)
    expect(result!.liftVsControl).toBeGreaterThan(0.05)
  })

  it('returns null when insufficient sample size for all cells', () => {
    const result = evaluateMultiCellWinner(
      [
        { cellName: 'control', metricValue: 0.05, sampleSize: 10 },
        { cellName: 'variant_a', metricValue: 0.08, sampleSize: 10 },
      ],
      100
    )
    expect(result).toBeNull()
  })

  it('marks as not significant when lift is below 5%', () => {
    const result = evaluateMultiCellWinner(
      [
        { cellName: 'control', metricValue: 0.05, sampleSize: 200 },
        { cellName: 'variant_a', metricValue: 0.051, sampleSize: 200 },
      ],
      100
    )
    expect(result).not.toBeNull()
    expect(result!.isSignificant).toBe(false)
  })

  it('returns null for fewer than 2 cells', () => {
    const result = evaluateMultiCellWinner(
      [{ cellName: 'control', metricValue: 0.05, sampleSize: 200 }],
      100
    )
    expect(result).toBeNull()
  })

  it('handles control being the best performer', () => {
    const result = evaluateMultiCellWinner(
      [
        { cellName: 'control', metricValue: 0.10, sampleSize: 200 },
        { cellName: 'variant_a', metricValue: 0.05, sampleSize: 200 },
      ],
      100
    )
    expect(result).not.toBeNull()
    expect(result!.winner).toBe('control')
    // Lift vs control when control wins = 0
    expect(result!.liftVsControl).toBe(0)
    expect(result!.isSignificant).toBe(false)
  })

  it('handles three cells and picks the best', () => {
    const result = evaluateMultiCellWinner(
      [
        { cellName: 'control', metricValue: 0.05, sampleSize: 200 },
        { cellName: 'variant_a', metricValue: 0.06, sampleSize: 200 },
        { cellName: 'variant_b', metricValue: 0.09, sampleSize: 200 },
      ],
      100
    )
    expect(result).not.toBeNull()
    expect(result!.winner).toBe('variant_b')
    expect(result!.isSignificant).toBe(true)
  })
})

describe('buildRolloutPlan', () => {
  it('generates a rollout plan with correct experiment key and winner', () => {
    const plan = buildRolloutPlan('variant_a', 'exp-title-length')
    expect(plan.experimentKey).toBe('exp-title-length')
    expect(plan.winningCell).toBe('variant_a')
    expect(plan.action).toBe('apply_winner_to_all_traffic')
    expect(plan.steps.length).toBeGreaterThan(0)
    expect(plan.steps.some((s) => s.includes('variant_a'))).toBe(true)
    expect(plan.steps.some((s) => s.includes('exp-title-length'))).toBe(true)
  })

  it('includes gradual traffic shift in steps', () => {
    const plan = buildRolloutPlan('winner_cell', 'my-experiment')
    expect(plan.steps.some((s) => s.includes('25%') || s.includes('50%') || s.includes('100%'))).toBe(true)
  })
})
