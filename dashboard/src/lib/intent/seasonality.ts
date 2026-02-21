/**
 * Seasonality module for Adaptive Subclass Rules.
 *
 * Provides season detection, seasonal modifiers for promotion thresholds,
 * and threshold adjustment helpers.
 */

export type SeasonContext =
  | 'holiday'
  | 'back-to-school'
  | 'spring-refresh'
  | 'summer'
  | 'Q4-holiday'
  | 'standard'

export interface SeasonInfo {
  season: SeasonContext
  label: string
  month: number
}

/**
 * Month-to-season mapping:
 *   Jan       → holiday (post-holiday / New Year sales)
 *   Feb       → standard
 *   Mar–Apr   → spring-refresh
 *   May       → standard
 *   Jun–Jul   → summer
 *   Aug–Sep   → back-to-school
 *   Oct       → standard (pre-Q4 ramp)
 *   Nov–Dec   → Q4-holiday
 */
const MONTH_SEASON_MAP: Record<number, SeasonContext> = {
  0: 'holiday',        // January
  1: 'standard',       // February
  2: 'spring-refresh', // March
  3: 'spring-refresh', // April
  4: 'standard',       // May
  5: 'summer',         // June
  6: 'summer',         // July
  7: 'back-to-school', // August
  8: 'back-to-school', // September
  9: 'standard',       // October
  10: 'Q4-holiday',    // November
  11: 'Q4-holiday',    // December
}

const SEASON_LABELS: Record<SeasonContext, string> = {
  'holiday': 'Post-Holiday / New Year',
  'back-to-school': 'Back to School',
  'spring-refresh': 'Spring Refresh',
  'summer': 'Summer',
  'Q4-holiday': 'Q4 Holiday Season',
  'standard': 'Standard',
}

/**
 * Seasonal multipliers for promotion thresholds.
 * Values < 1 mean lower thresholds (easier to promote — capture demand).
 * Values > 1 mean higher thresholds (more conservative).
 */
const SEASONAL_MODIFIERS: Record<SeasonContext, number> = {
  'holiday': 0.85,
  'back-to-school': 0.90,
  'spring-refresh': 0.92,
  'summer': 1.0,
  'Q4-holiday': 0.80,
  'standard': 1.0,
}

/**
 * Returns the current season context based on the given date (defaults to now).
 */
export function getSeasonalContext(date?: Date): SeasonInfo {
  const d = date ?? new Date()
  const month = d.getMonth()
  const season = MONTH_SEASON_MAP[month] ?? 'standard'

  return {
    season,
    label: SEASON_LABELS[season],
    month,
  }
}

/**
 * Returns the multiplier for promotion thresholds during the given season.
 * A multiplier < 1 lowers thresholds (makes promotions easier).
 */
export function getSeasonalModifiers(season: SeasonContext): number {
  return SEASONAL_MODIFIERS[season] ?? 1.0
}

/**
 * Adjusts a policy threshold by the seasonal multiplier.
 * Example: baseThreshold=80, Q4-holiday multiplier=0.80 → 64
 */
export function applySeasonalAdjustment(baseThreshold: number, season: SeasonContext): number {
  const multiplier = getSeasonalModifiers(season)
  return baseThreshold * multiplier
}
