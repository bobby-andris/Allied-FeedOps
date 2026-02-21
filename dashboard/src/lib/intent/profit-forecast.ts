/**
 * Full COGS/Returns Integration + Lag-Adjusted Profit forecasting.
 *
 * Provides ROAS adjustments for cost-of-goods-sold and return rates,
 * with optional conversion lag adjustment.
 */

import type { SupabaseClient } from '@supabase/supabase-js'
import type { PromotionDemotionDecision, TermMetrics } from '@/lib/intent/types'

export interface ProfitSignals {
  /** Average COGS rate as a fraction of revenue (e.g., 0.35 = 35%). */
  cogsRate: number
  /** Average return rate as a fraction of orders (e.g., 0.08 = 8%). */
  returnRate: number
  /** How many days old the underlying data is. */
  dataAge: number
}

export interface MarginAdjustedDecision extends PromotionDemotionDecision {
  /** The original action before margin adjustment. */
  originalAction: PromotionDemotionDecision['action']
  /** Whether the action was downgraded due to margin pressure. */
  marginDowngraded: boolean
  /** The profit-adjusted ROAS used for the decision. */
  profitAdjustedRoas: number
}

/**
 * Default lag adjustment factor for 7-day conversion lag.
 * Accounts for conversions that haven't been attributed yet.
 * Factor > 1 means we expect more revenue to arrive.
 */
const DEFAULT_LAG_FACTOR = 1.12

/** Tier ROAS floors — below this, the action should be downgraded. */
const TIER_ROAS_FLOORS: Record<string, number> = {
  promote_to_high: 3.6,
  promote_to_medium: 3.1,
  hold: 2.6,
  demote_to_medium: 2.6,
  demote_to_low: 0,
  negative: 0,
}

/**
 * Calculates ROAS adjusted for COGS and returns, with optional conversion lag.
 *
 * Formula:
 *   effectiveRevenue = conversionsValue * (1 - returnRate) - (conversionsValue * cogsRate)
 *   lagAdjustedRevenue = effectiveRevenue * lagFactor
 *   ROAS = lagAdjustedRevenue / spend
 *
 * @param metrics - Term performance metrics
 * @param cogsRate - COGS as fraction of revenue (0-1)
 * @param returnRate - Return rate as fraction (0-1)
 * @param lagDays - Optional lag days; controls the lag adjustment factor
 * @returns Lag-adjusted, margin-aware ROAS
 */
export function calculateLagAdjustedROAS(
  metrics: TermMetrics,
  cogsRate: number,
  returnRate: number,
  lagDays?: number
): number {
  const spend = metrics.costMicros / 1_000_000
  if (spend <= 0) return 0

  const revenue = metrics.conversionsValue
  const netRevenue = revenue * (1 - returnRate) - revenue * cogsRate

  // Apply lag factor — if lagDays is provided, scale proportionally to 7-day baseline
  const lagFactor = lagDays != null ? 1 + (DEFAULT_LAG_FACTOR - 1) * (lagDays / 7) : DEFAULT_LAG_FACTOR
  const lagAdjustedRevenue = netRevenue * lagFactor

  return lagAdjustedRevenue / spend
}

/**
 * Fetches the latest COGS rate and return rate from the database.
 * Falls back to conservative defaults if tables don't exist or are empty.
 */
export async function fetchProfitSignals(supabase: SupabaseClient): Promise<ProfitSignals> {
  const now = new Date()

  // Try to fetch latest COGS from sku_margin_daily
  let cogsRate = 0.35 // conservative default
  let cogsAge = 30

  try {
    const { data: cogsData } = await supabase
      .from('sku_margin_daily')
      .select('cogs_rate, report_date')
      .order('report_date', { ascending: false })
      .limit(1)
      .single()

    if (cogsData?.cogs_rate != null) {
      cogsRate = Number(cogsData.cogs_rate)
      const reportDate = new Date(cogsData.report_date)
      cogsAge = Math.floor((now.getTime() - reportDate.getTime()) / (1000 * 60 * 60 * 24))
    }
  } catch {
    // Table may not exist yet — use defaults
  }

  // Try to fetch latest return rate from order_line_returns_daily
  let returnRate = 0.05 // conservative default
  let returnAge = 30

  try {
    const { data: returnData } = await supabase
      .from('order_line_returns_daily')
      .select('return_rate, report_date')
      .order('report_date', { ascending: false })
      .limit(1)
      .single()

    if (returnData?.return_rate != null) {
      returnRate = Number(returnData.return_rate)
      const reportDate = new Date(returnData.report_date)
      returnAge = Math.floor((now.getTime() - reportDate.getTime()) / (1000 * 60 * 60 * 24))
    }
  } catch {
    // Table may not exist yet — use defaults
  }

  return {
    cogsRate,
    returnRate,
    dataAge: Math.max(cogsAge, returnAge),
  }
}

/**
 * Wraps a PromotionDemotionDecision with margin-awareness.
 * If the profit-adjusted ROAS falls below the tier floor for the recommended action,
 * the action is downgraded.
 */
export function buildMarginAdjustedDecision(
  policyDecision: PromotionDemotionDecision,
  profitSignals: ProfitSignals,
  metrics: TermMetrics
): MarginAdjustedDecision {
  const profitAdjustedRoas = calculateLagAdjustedROAS(
    metrics,
    profitSignals.cogsRate,
    profitSignals.returnRate
  )

  const floor = TIER_ROAS_FLOORS[policyDecision.action] ?? 0

  // Only downgrade promotion actions (not hold/demote/negative)
  const isPromotion =
    policyDecision.action === 'promote_to_high' ||
    policyDecision.action === 'promote_to_medium'

  if (isPromotion && profitAdjustedRoas < floor) {
    // Downgrade: promote_to_high → hold, promote_to_medium → hold
    return {
      ...policyDecision,
      action: 'hold',
      originalAction: policyDecision.action,
      marginDowngraded: true,
      profitAdjustedRoas,
      reasonCodes: [...policyDecision.reasonCodes, 'margin_adjusted_below_floor'],
    }
  }

  return {
    ...policyDecision,
    originalAction: policyDecision.action,
    marginDowngraded: false,
    profitAdjustedRoas,
  }
}
