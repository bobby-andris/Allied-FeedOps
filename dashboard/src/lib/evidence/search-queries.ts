/**
 * Search query insights integration for evidence table
 *
 * Fetches search queries from Supabase (collected via Google Ads
 * search_term_view) and formats them as Evidence rows for LLM prompts.
 */

import type { SupabaseClient } from '@supabase/supabase-js'
import type { Evidence } from './types'
import type { CompetitionLevel } from '@/lib/supabase/types'

/**
 * Search query insight from Supabase
 */
export interface SearchQueryInsight {
  query_text: string
  total_impressions: number
  total_clicks: number
  avg_monthly_searches: number | null
  competition: CompetitionLevel | null
}

/**
 * Variant-level search query
 */
export interface VariantSearchQuery {
  query_text: string
  impressions: number
  clicks: number
}

/**
 * Fetch top search queries aggregated at master SKU level
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU to fetch queries for
 * @param limit - Maximum number of queries to return
 * @param minImpressions - Minimum total impressions threshold
 * @returns List of search query insights
 */
export async function getSearchQueriesForMasterSku(
  supabase: SupabaseClient,
  masterSku: string,
  limit: number = 15,
  minImpressions: number = 10
): Promise<SearchQueryInsight[]> {
  try {
    const { data, error } = await supabase
      .from('search_queries_by_master_sku')
      .select('query_text, total_impressions, total_clicks, avg_monthly_searches, competition')
      .eq('master_sku', masterSku)
      .gte('total_impressions', minImpressions)
      .order('total_impressions', { ascending: false })
      .limit(limit)

    if (error) {
      console.warn(`Failed to fetch search queries for ${masterSku}:`, error.message)
      return []
    }

    return data ?? []
  } catch (err) {
    console.warn(`Error fetching search queries for ${masterSku}:`, err)
    return []
  }
}

/**
 * Fetch search queries specific to a variant (finish)
 *
 * For Google/Bing variant-level content generation, fetches queries
 * associated with specific finish codes.
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU
 * @param finishCode - Finish code (e.g., "PB", "SN")
 * @param limit - Maximum number of queries to return
 * @returns List of variant search queries
 */
export async function getSearchQueriesForVariant(
  supabase: SupabaseClient,
  masterSku: string,
  finishCode: string,
  limit: number = 10
): Promise<VariantSearchQuery[]> {
  try {
    const { data, error } = await supabase
      .from('search_queries')
      .select('query_text, impressions, clicks')
      .eq('master_sku', masterSku)
      .eq('finish_code', finishCode)
      .order('impressions', { ascending: false })
      .limit(limit)

    if (error) {
      console.warn(`Failed to fetch variant queries for ${masterSku}/${finishCode}:`, error.message)
      return []
    }

    return data ?? []
  } catch (err) {
    console.warn(`Error fetching variant queries for ${masterSku}/${finishCode}:`, err)
    return []
  }
}

/**
 * Format a number for display (e.g., 2400 -> "2.4K")
 */
function formatVolume(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return String(value)
}

/**
 * Convert search queries to Evidence rows for LLM prompt
 *
 * @param queries - List of query objects
 * @param context - Either "master" (SKU-level) or "variant" (finish-specific)
 * @returns List of Evidence rows
 */
