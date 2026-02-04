import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'

/**
 * POST /api/competitors/scrape
 * Create a scrape job and return Apify actor configuration
 *
 * Body:
 * - category: Product category
 * - jobType: 'serp' | 'marketplace'
 * - source: 'google' | 'amazon' | 'wayfair' | 'homedepot'
 * - searchQuery?: For SERP jobs, the search query
 */

interface ScrapeRequest {
  category: string
  jobType: 'serp' | 'marketplace'
  source: 'google' | 'amazon' | 'wayfair' | 'homedepot'
  searchQuery?: string
}

// SERP queries for each category
const SERP_QUERIES: Record<string, string[]> = {
  'towel bars': [
    'brass towel bar bathroom',
    'brass towel bar 24 inch',
    'bathroom towel bar gold',
  ],
  'grab bars': [
    'brass grab bar bathroom',
    'decorative grab bar',
    'grab bar shower brass',
  ],
  'toilet paper holders': [
    'brass toilet paper holder',
    'recessed toilet paper holder brass',
    'freestanding toilet paper holder',
  ],
  'robe hooks': [
    'brass robe hook bathroom',
    'double robe hook brass',
  ],
  'soap dispensers': [
    'brass soap dispenser bathroom',
    'wall mount soap dispenser brass',
  ],
  'glass shelves': [
    'brass glass shelf bathroom',
    'bathroom glass shelf gold',
  ],
  'mirrors': [
    'brass bathroom mirror',
    'vanity mirror brass frame',
  ],
}

// Category URLs for marketplace scrapers
const CATEGORY_URLS: Record<string, Record<string, string>> = {
  wayfair: {
    'towel bars': 'https://www.wayfair.com/home-improvement/sb0/towel-bars-c215273.html',
    'grab bars': 'https://www.wayfair.com/home-improvement/sb0/grab-bars-c215269.html',
    'toilet paper holders': 'https://www.wayfair.com/home-improvement/sb0/toilet-paper-holders-c215291.html',
    'robe hooks': 'https://www.wayfair.com/home-improvement/sb0/robe-hooks-c215283.html',
    'soap dispensers': 'https://www.wayfair.com/home-improvement/sb0/soap-dispensers-c215289.html',
  },
  homedepot: {
    'towel bars': 'https://www.homedepot.com/b/Bath-Bathroom-Hardware-Towel-Bars/N-5yc1vZcb3q',
    'grab bars': 'https://www.homedepot.com/b/Bath-Bathroom-Accessories-Grab-Bars/N-5yc1vZcb2y',
    'toilet paper holders': 'https://www.homedepot.com/b/Bath-Bathroom-Hardware-Toilet-Paper-Holders/N-5yc1vZcb3n',
    'robe hooks': 'https://www.homedepot.com/b/Bath-Bathroom-Hardware-Robe-Hooks/N-5yc1vZcb3p',
  },
}

// Apify actor configurations
function getApifyConfig(
  source: string,
  jobType: string,
  category: string,
  searchQuery?: string
) {
  switch (source) {
    case 'google':
      // Google SERP scraper
      const queries = searchQuery
        ? [searchQuery]
        : SERP_QUERIES[category] || [`brass ${category} bathroom`]
      return {
        actor: 'apify/google-search-scraper',
        input: {
          queries: queries.join('\n'),
          maxPagesPerQuery: 2,
          resultsPerPage: 20,
          countryCode: 'us',
          languageCode: 'en',
          mobileResults: false,
          includeUnfilteredResults: false,
        },
      }

    case 'amazon':
      // Amazon search scraper
      const amazonKeyword = searchQuery || `brass ${category}`
      return {
        actor: 'axesso_data/amazon-search-scraper',
        input: {
          input: [
            {
              keyword: amazonKeyword,
              domainCode: 'com',
              sortBy: 'relevanceblender',
              maxPages: 1,
              category: 'aps',
            },
          ],
        },
      }

    case 'wayfair':
      // Wayfair scraper
      const wayfairUrl = CATEGORY_URLS.wayfair[category]
      if (!wayfairUrl) {
        return null
      }
      return {
        actor: '123webdata/wayfair-scraper',
        input: {
          categoryUrls: [wayfairUrl],
          maxResultsPerScrape: 20,
          usePagination: false,
        },
      }

    case 'homedepot':
      // Home Depot scraper
      const hdUrl = CATEGORY_URLS.homedepot[category]
      if (!hdUrl) {
        return null
      }
      return {
        actor: 'rigelbytes/homedepot-scraper',
        input: {
          url: hdUrl,
          deliveryZip: '23060', // Richmond VA area
          maxProducts: 20,
          proxyConfiguration: {
            useApifyProxy: true,
            apifyProxyGroups: ['RESIDENTIAL'],
            apifyProxyCountry: 'US',
          },
        },
      }

    default:
      return null
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: ScrapeRequest = await request.json()
    const { category, jobType, source, searchQuery } = body

    // Validate required fields
    if (!category || !jobType || !source) {
      return NextResponse.json(
        { error: 'Missing required fields: category, jobType, source' },
        { status: 400 }
      )
    }

    // Get Apify configuration
    const apifyConfig = getApifyConfig(source, jobType, category, searchQuery)
    if (!apifyConfig) {
      return NextResponse.json(
        { error: `No configuration available for ${source} + ${category}` },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()

    // Create job record
    const { data: job, error: jobError } = await supabase
      .from('competitor_scrape_jobs')
      .insert({
        category,
        job_type: jobType,
        source,
        search_query: searchQuery || (jobType === 'serp' ? SERP_QUERIES[category]?.join(', ') : null),
        status: 'pending',
      })
      .select()
      .single()

    if (jobError) {
      console.error('Failed to create scrape job:', jobError)
      return NextResponse.json(
        { error: 'Failed to create scrape job', details: jobError.message },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      job,
      apifyConfig,
      message: `Created ${jobType} scrape job for "${category}" from ${source}`,
    })
  } catch (error) {
    console.error('Scrape API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * GET /api/competitors/scrape
 * Get available scrape configurations for a category
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const category = searchParams.get('category') || 'towel bars'

  const serpQueries = SERP_QUERIES[category] || [`brass ${category} bathroom`]
  const wayfairUrl = CATEGORY_URLS.wayfair[category]
  const homedepotUrl = CATEGORY_URLS.homedepot[category]

  return NextResponse.json({
    category,
    available: {
      serp: {
        google: {
          available: true,
          queries: serpQueries,
        },
      },
      marketplace: {
        amazon: {
          available: true,
          keyword: `brass ${category}`,
        },
        wayfair: {
          available: !!wayfairUrl,
          url: wayfairUrl || null,
        },
        homedepot: {
          available: !!homedepotUrl,
          url: homedepotUrl || null,
        },
      },
    },
  })
}
