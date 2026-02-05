import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'
import { ApifyClient } from 'apify-client'
import {
  extractPatterns,
  normalizeApifyData,
  extractDomain,
} from '@/lib/competitors/pattern-extraction'

/**
 * GET /api/competitors/scrape/[jobId]
 * Check the status of a scrape job and auto-ingest results when complete
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params

    if (!jobId) {
      return NextResponse.json({ error: 'Job ID required' }, { status: 400 })
    }

    const supabase = createAdminClient()

    // Get job from database
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

    // If already completed or failed, just return status
    if (job.status === 'completed' || job.status === 'failed') {
      return NextResponse.json({
        job,
        status: job.status,
        message: job.status === 'completed'
          ? `Job completed with ${job.listings_count} listings`
          : `Job failed: ${job.error_message}`,
      })
    }

    // Check Apify run status
    const apifyToken = process.env.APIFY_API_TOKEN
    if (!apifyToken || !job.apify_run_id) {
      return NextResponse.json({
        job,
        status: job.status,
        message: 'Waiting for Apify run to start...',
      })
    }

    const client = new ApifyClient({ token: apifyToken })

    try {
      const run = await client.run(job.apify_run_id).get()

      if (!run) {
        return NextResponse.json({
          job,
          status: 'running',
          message: 'Apify run not found, may still be starting...',
        })
      }

      // Map Apify status to our status
      const apifyStatus = run.status

      if (apifyStatus === 'SUCCEEDED') {
        // Fetch results and ingest
        const dataset = client.dataset(run.defaultDatasetId)
        const { items } = await dataset.listItems()

        if (items && items.length > 0) {
          // Ingest the results
          const result = await ingestResults(supabase, job, items as Record<string, unknown>[])

          return NextResponse.json({
            job: { ...job, status: 'completed', listings_count: result.listingsIngested },
            status: 'completed',
            message: `Completed! Ingested ${result.listingsIngested} listings and extracted ${result.patternsExtracted} patterns.`,
            result,
          })
        } else {
          // Mark as completed but with 0 results
          await supabase
            .from('competitor_scrape_jobs')
            .update({
              status: 'completed',
              listings_count: 0,
              completed_at: new Date().toISOString(),
            })
            .eq('id', jobId)

          return NextResponse.json({
            job: { ...job, status: 'completed', listings_count: 0 },
            status: 'completed',
            message: 'Completed but no results found.',
          })
        }
      } else if (apifyStatus === 'FAILED' || apifyStatus === 'ABORTED' || apifyStatus === 'TIMED-OUT') {
        // Mark job as failed
        await supabase
          .from('competitor_scrape_jobs')
          .update({
            status: 'failed',
            error_message: `Apify run ${apifyStatus.toLowerCase()}`,
            completed_at: new Date().toISOString(),
          })
          .eq('id', jobId)

        return NextResponse.json({
          job: { ...job, status: 'failed' },
          status: 'failed',
          message: `Apify run ${apifyStatus.toLowerCase()}`,
        })
      } else {
        // Still running
        return NextResponse.json({
          job,
          status: 'running',
          apifyStatus,
          message: `Apify run status: ${apifyStatus}`,
        })
      }
    } catch (apifyError) {
      console.error('Error checking Apify status:', apifyError)
      return NextResponse.json({
        job,
        status: job.status,
        message: 'Error checking Apify status',
        error: apifyError instanceof Error ? apifyError.message : 'Unknown error',
      })
    }
  } catch (error) {
    console.error('Job status API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * PATCH /api/competitors/scrape/[jobId]
 * Update the status of a scrape job
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const body = await request.json()
    const supabase = createAdminClient()

    // Build update object
    const update: Record<string, unknown> = {}

    if (body.status) {
      update.status = body.status
      if (body.status === 'running' && !body.started_at) {
        update.started_at = new Date().toISOString()
      }
      if (['completed', 'failed'].includes(body.status)) {
        update.completed_at = new Date().toISOString()
      }
    }

    if (body.apify_run_id !== undefined) {
      update.apify_run_id = body.apify_run_id
    }

    if (body.apify_dataset_id !== undefined) {
      update.apify_dataset_id = body.apify_dataset_id
    }

    if (body.listings_count !== undefined) {
      update.listings_count = body.listings_count
    }

    if (body.error_message !== undefined) {
      update.error_message = body.error_message
    }

    const { data: job, error } = await supabase
      .from('competitor_scrape_jobs')
      .update(update)
      .eq('id', jobId)
      .select()
      .single()

    if (error) {
      console.error('Error updating job:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ job })
  } catch (error) {
    console.error('Job update API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * Ingest results from Apify into the database
 */
async function ingestResults(
  supabase: ReturnType<typeof createAdminClient>,
  job: {
    id: string
    source: string
    job_type: string
    category: string
  },
  listings: Record<string, unknown>[]
) {
  // Normalize the raw Apify data
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

  // Prepare listings for insert/upsert
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
      scrape_job_id: job.id,
      keywords_extracted: extractKeywordsFromText(listing.title + ' ' + (listing.description || '')),
    }
  })

  // Upsert listings
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

  // Extract patterns from all listings for this category
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

  // Upsert patterns
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

  // Update job status
  await supabase
    .from('competitor_scrape_jobs')
    .update({
      status: 'completed',
      listings_count: insertedCount,
      completed_at: new Date().toISOString(),
    })
    .eq('id', job.id)

  return {
    listingsIngested: insertedCount,
    patternsExtracted: patternsUpserted,
  }
}

function parsePrice(price: unknown): number | null {
  if (typeof price === 'number') return price
  if (typeof price === 'string') {
    const cleaned = price.replace(/[^0-9.]/g, '')
    const parsed = parseFloat(cleaned)
    return isNaN(parsed) ? null : parsed
  }
  return null
}

function extractBrandFromTitle(title: string): string | null {
  const dashMatch = title.match(/^([^-|]+)\s*[-|]\s*/i)
  if (dashMatch && dashMatch[1].length < 30) {
    return dashMatch[1].trim()
  }
  return null
}

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
