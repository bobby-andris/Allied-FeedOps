import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'

/**
 * Batch Regeneration API
 *
 * Triggers regeneration for multiple SKUs across all platforms and content types.
 * This is a long-running operation that processes SKUs sequentially to avoid
 * overwhelming the OpenAI API.
 *
 * POST /api/regenerate/batch
 * Body: { skus?: string[], all?: boolean }
 *
 * If `all: true`, regenerates all SKUs with existing content.
 * If `skus` array provided, regenerates only those SKUs.
 */

interface BatchRegenerateRequest {
  skus?: string[]
  all?: boolean
  platforms?: ('google' | 'bing' | 'shopify')[]
  content_types?: ('title' | 'description')[]
}

interface RegenerateResult {
  sku: string
  platform: string
  content_type: string
  success: boolean
  error?: string
}

const PLATFORMS = ['google', 'bing', 'shopify'] as const
const CONTENT_TYPES = ['title', 'description'] as const

// Rate limiting: wait between API calls to avoid overwhelming OpenAI
const DELAY_BETWEEN_CALLS_MS = 1000

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function regenerateContent(
  baseUrl: string,
  sku: string,
  platform: 'google' | 'bing' | 'shopify',
  contentType: 'title' | 'description'
): Promise<RegenerateResult> {
  try {
    const response = await fetch(`${baseUrl}/api/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        master_sku: sku,
        platform,
        content_type: contentType,
        mode: 'simple',
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        sku,
        platform,
        content_type: contentType,
        success: false,
        error: errorData.error || `HTTP ${response.status}`,
      }
    }

    return {
      sku,
      platform,
      content_type: contentType,
      success: true,
    }
  } catch (error) {
    return {
      sku,
      platform,
      content_type: contentType,
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: BatchRegenerateRequest = await request.json()
    const { skus, all, platforms, content_types } = body

    // Validate request
    if (!skus && !all) {
      return NextResponse.json(
        { error: 'Must provide either "skus" array or "all: true"' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()
    let targetSkus: string[] = []

    if (all) {
      // Get all SKUs with existing content
      const { data, error } = await supabase
        .from('generated_content')
        .select('master_sku')
        .not('candidate_content', 'is', null)

      if (error) {
        return NextResponse.json(
          { error: 'Failed to fetch SKUs from database' },
          { status: 500 }
        )
      }

      targetSkus = [...new Set(data?.map(d => d.master_sku) || [])]
    } else if (skus) {
      targetSkus = skus
    }

    if (targetSkus.length === 0) {
      return NextResponse.json(
        { error: 'No SKUs to regenerate' },
        { status: 400 }
      )
    }

    // Determine which platforms and content types to regenerate
    const targetPlatforms = platforms || [...PLATFORMS]
    const targetContentTypes = content_types || [...CONTENT_TYPES]

    // Calculate total operations
    const totalOperations = targetSkus.length * targetPlatforms.length * targetContentTypes.length

    // Get base URL for internal API calls
    const baseUrl = request.nextUrl.origin

    console.log(`Starting batch regeneration: ${targetSkus.length} SKUs, ${totalOperations} total operations`)

    // Process all SKUs
    const results: RegenerateResult[] = []
    let completed = 0
    let successful = 0
    let failed = 0

    for (const sku of targetSkus) {
      for (const platform of targetPlatforms) {
        for (const contentType of targetContentTypes) {
          const result = await regenerateContent(baseUrl, sku, platform, contentType)
          results.push(result)

          completed++
          if (result.success) {
            successful++
          } else {
            failed++
            console.error(`Failed: ${sku}/${platform}/${contentType}: ${result.error}`)
          }

          // Log progress every 10 operations
          if (completed % 10 === 0) {
            console.log(`Batch regeneration progress: ${completed}/${totalOperations} (${successful} success, ${failed} failed)`)
          }

          // Rate limiting
          await sleep(DELAY_BETWEEN_CALLS_MS)
        }
      }
    }

    console.log(`Batch regeneration complete: ${successful}/${totalOperations} successful`)

    return NextResponse.json({
      success: true,
      summary: {
        total_skus: targetSkus.length,
        total_operations: totalOperations,
        successful,
        failed,
      },
      results,
    })
  } catch (error) {
    console.error('Batch regeneration error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

// GET endpoint to check status/list SKUs that need regeneration
export async function GET() {
  try {
    const supabase = createAdminClient()

    const { data, error } = await supabase
      .from('generated_content')
      .select('master_sku, platform, content_type, candidate_content')
      .not('candidate_content', 'is', null)
      .order('master_sku')

    if (error) {
      return NextResponse.json(
        { error: 'Failed to fetch content' },
        { status: 500 }
      )
    }

    const skus = [...new Set(data?.map(d => d.master_sku) || [])]
    const totalItems = data?.length || 0

    return NextResponse.json({
      skus,
      total_skus: skus.length,
      total_content_items: totalItems,
      estimated_time_minutes: Math.ceil((totalItems * 2) / 60), // ~2 seconds per item with delays
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
