import { NextRequest, NextResponse } from 'next/server'
import { ensureAllData } from '@/lib/data-collection/ensure-data'
import { createAdminClient } from '@/lib/supabase/admin'
import { resolveCanonicalMasterSkuList } from '@/lib/master-sku'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

interface GenerateRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    images: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
    num_candidates?: number
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: GenerateRequest = await request.json()
    const { skus, options } = body

    // Validate input
    if (!skus || !Array.isArray(skus) || skus.length === 0) {
      return NextResponse.json(
        { error: 'No SKUs provided' },
        { status: 400 }
      )
    }

    if (skus.length > 100) {
      return NextResponse.json(
        { error: 'Maximum 100 SKUs per batch' },
        { status: 400 }
      )
    }

    if (!options || (!options.titles && !options.descriptions && !options.images)) {
      return NextResponse.json(
        { error: 'At least one content type (titles, descriptions, or images) must be selected' },
        { status: 400 }
      )
    }

    if (!options.platforms || options.platforms.length === 0) {
      return NextResponse.json(
        { error: 'At least one platform must be selected' },
        { status: 400 }
      )
    }

    if (!PIPELINE_URL) {
      return NextResponse.json(
        { error: 'Content generation pipeline is not configured (FEEDOPS_PIPELINE_URL not set)' },
        { status: 503 }
      )
    }

    const adminClient = createAdminClient()
    const canonicalSkus = [...new Set(await resolveCanonicalMasterSkuList(adminClient, skus))]

    // Ensure data collection before batch generation (non-blocking, best-effort)
    ensureAllData(canonicalSkus, adminClient)
      .then((result) => {
        if (result.success) {
          console.log(`Data collection triggered for ${canonicalSkus.length} SKUs before batch generation`, result.details)
        } else {
          console.warn('Data collection failed (non-blocking):', result.error)
        }
      })
      .catch((error) => {
        console.warn('Data collection background task failed:', error)
      })

    // Call Cloud Run's batch-optimize endpoint
    // Cloud Run creates job records and processes SKUs in the background
    const response = await fetch(`${PIPELINE_URL}/batch-optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skus: canonicalSkus,
        num_candidates: options.num_candidates ?? 1,
        dry_run: false,
        options: {
          titles: options.titles,
          descriptions: options.descriptions,
          platforms: options.platforms,
        },
      }),
    })

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}))
      console.error('Cloud Run batch-optimize failed:', response.status, errorBody)
      return NextResponse.json(
        { error: errorBody.detail || 'Failed to start content generation pipeline' },
        { status: response.status }
      )
    }

    const result = await response.json()

    return NextResponse.json({
      success: true,
      job_id: result.job_id,
      status: result.status,
      total_skus: result.total_skus,
    })
  } catch (error) {
    console.error('Generation API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
