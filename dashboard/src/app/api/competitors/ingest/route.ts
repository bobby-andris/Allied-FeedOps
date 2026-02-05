import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'
import {
  extractPatterns,
  normalizeApifyData,
  extractDomain,
} from '@/lib/competitors/pattern-extraction'

/**
 * POST /api/competitors/ingest
 * Ingest scraped data from Apify and extract patterns
 *
 * Body:
 * - jobId: The scrape job ID
 * - listings: Array of raw listing data from Apify
 */

interface IngestRequest {
  jobId: string
  listings: Record<string, unknown>[]
}

export async function POST(request: NextRequest) {
  try {
    const body: IngestRequest = await request.json()
    const { jobId, listings } = body

    if (!jobId || !listings || !Array.isArray(listings)) {
      return NextResponse.json(
        { error: 'Missing required fields: jobId, listings (array)' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()

    // 1. Get the job to know category and source
    const { data: job, error: jobError } = await supabase
      .from('competitor_scrape_jobs')
      .select('*')
      .eq('id', jobId)
      .single()

    if (jobError || !job) {
      return NextResponse.json(
        { error: 'Job not found', details: jobError?.message },
        { status: 404 }
      )
    }

    // 2. Normalize the raw Apify data
    const normalizedListings = normalizeApifyData(job.source, listings)

    // For Google SERP, we need to flatten the raw organic results to match normalized data
    let flattenedRawListings: Record<string, unknown>[] = listings
    if (job.source === 'google') {
      flattenedRawListings = []
      for (const page of listings) {
        const organicResults = page.organicResults as Array<Record<string, unknown>> | undefined
        if (organicResults && Array.isArray(organicResults)) {
          flattenedRawListings.push(...organicResults)
        }
      }
    }

    // 3. Prepare listings for insert/upsert
    const listingsToInsert = normalizedListings.map((listing, index) => {
      const rawListing = flattenedRawListings[index]
      // For SERP results, extract domain from URL in raw data
      let domain = listing.domain
      if (job.job_type === 'serp' && rawListing) {
        const rawUrl = rawListing.url || rawListing.link
        if (rawUrl && typeof rawUrl === 'string') {
          domain = extractDomain(rawUrl)
        }
      }

      return {
        source: job.source,
        source_type: job.job_type,
        source_url: (rawListing?.url || rawListing?.link || null) as string | null,
        domain,
        product_category: job.category,
        title: listing.title,
        description: listing.description,
        price: parsePrice(rawListing?.price),
        rating: parseFloat(String(rawListing?.rating || '0')) || null,
        review_count: parseInt(String(rawListing?.reviewsCount || rawListing?.reviewCount || rawListing?.reviews || '0'), 10) || null,
        brand: listing.brand || extractBrandFromTitle(listing.title),
        position: listing.position,
        image_url: (rawListing?.image || rawListing?.imageUrl || rawListing?.thumbnail || null) as string | null,
        scrape_job_id: jobId,
        keywords_extracted: extractKeywordsFromText(listing.title + ' ' + (listing.description || '')),
      }
    })

    // 4. Upsert listings (update on conflict)
    let insertedCount = 0
    for (const listing of listingsToInsert) {
      if (!listing.title || listing.title.length < 3) continue

      const { error: insertError } = await supabase
        .from('competitor_listings')
        .upsert(listing, {
          onConflict: 'source,source_url',
          ignoreDuplicates: false,
        })

      if (insertError) {
        console.error('Error inserting listing:', insertError, listing.title?.slice(0, 50))
      } else {
        insertedCount++
      }
    }

    // 5. Extract patterns from all listings for this category
    // Fetch all recent listings for the category to re-extract patterns
    const { data: allListings } = await supabase
      .from('competitor_listings')
      .select('title, description, source, position, domain, brand')
      .eq('product_category', job.category)
      .order('scraped_at', { ascending: false })
      .limit(200)

    const patterns = extractPatterns(
      (allListings || []).map(l => ({
        title: l.title,
        description: l.description,
        source: l.source,
        position: l.position,
        domain: l.domain,
        brand: l.brand,
      })),
      job.category
    )

    // 6. Upsert patterns
    let patternsUpserted = 0
    for (const pattern of patterns) {
      const { error: patternError } = await supabase
        .from('competitor_patterns')
        .upsert(
          {
            category: pattern.category,
            pattern_type: pattern.pattern_type,
            pattern_value: pattern.pattern_value,
            frequency: pattern.frequency,
            avg_position: pattern.avg_position,
            sources: pattern.sources,
            example_titles: pattern.example_titles,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'category,pattern_type,pattern_value' }
        )

      if (patternError) {
        console.error('Error upserting pattern:', patternError)
      } else {
        patternsUpserted++
      }
    }

    // 7. Update job status
    const { error: updateError } = await supabase
      .from('competitor_scrape_jobs')
      .update({
        status: 'completed',
        listings_count: insertedCount,
        completed_at: new Date().toISOString(),
      })
      .eq('id', jobId)

    if (updateError) {
      console.error('Error updating job status:', updateError)
    }

    return NextResponse.json({
      success: true,
      listingsIngested: insertedCount,
      patternsExtracted: patternsUpserted,
      jobId,
    })
  } catch (error) {
    console.error('Ingest API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * Parse price from various formats
 */
function parsePrice(price: unknown): number | null {
  if (typeof price === 'number') return price
  if (typeof price === 'string') {
    const cleaned = price.replace(/[^0-9.]/g, '')
    const parsed = parseFloat(cleaned)
    return isNaN(parsed) ? null : parsed
  }
  return null
}

/**
 * Extract brand from title (common pattern: "Brand - Product Title")
 */
function extractBrandFromTitle(title: string): string | null {
  // Check for "Brand - " or "Brand | " pattern
  const dashMatch = title.match(/^([^-|]+)\s*[-|]\s*/i)
  if (dashMatch && dashMatch[1].length < 30) {
    return dashMatch[1].trim()
  }
  return null
}

/**
 * Simple keyword extraction for storage
 */
function extractKeywordsFromText(text: string): string[] {
  const stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'by', 'from', 'this', 'that', 'is', 'are', 'was', 'be', 'been',
  ])

  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter(word => word.length > 2 && !stopWords.has(word))
    .slice(0, 20)
}