export function formatSearchQueriesForEvidence(
  queries: SearchQueryInsight[] | VariantSearchQuery[],
  context: 'master' | 'variant',
  options?: { currentTitle?: string }
): Evidence[] {
  if (!queries || queries.length === 0) {
    return []
  }

  const evidenceRows: Evidence[] = []

  if (context === 'master') {
    // Format top queries with search volume when available
    const queryParts: string[] = []
    for (const q of queries.slice(0, 10)) {
      const text = q.query_text
      if (!text) continue

      const insight = q as SearchQueryInsight
      const volume = insight.avg_monthly_searches
      if (volume && volume > 0) {
        // Format with volume: "brass towel bar (2.4K vol)"
        queryParts.push(`"${text}" (${formatVolume(volume)} vol)`)
      } else {
        // No volume data, use impressions
        const impressions = insight.total_impressions ?? 0
        queryParts.push(`"${text}" (${formatVolume(impressions)} imp)`)
      }
    }

    if (queryParts.length > 0) {
      evidenceRows.push({
        field: 'search_queries_top',
        value: queryParts.join(', '),
        source: 'search_insights',
      })
    }

    // Add missing keyword analysis if current title is available
    if (options?.currentTitle && context === 'master') {
      const titleLower = options.currentTitle.toLowerCase()
      const masterQueries = queries as SearchQueryInsight[]

      // Find queries with significant clicks where the query text is missing from title
      const missingTerms = masterQueries
        .filter(q => {
          const clicks = q.total_clicks ?? 0
          if (clicks < 5) return false // Must have meaningful clicks
          // Check if the multi-word query is missing from the title
          const words = q.query_text.toLowerCase().split(/\s+/)
          if (words.length < 2) return false // Single words are too generic
          return !titleLower.includes(q.query_text.toLowerCase())
        })
        .slice(0, 5)

      if (missingTerms.length > 0) {
        evidenceRows.push({
          field: 'high_click_queries_not_in_title',
          value: missingTerms.map(q => {
            const clicks = q.total_clicks ?? 0
            const impressions = q.total_impressions ?? 1
            const ctr = ((clicks / impressions) * 100).toFixed(1)
            return `"${q.query_text}" (${clicks} clicks, ${ctr}% CTR)`
          }).join(', '),
          source: 'keyword_gap_analysis',
        })
      }
    }

    // Extract themes from queries
    const themes = extractQueryThemes(queries as SearchQueryInsight[])
    if (themes) {
      evidenceRows.push({
        field: 'search_query_themes',
        value: themes,
        source: 'search_insights',
      })
    }
  } else if (context === 'variant') {
    // Variant-specific queries (shorter format)
    const queryParts: string[] = []
    for (const q of queries.slice(0, 5)) {
      const text = q.query_text
      if (!text) continue
      const variant = q as VariantSearchQuery
      const impressions = variant.impressions ?? 0
      queryParts.push(`"${text}" (${formatVolume(impressions)} imp)`)
    }

    if (queryParts.length > 0) {
      evidenceRows.push({
        field: 'variant_top_queries',
        value: queryParts.join(', '),
        source: 'search_insights_variant',
      })
    }
  }

  return evidenceRows
}

/**
 * Extract common themes from search queries
 *
 * Identifies patterns like:
 * - Material mentions (brass, chrome, nickel)
 * - Style mentions (antique, modern, vintage)
 * - Function mentions (towel holder, grab bar)
 */
function extractQueryThemes(queries: SearchQueryInsight[]): string {
  // Material keywords
  const materials = new Set([
    'brass', 'chrome', 'nickel', 'gold', 'bronze', 'copper', 'stainless', 'iron',
  ])
  // Style keywords
  const styles = new Set([
    'antique', 'modern', 'vintage', 'contemporary', 'traditional', 'classic', 'rustic',
  ])
  // Function/product type keywords (sorted by length for matching)
  const functions = [
    'towel bar', 'towel holder', 'towel rack', 'towel ring',
    'grab bar', 'safety bar', 'toilet paper holder', 'tissue holder',
    'robe hook', 'coat hook', 'soap dish', 'soap dispenser',
    'shelf', 'mirror', 'hardware', 'bathroom accessories',
  ].sort((a, b) => b.length - a.length) // Longer phrases first

  const foundMaterials = new Set<string>()
  const foundStyles = new Set<string>()
  const foundFunctions = new Set<string>()

  for (const q of queries) {
    const text = (q.query_text ?? '').toLowerCase()

    // Check materials
    for (const mat of materials) {
      if (text.includes(mat)) {
        foundMaterials.add(mat)
      }
    }

    // Check styles
    for (const style of styles) {
      if (text.includes(style)) {
        foundStyles.add(style)
      }
    }

    // Check functions (only match one per query)
    for (const func of functions) {
      if (text.includes(func)) {
        foundFunctions.add(func)
        break
      }
    }
  }

  const themeParts: string[] = []

  if (foundMaterials.size > 0) {
    themeParts.push(`Material: ${[...foundMaterials].slice(0, 3).sort().join('/')}`)
  }

  if (foundStyles.size > 0) {
    themeParts.push(`Style: ${[...foundStyles].slice(0, 2).sort().join('/')}`)
  }

  if (foundFunctions.size > 0) {
    themeParts.push(`Function: ${[...foundFunctions].slice(0, 2).sort().join('/')}`)
  }

  return themeParts.join(', ')
}

/**
 * Get complete search insights summary for a SKU
 *
 * Convenience function that combines queries and metrics.
 * Useful for displaying on review pages.
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU to analyze
 * @returns Summary object with top queries, themes, and totals
 */
export async function getSearchInsightsForSku(
  supabase: SupabaseClient,
  masterSku: string
): Promise<{
  topQueries: SearchQueryInsight[]
  themes: string
  totalQueries: number
  totalImpressions: number
}> {
  const queries = await getSearchQueriesForMasterSku(supabase, masterSku, 20)

  if (!queries || queries.length === 0) {
    return {
      topQueries: [],
      themes: '',
      totalQueries: 0,
      totalImpressions: 0,
    }
  }

  return {
    topQueries: queries.slice(0, 10),
    themes: extractQueryThemes(queries),
    totalQueries: queries.length,
    totalImpressions: queries.reduce((sum, q) => sum + (q.total_impressions ?? 0), 0),
  }
}
