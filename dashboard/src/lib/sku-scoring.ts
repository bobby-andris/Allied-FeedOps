/**
 * SKU Scoring and Selection Library
 *
 * Implements strategic tier-based SKU selection for content optimization:
 * - Tier 1 (20%): High conversion, low traffic - proven winners to protect
 * - Tier 2 (50%): Mid-pack - primary test bed
 * - Tier 3 (20%): High traffic, low conversion - largest upside potential
 * - Fill (10%): Category diversity completion
 * - Excluded: Top 5% revenue (too risky to experiment with)
 */

export interface SkuMetrics {
  master_sku: string
  product_name?: string
  category?: string
  impressions: number
  clicks: number
  conversions: number
  revenue: number
  cost: number
  variant_count?: number
  already_optimized?: boolean
  // Performance baseline fields (optional - for prioritization boosting)
  baseline_ctr?: number
  ctr_trend?: number  // Percentage change in CTR (e.g., -0.15 for 15% decline)
}

export interface ScoredSku extends SkuMetrics {
  ctr: number
  cvr: number
  roas: number
  tier: 'tier1' | 'tier2' | 'tier3' | 'fill' | 'excluded'
  score: number
  tierReason: string
}

export interface SelectionResult {
  recommended: ScoredSku[]
  distribution: {
    tier1: number
    tier2: number
    tier3: number
    fill: number
  }
  excluded: {
    top_revenue: string[]
    already_optimized: string[]
    insufficient_data: string[]
  }
  total_eligible: number
}

/**
 * Calculate percentile values for an array of numbers
 */
function calculatePercentiles(values: number[]): number[] {
  return [...values].sort((a, b) => a - b)
}

/**
 * Get the percentile rank (0-100) of a value within a sorted array
 */
function getPercentile(value: number, sortedValues: number[]): number {
  if (sortedValues.length === 0) return 50
  const index = sortedValues.findIndex((v) => v >= value)
  if (index === -1) return 100
  if (index === 0) return 0
  return (index / sortedValues.length) * 100
}

/**
 * Calculate an optimization score (0-100) based on metrics
 * Higher score = better candidate for optimization
 */
function calculateOptimizationScore(
  impPct: number,
  cvrPct: number,
  clicks: number,
  impressions: number,
  ctr: number,
  baselineCtr?: number,
  ctrTrend?: number
): number {
  // Penalize extremes, reward middle ground (more room to improve)
  const trafficScore = 100 - Math.abs(impPct - 50) * 2
  const conversionScore = 100 - Math.abs(cvrPct - 50) * 2

  // Bonus for having enough data (statistical significance)
  const dataBonus = Math.min(clicks / 100, 20)

  // Slight bonus for higher impressions (more visible impact)
  const visibilityBonus = Math.min(impPct / 5, 10)

  let baseScore = Math.round(
    (trafficScore + conversionScore) / 2 + dataBonus + visibilityBonus
  )

  // === PERFORMANCE-BASED PRIORITIZATION ===

  // Boost priority for high-traffic, low-CTR products (need optimization most)
  // Category average CTR for Shopping ads is typically 0.9-1.2%
  const categoryAverageCtr = 1.0
  if (impressions > 10000 && ctr < categoryAverageCtr * 0.8) {
    // High traffic but CTR 20% below average = big opportunity
    baseScore = Math.round(baseScore * 1.5)
  }

  // Boost for products with declining performance
  if (ctrTrend !== undefined && ctrTrend < -0.1) {
    // 10% or more decline in CTR = needs attention
    baseScore = Math.round(baseScore * 1.3)
  }

  // Additional boost for products significantly below their own baseline
  if (baselineCtr !== undefined && baselineCtr > 0) {
    const ctrVsBaseline = (ctr - baselineCtr) / baselineCtr
    if (ctrVsBaseline < -0.2) {
      // CTR dropped 20% or more from baseline = urgent
      baseScore = Math.round(baseScore * 1.4)
    }
  }

  return Math.min(baseScore, 200) // Cap at 200 to prevent extreme scores
}

/**
 * Assign tier based on percentile metrics
 */
function assignTier(
  cvrPct: number,
  impPct: number,
  revPct: number
): { tier: ScoredSku['tier']; reason: string } {
  // Top 5% revenue - exclude from experiments
  if (revPct >= 95) {
    return { tier: 'excluded', reason: 'Top 5% revenue - protected from experiments' }
  }

  // Tier 1: High conversion, low traffic (hidden gems)
  if (cvrPct >= 70 && impPct <= 50) {
    return {
      tier: 'tier1',
      reason: 'High conversion rate with low visibility - proven performer',
    }
  }

  // Tier 3: High traffic, low conversion (opportunity)
  if (impPct >= 70 && cvrPct <= 30) {
    return {
      tier: 'tier3',
      reason: 'High visibility but low conversion - largest upside potential',
    }
  }

  // Tier 2: Everything else (mid-pack)
  return { tier: 'tier2', reason: 'Mid-pack performance - primary test candidate' }
}

/**
 * Score all SKUs based on their performance metrics
 */
