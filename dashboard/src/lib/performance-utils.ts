import type { PerformanceStatus } from './supabase/types'

// Category average CTR benchmarks (hardcoded for MVP)
// TODO: Query from category_performance_benchmarks table when implemented
const CATEGORY_AVG_CTR: Record<string, number> = {
  'Bathroom Accessories': 0.041,  // 4.1%
  'Cabinet Hardware': 0.038,       // 3.8%
  'Door Hardware': 0.035,          // 3.5%
  'default': 0.038,                // 3.8% fallback
}

/**
 * Calculate performance status based on CTR comparison
 *
 * Status Logic:
 * - good: CTR >= category average AND improving from baseline
 * - warning: CTR < category average OR declining from baseline
 * - critical: CTR >20% below category average
 * - no-data: No current CTR available
 */
export function calculatePerformanceStatus(
  current_ctr: number | null | undefined,
  baseline_ctr: number | null | undefined,
  category_avg_ctr: number = CATEGORY_AVG_CTR.default
): PerformanceStatus {
  if (!current_ctr || current_ctr === 0) {
    return 'no-data'
  }

  const vs_category = current_ctr / category_avg_ctr
  const is_improving = baseline_ctr ? current_ctr >= baseline_ctr : true

  // Critical: >20% below category average
  if (vs_category < 0.8) {
    return 'critical'
  }

  // Good: >= category average AND improving
  if (vs_category >= 1.0 && is_improving) {
    return 'good'
  }

  // Warning: below average OR declining
  return 'warning'
}

/**
 * Format metric change as percentage string
 * Returns: "+X.X%" or "-X.X%" or "—" if no baseline
 */
export function formatMetricChange(
  current: number | null | undefined,
  baseline: number | null | undefined
): string {
  if (!current || !baseline || baseline === 0) {
    return '—'
  }

  const pct = ((current - baseline) / baseline) * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

/**
 * Format large numbers with K/M suffix
 * Examples: 1234 -> "1.2K", 1234567 -> "1.2M"
 */
export function formatNumber(value: number | null | undefined): string {
  if (!value || value === 0) return '0'

  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return value.toLocaleString()
}

/**
 * Format currency values
 * Examples: 2847 -> "$2,847", 2847.50 -> "$2,847.50"
 */
export function formatCurrency(value: number | null | undefined): string {
  if (!value || value === 0) return '$0'

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Format percentage values
 * Examples: 0.032 -> "3.2%", 0.041 -> "4.1%"
 */
export function formatPercentage(value: number | null | undefined): string {
  if (!value || value === 0) return '0%'

  return `${(value * 100).toFixed(1)}%`
}

/**
 * Get status indicator label text
 */
export function getStatusLabel(status: PerformanceStatus): string {
  switch (status) {
    case 'good':
      return 'above avg'
    case 'warning':
      return 'below avg'
    case 'critical':
      return 'critical'
    case 'no-data':
      return 'no data'
  }
}

/**
 * Get status indicator color classes
 */
export function getStatusColor(status: PerformanceStatus): string {
  switch (status) {
    case 'good':
      return 'bg-green-500'
    case 'warning':
      return 'bg-yellow-500'
    case 'critical':
      return 'bg-red-500'
    case 'no-data':
      return 'bg-gray-500'
  }
}

/**
 * Get status glow effect classes
 */
export function getStatusGlow(status: PerformanceStatus): string {
  switch (status) {
    case 'good':
      return 'shadow-[0_0_8px_rgba(16,185,129,0.3)]'
    case 'warning':
      return 'shadow-[0_0_8px_rgba(245,158,11,0.3)]'
    case 'critical':
      return 'shadow-[0_0_8px_rgba(239,68,68,0.3)]'
    case 'no-data':
      return 'shadow-none'
  }
}

/**
 * Get category average CTR by category name
 */
export function getCategoryAvgCTR(category?: string): number {
  if (!category) return CATEGORY_AVG_CTR.default
  return CATEGORY_AVG_CTR[category] || CATEGORY_AVG_CTR.default
}
