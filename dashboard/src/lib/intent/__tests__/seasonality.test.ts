import { describe, expect, it } from 'vitest'
import {
  getSeasonalContext,
  getSeasonalModifiers,
  applySeasonalAdjustment,
} from '@/lib/intent/seasonality'
import type { SeasonContext } from '@/lib/intent/seasonality'

describe('getSeasonalContext', () => {
  it('detects January as holiday season', () => {
    const result = getSeasonalContext(new Date('2026-01-15'))
    expect(result.season).toBe('holiday')
    expect(result.month).toBe(0)
  })

  it('detects February as standard', () => {
    const result = getSeasonalContext(new Date('2026-02-10'))
    expect(result.season).toBe('standard')
  })

  it('detects March as spring-refresh', () => {
    const result = getSeasonalContext(new Date(2026, 2, 15))
    expect(result.season).toBe('spring-refresh')
  })

  it('detects April as spring-refresh', () => {
    const result = getSeasonalContext(new Date('2026-04-20'))
    expect(result.season).toBe('spring-refresh')
  })

  it('detects May as standard', () => {
    const result = getSeasonalContext(new Date('2026-05-15'))
    expect(result.season).toBe('standard')
  })

  it('detects June as summer', () => {
    const result = getSeasonalContext(new Date('2026-06-15'))
    expect(result.season).toBe('summer')
  })

  it('detects July as summer', () => {
    const result = getSeasonalContext(new Date('2026-07-04'))
    expect(result.season).toBe('summer')
  })

  it('detects August as back-to-school', () => {
    const result = getSeasonalContext(new Date('2026-08-20'))
    expect(result.season).toBe('back-to-school')
  })

  it('detects September as back-to-school', () => {
    const result = getSeasonalContext(new Date('2026-09-10'))
    expect(result.season).toBe('back-to-school')
  })

  it('detects October as standard', () => {
    const result = getSeasonalContext(new Date('2026-10-15'))
    expect(result.season).toBe('standard')
  })

  it('detects November as Q4-holiday', () => {
    const result = getSeasonalContext(new Date('2026-11-25'))
    expect(result.season).toBe('Q4-holiday')
  })

  it('detects December as Q4-holiday', () => {
    const result = getSeasonalContext(new Date('2026-12-20'))
    expect(result.season).toBe('Q4-holiday')
  })

  it('uses current date when no date provided', () => {
    const result = getSeasonalContext()
    expect(result.season).toBeDefined()
    expect(result.label).toBeDefined()
    expect(result.month).toBeGreaterThanOrEqual(0)
    expect(result.month).toBeLessThanOrEqual(11)
  })

  it('returns a human-readable label', () => {
    const result = getSeasonalContext(new Date('2026-12-01'))
    expect(result.label).toBe('Q4 Holiday Season')
  })
})

describe('getSeasonalModifiers', () => {
  it('returns multiplier < 1 for holiday (easier promotions)', () => {
    const mod = getSeasonalModifiers('holiday')
    expect(mod).toBeLessThan(1)
    expect(mod).toBe(0.85)
  })

  it('returns multiplier < 1 for Q4-holiday', () => {
    const mod = getSeasonalModifiers('Q4-holiday')
    expect(mod).toBeLessThan(1)
    expect(mod).toBe(0.80)
  })

  it('returns multiplier < 1 for back-to-school', () => {
    const mod = getSeasonalModifiers('back-to-school')
    expect(mod).toBeLessThan(1)
    expect(mod).toBe(0.90)
  })

  it('returns multiplier < 1 for spring-refresh', () => {
    const mod = getSeasonalModifiers('spring-refresh')
    expect(mod).toBeLessThan(1)
    expect(mod).toBe(0.92)
  })

  it('returns multiplier of 1.0 for summer', () => {
    const mod = getSeasonalModifiers('summer')
    expect(mod).toBe(1.0)
  })

  it('returns multiplier of 1.0 for standard', () => {
    const mod = getSeasonalModifiers('standard')
    expect(mod).toBe(1.0)
  })

  it('returns valid multipliers for all known seasons', () => {
    const seasons: SeasonContext[] = [
      'holiday',
      'back-to-school',
      'spring-refresh',
      'summer',
      'Q4-holiday',
      'standard',
    ]
    for (const season of seasons) {
      const mod = getSeasonalModifiers(season)
      expect(mod).toBeGreaterThan(0)
      expect(mod).toBeLessThanOrEqual(1.0)
    }
  })
})

describe('applySeasonalAdjustment', () => {
  it('lowers threshold during Q4-holiday', () => {
    const adjusted = applySeasonalAdjustment(100, 'Q4-holiday')
    expect(adjusted).toBe(80)
  })

  it('lowers threshold during holiday', () => {
    const adjusted = applySeasonalAdjustment(80, 'holiday')
    expect(adjusted).toBe(68)
  })

  it('keeps threshold unchanged during standard season', () => {
    const adjusted = applySeasonalAdjustment(80, 'standard')
    expect(adjusted).toBe(80)
  })

  it('applies back-to-school modifier correctly', () => {
    const adjusted = applySeasonalAdjustment(100, 'back-to-school')
    expect(adjusted).toBe(90)
  })

  it('applies spring-refresh modifier correctly', () => {
    const adjusted = applySeasonalAdjustment(100, 'spring-refresh')
    expect(adjusted).toBeCloseTo(92)
  })

  it('handles zero base threshold', () => {
    const adjusted = applySeasonalAdjustment(0, 'Q4-holiday')
    expect(adjusted).toBe(0)
  })
})