export function scoreSkus(skus: SkuMetrics[]): ScoredSku[] {
  if (skus.length === 0) return []

  // Calculate derived metrics
  const withMetrics = skus.map((sku) => ({
    ...sku,
    ctr: sku.impressions > 0 ? (sku.clicks / sku.impressions) * 100 : 0,
    cvr: sku.clicks > 0 ? (sku.conversions / sku.clicks) * 100 : 0,
    roas: sku.cost > 0 ? sku.revenue / sku.cost : 0,
  }))

  // Calculate percentile arrays
  const cvrValues = withMetrics.map((s) => s.cvr)
  const revenueValues = withMetrics.map((s) => s.revenue)
  const impressionValues = withMetrics.map((s) => s.impressions)

  const cvrPercentiles = calculatePercentiles(cvrValues)
  const revenuePercentiles = calculatePercentiles(revenueValues)
  const impressionPercentiles = calculatePercentiles(impressionValues)

  // Assign tiers and scores
  return withMetrics.map((sku) => {
    const cvrPct = getPercentile(sku.cvr, cvrPercentiles)
    const revPct = getPercentile(sku.revenue, revenuePercentiles)
    const impPct = getPercentile(sku.impressions, impressionPercentiles)

    const { tier, reason } = assignTier(cvrPct, impPct, revPct)
    const score = calculateOptimizationScore(
      impPct,
      cvrPct,
      sku.clicks,
      sku.impressions,
      sku.ctr,
      sku.baseline_ctr,
      sku.ctr_trend
    )

    return {
      ...sku,
      tier,
      score,
      tierReason: reason,
    }
  })
}

/**
 * Select the best SKUs for optimization based on tier distribution
 *
 * @param scoredSkus - Already scored SKUs
 * @param count - Number of SKUs to select
 * @param excludeOptimized - Whether to exclude already optimized SKUs
 */
export function selectSkus(
  scoredSkus: ScoredSku[],
  count: number,
  excludeOptimized: boolean = true
): SelectionResult {
  const excludedTopRevenue: string[] = []
  const excludedOptimized: string[] = []
  const excludedInsufficientData: string[] = []

  // Filter out excluded tiers
  let eligible = scoredSkus.filter((s) => {
    if (s.tier === 'excluded') {
      excludedTopRevenue.push(s.master_sku)
      return false
    }
    return true
  })

  // Optionally filter out already optimized
  if (excludeOptimized) {
    eligible = eligible.filter((s) => {
      if (s.already_optimized) {
        excludedOptimized.push(s.master_sku)
        return false
      }
      return true
    })
  }

  // Separate SKUs with insufficient data (less than 100 impressions)
  // These are still eligible as "fill" tier candidates — they need content generation
  const withData = eligible.filter((s) => s.impressions >= 100)
  const noData = eligible.filter((s) => s.impressions < 100)
  for (const s of noData) {
    excludedInsufficientData.push(s.master_sku)
  }
  eligible = withData

  // Target distribution
  const targetDist = {
    tier1: Math.round(count * 0.2),
    tier2: Math.round(count * 0.5),
    tier3: Math.round(count * 0.2),
    fill: Math.round(count * 0.1),
  }

  // Select from each tier (sorted by score)
  const tier1 = eligible
    .filter((s) => s.tier === 'tier1')
    .sort((a, b) => b.score - a.score)
    .slice(0, targetDist.tier1)

  const tier2 = eligible
    .filter((s) => s.tier === 'tier2')
    .sort((a, b) => b.score - a.score)
    .slice(0, targetDist.tier2)

  const tier3 = eligible
    .filter((s) => s.tier === 'tier3')
    .sort((a, b) => b.score - a.score)
    .slice(0, targetDist.tier3)

  // Fill with remaining high-score SKUs for diversity
  const selected = new Set([...tier1, ...tier2, ...tier3].map((s) => s.master_sku))
  const fillFromEligible = eligible
    .filter((s) => !selected.has(s.master_sku))
    .sort((a, b) => b.score - a.score)
    .slice(0, targetDist.fill)

  // Calculate how many slots remain unfilled
  const filledSoFar = tier1.length + tier2.length + tier3.length + fillFromEligible.length
  const remainingSlots = Math.max(0, count - filledSoFar)

  // Backfill remaining slots with no-data SKUs (new products needing content)
  // Assign them as "fill" tier since they have no performance data for tiering
  const noDataFill: ScoredSku[] = noData
    .slice(0, remainingSlots)
    .map((s) => ({ ...s, tier: 'fill' as const, tierReason: 'No performance data - new content candidate' }))

  const fillCandidates = [...fillFromEligible, ...noDataFill]

  // Combine and sort by score (no-data SKUs sort last with score 0)
  const recommended = [...tier1, ...tier2, ...tier3, ...fillCandidates].sort(
    (a, b) => b.score - a.score
  )

  return {
    recommended,
    distribution: {
      tier1: tier1.length,
      tier2: tier2.length,
      tier3: tier3.length,
      fill: fillCandidates.length,
    },
    excluded: {
      top_revenue: excludedTopRevenue,
      already_optimized: excludedOptimized,
      insufficient_data: excludedInsufficientData,
    },
    total_eligible: eligible.length + noData.length,
  }
}
