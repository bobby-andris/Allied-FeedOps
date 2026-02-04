import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

/**
 * GET /api/competitors
 * Fetch competitor listings and patterns for a category
 *
 * Query params:
 * - category: Product category (e.g., 'towel bars')
 * - sourceType: 'serp' | 'marketplace' | undefined (all)
 * - source: 'google' | 'amazon' | 'wayfair' | 'homedepot' | undefined (all)
 * - sku: Optional SKU to fetch Allied Brass content for comparison
 * - limit: Max listings to return (default 50)
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const category = searchParams.get('category') || 'towel bars'
    const sourceType = searchParams.get('sourceType') as 'serp' | 'marketplace' | null
    const source = searchParams.get('source')
    const sku = searchParams.get('sku')
    const limit = parseInt(searchParams.get('limit') || '50', 10)

    const supabase = await createClient()

    // 1. Fetch competitor listings
    let listingsQuery = supabase
      .from('competitor_listings')
      .select('*')
      .eq('product_category', category)
      .order('position', { ascending: true, nullsFirst: false })
      .limit(limit)

    if (sourceType) {
      listingsQuery = listingsQuery.eq('source_type', sourceType)
    }
    if (source) {
      listingsQuery = listingsQuery.eq('source', source)
    }

    const { data: listings, error: listingsError } = await listingsQuery

    if (listingsError) {
      console.error('Error fetching competitor listings:', listingsError)
      return NextResponse.json({ error: listingsError.message }, { status: 500 })
    }

    // 2. Fetch patterns for category
    const { data: patterns, error: patternsError } = await supabase
      .from('competitor_patterns')
      .select('*')
      .eq('category', category)
      .order('frequency', { ascending: false })
      .limit(50)

    if (patternsError) {
      console.error('Error fetching competitor patterns:', patternsError)
      return NextResponse.json({ error: patternsError.message }, { status: 500 })
    }

    // 3. If SKU provided, fetch Allied Brass content for comparison
    let ourContent = null
    if (sku) {
      const { data: content, error: contentError } = await supabase
        .from('generated_content')
        .select('*')
        .eq('master_sku', sku)
        .eq('is_current', true)

      if (!contentError && content) {
        const googleTitle = content.find(
          c => c.content_type === 'title' && c.platform === 'google'
        )
        const googleDesc = content.find(
          c => c.content_type === 'description' && c.platform === 'google'
        )

        ourContent = {
          sku,
          title: googleTitle?.candidate_content || null,
          description: googleDesc?.candidate_content || null,
        }
      }
    }

    // 4. Get recent scrape jobs for this category
    const { data: recentJobs, error: jobsError } = await supabase
      .from('competitor_scrape_jobs')
      .select('*')
      .eq('category', category)
      .order('created_at', { ascending: false })
      .limit(10)

    if (jobsError) {
      console.error('Error fetching scrape jobs:', jobsError)
    }

    // 5. Aggregate domain stats for SERP data
    const domainStats: Record<string, { count: number; avgPosition: number }> = {}
    const serpListings = (listings || []).filter(l => l.source_type === 'serp')
    for (const listing of serpListings) {
      if (listing.domain) {
        if (!domainStats[listing.domain]) {
          domainStats[listing.domain] = { count: 0, avgPosition: 0 }
        }
        const stats = domainStats[listing.domain]
        const newCount = stats.count + 1
        stats.avgPosition =
          (stats.avgPosition * stats.count + (listing.position || 100)) / newCount
        stats.count = newCount
      }
    }

    // Sort domains by count
    const sortedDomains = Object.entries(domainStats)
      .sort((a, b) => b[1].count - a[1].count)
      .map(([domain, stats]) => ({
        domain,
        count: stats.count,
        avgPosition: Math.round(stats.avgPosition * 10) / 10,
      }))

    return NextResponse.json({
      listings: listings || [],
      patterns: patterns || [],
      ourContent,
      recentJobs: recentJobs || [],
      domainStats: sortedDomains,
      lastScraped: listings?.[0]?.scraped_at || null,
      totalListings: listings?.length || 0,
    })
  } catch (error) {
    console.error('Competitors API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
