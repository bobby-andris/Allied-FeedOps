import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { resolveCanonicalMasterSkuList } from '@/lib/master-sku'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

interface GenerateHybridRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: GenerateHybridRequest = await request.json()
    const { skus, options } = body

    if (!skus || !Array.isArray(skus) || skus.length === 0) {
      return NextResponse.json({ error: 'No SKUs provided' }, { status: 400 })
    }

    if (skus.length > 100) {
      return NextResponse.json(
        { error: 'Maximum 100 SKUs per batch' },
        { status: 400 }
      )
    }

    if (!options || (!options.titles && !options.descriptions)) {
      return NextResponse.json(
        { error: 'At least one content type must be selected' },
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

    const response = await fetch(`${PIPELINE_URL}/hybrid-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skus: canonicalSkus,
        options,
      }),
    })

    const payload = await response
      .json()
      .catch(() => ({ detail: 'Invalid pipeline response' }))

    if (!response.ok) {
      return NextResponse.json(
        { error: payload.detail || payload.error || 'Hybrid generation failed' },
        { status: response.status }
      )
    }

    return NextResponse.json(payload)
  } catch (error) {
    console.error('Hybrid generation API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
