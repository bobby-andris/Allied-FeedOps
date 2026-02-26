import { median } from 'simple-statistics'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { BcgQuadrant, LongTailBucket, MonthlySearchVolume } from './types'
import { LONG_TAIL_BUCKETS, SEASONAL_THRESHOLD } from './constants'

/**
 * Fetch the latest "major" period from the MV (>500 unique terms).
 * Falls back to the most recent period if none qualifies.
 */
export async function fetchLatestPeriod(supabase: SupabaseClient): Promise<string | null> {
  const { data, error } = await supabase.rpc('market_intelligence_latest_period')
  if (error || !data) return null
  return data as string
}

/**
 * Fetch the prior major period (the one before the latest).
 * Used for new term detection (comparing current vs prior).
 */
export async function fetchPriorPeriod(supabase: SupabaseClient, latestPeriod: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('market_intelligence_mv')
    .select('period_start')
    .lt('period_start', latestPeriod)
    .order('period_start', { ascending: false })
    .limit(1)
  if (error || !data || data.length === 0) return null
  // Only return if it's a "major" period (check term count)
  const period = data[0].period_start as string
  const { count } = await supabase
    .from('market_intelligence_mv')
    .select('*', { count: 'exact', head: true })
    .eq('period_start', period)
  if ((count ?? 0) < 500) return null
  return period
}

/**
 * Paginate through an RPC call that may exceed Supabase's 1000-row server limit.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function paginateRpc<T>(supabase: SupabaseClient, fnName: string, params: Record<string, unknown>, pageSize = 1000): Promise<T[]> {
  const all: T[] = []
  let offset = 0
  while (true) {
    const { data, error } = await supabase
      .rpc(fnName, params)
      .range(offset, offset + pageSize - 1)
    if (error) throw error
    if (!data || (data as T[]).length === 0) break
    all.push(...(data as T[]))
    if ((data as T[]).length < pageSize) break
    offset += pageSize
  }
  return all
}

export function classifyQuadrant(
  roas: number,
  revenue: number,
  medianRoas: number,
  medianRevenue: number
): BcgQuadrant {
  // Use strict > for median so values at exactly the median fall to the lower quadrant.
  // This prevents all-Stars when many groups sit at 0.
  if (roas > medianRoas && revenue > medianRevenue) return 'star'
  if (roas > medianRoas && revenue <= medianRevenue) return 'cashCow'
  if (roas <= medianRoas && revenue > medianRevenue) return 'questionMark'
  return 'dog'
}

export function computeMedians(values: number[]): number {
  if (values.length === 0) return 0
  return median(values)
}

export function computeTrendDirection(change: number): 'up' | 'down' | 'flat' {
  if (change > 5) return 'up'
  if (change < -5) return 'down'
  return 'flat'
}

export function classifySeasonalDirection(changePercent: number): 'spiking' | 'declining' | 'stable' {
  if (changePercent > SEASONAL_THRESHOLD) return 'spiking'
  if (changePercent < -SEASONAL_THRESHOLD) return 'declining'
  return 'stable'
}

export function getWordCount(queryText: string): number {
  return queryText.trim().split(/\s+/).length
}

export function getLongTailBucketLabel(wordCount: number): string {
  const bucket = LONG_TAIL_BUCKETS.find(b => wordCount >= b.min && wordCount <= b.max)
  return bucket?.label ?? '5+ words'
}

export function parseMonthlySearchVolumes(raw: unknown): MonthlySearchVolume[] {
  if (!raw) return []
  // monthly_searches JSONB may be stored as text string per project conventions
  const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (!Array.isArray(parsed)) return []
  return parsed.map((entry: { year?: number; month?: number; monthly_searches?: number; searches?: number }) => {
    let year = entry.year ?? 0
    let month = entry.month ?? 0
    // Google Keyword Planner uses month 13 to represent January of the next year
    if (month > 12) {
      year += Math.floor((month - 1) / 12)
      month = ((month - 1) % 12) + 1
    }
    return {
      year,
      month,
      searches: entry.monthly_searches ?? entry.searches ?? 0,
    }
  })
}

export function computeMoMChange(volumes: MonthlySearchVolume[]): { current: number; prior: number; changePercent: number } {
  if (volumes.length < 2) return { current: 0, prior: 0, changePercent: 0 }
  // Sort descending by year/month
  const sorted = [...volumes].sort((a, b) => b.year - a.year || b.month - a.month)
  const current = sorted[0].searches
  const prior = sorted[1].searches
  const changePercent = prior > 0 ? ((current - prior) / prior) * 100 : 0
  return { current, prior, changePercent }
}

export function matchesCompetitor(queryText: string, tokens: readonly string[]): string[] {
  const lower = queryText.toLowerCase()
  return tokens.filter(token => lower.includes(token))
}

export function isBrandTerm(queryText: string, brandTokens: readonly string[]): boolean {
  const lower = queryText.toLowerCase()
  return brandTokens.some(token => lower.includes(token))
}

export function costMicrosToDollars(micros: number): number {
  return micros / 1_000_000
}

export function buildLongTailBuckets(
  terms: Array<{ queryText: string; roas: number; cvr: number; impressions: number; conversions: number; revenue: number; spend: number }>
): LongTailBucket[] {
  const bucketMap = new Map<string, typeof terms>()

  for (const bucket of LONG_TAIL_BUCKETS) {
    bucketMap.set(bucket.label, [])
  }

  for (const term of terms) {
    const wc = getWordCount(term.queryText)
    const label = getLongTailBucketLabel(wc)
    bucketMap.get(label)?.push(term)
  }

  return LONG_TAIL_BUCKETS.map(bucket => {
    const items = bucketMap.get(bucket.label) ?? []
    const totalImpressions = items.reduce((s, t) => s + t.impressions, 0)
    const totalConversions = items.reduce((s, t) => s + t.conversions, 0)
    const totalRevenue = items.reduce((s, t) => s + t.revenue, 0)
    const totalSpend = items.reduce((s, t) => s + t.spend, 0)
    const totalClicks = items.reduce((s, t) => s + (t.impressions > 0 ? t.impressions : 0), 0)
    return {
      wordCountRange: bucket.label,
      termCount: items.length,
      avgRoas: totalSpend > 0 ? totalRevenue / totalSpend : 0,
      avgCvr: items.length > 0 ? totalConversions / Math.max(totalClicks, 1) : 0,
      totalImpressions,
      totalConversions,
      totalRevenue,
      totalSpend,
    }
  })
}
