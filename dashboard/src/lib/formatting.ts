/**
 * Shared formatting utilities for the dashboard.
 */

/**
 * Format a dollar amount for display.
 * - >= 1000: "$1.2K"
 * - < 1000: "$850"
 * - Handles negative values correctly
 */
export function formatDollars(amount: number): string {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
