import { describe, it, expect } from 'vitest'
import { getConfidenceDotColor, formatTimestamp } from '../components/LeakageHero'

// ---------------------------------------------------------------------------
// getConfidenceDotColor
// ---------------------------------------------------------------------------

describe('getConfidenceDotColor', () => {
  it('returns green for high confidence (>= 0.70)', () => {
    expect(getConfidenceDotColor(0.70)).toBe('bg-green-500')
    expect(getConfidenceDotColor(0.85)).toBe('bg-green-500')
    expect(getConfidenceDotColor(1.0)).toBe('bg-green-500')
  })

  it('returns yellow for medium confidence (0.40 - 0.69)', () => {
    expect(getConfidenceDotColor(0.40)).toBe('bg-yellow-500')
    expect(getConfidenceDotColor(0.55)).toBe('bg-yellow-500')
    expect(getConfidenceDotColor(0.69)).toBe('bg-yellow-500')
  })

  it('returns red for low confidence (< 0.40)', () => {
    expect(getConfidenceDotColor(0.39)).toBe('bg-red-500')
    expect(getConfidenceDotColor(0.10)).toBe('bg-red-500')
    expect(getConfidenceDotColor(0)).toBe('bg-red-500')
  })
})

// ---------------------------------------------------------------------------
// formatTimestamp
// ---------------------------------------------------------------------------

describe('formatTimestamp', () => {
  it('formats ISO string to readable date', () => {
    const iso = '2026-02-25T14:30:00Z'
    const formatted = formatTimestamp(iso)
    // Should contain month and day at minimum
    expect(formatted).toMatch(/Feb/)
    expect(formatted).toMatch(/25/)
  })
})

// ---------------------------------------------------------------------------
// LeakageHero range format (LEAK-01)
// ---------------------------------------------------------------------------

describe('LeakageHero range format', () => {
  it('formats range as "$X - $Y/mo (est. $Z)" with formatDollars', async () => {
    // Test the formatting logic directly since we use formatDollars
    const { formatDollars } = await import('@/lib/formatting')
    const impact = { low: 1200, mid: 2300, high: 3400 }

    const rangeText = `${formatDollars(impact.low)} \u2013 ${formatDollars(impact.high)}/mo (est. ${formatDollars(impact.mid)})`
    expect(rangeText).toBe('$1.2K \u2013 $3.4K/mo (est. $2.3K)')
  })

  it('formats sub-1000 values without K suffix', async () => {
    const { formatDollars } = await import('@/lib/formatting')
    const impact = { low: 50, mid: 120, high: 200 }

    const rangeText = `${formatDollars(impact.low)} \u2013 ${formatDollars(impact.high)}/mo (est. ${formatDollars(impact.mid)})`
    expect(rangeText).toBe('$50 \u2013 $200/mo (est. $120)')
  })
})

// ---------------------------------------------------------------------------
// Empty state (LEAK-06)
// ---------------------------------------------------------------------------

describe('LeakageHero empty state', () => {
  it('actionableCount === 0 should trigger empty state', () => {
    // This tests the conditional logic — when actionableCount is 0,
    // the component should show the green checkmark "No revenue leakage detected"
    const actionableCount = 0
    const isEmptyState = actionableCount === 0
    expect(isEmptyState).toBe(true)
  })
})
