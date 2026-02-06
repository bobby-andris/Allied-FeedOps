import { NextRequest, NextResponse } from 'next/server'

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

    // Call Cloud Run's batch-optimize endpoint
    // Cloud Run creates job records and processes SKUs in the background
    const response = await fetch(`${PIPELINE_URL}/batch-optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skus,
        num_candidates: options.num_candidates ?? 1,
        dry_run: false,
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
