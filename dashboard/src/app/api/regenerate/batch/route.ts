import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'

interface BatchRegenerateRequest {
  skus?: string[]
  all?: boolean
  platforms?: Platform[]
  content_types?: ContentType[]
}

interface RegenerateResult {
  sku: string
  platform: Platform
  content_type: ContentType
  success: boolean
  content?: string
  version?: number
  error?: string
}

type Platform = 'google' | 'bing' | 'shopify'
type ContentType = 'title' | 'description'

const PLATFORMS: Platform[] = ['google', 'bing', 'shopify']
const CONTENT_TYPES: ContentType[] = ['title', 'description']
const DELAY_BETWEEN_CALLS_MS = 250

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function getRegenerateEndpoint(request: NextRequest): string {
  return new URL('/api/regenerate', request.url).toString()
}

export async function POST(request: NextRequest) {
  try {
    const body: BatchRegenerateRequest = await request.json()
    const { skus, all, platforms, content_types } = body

    if (!skus && !all) {
      return NextResponse.json(
        { error: 'Must provide either "skus" array or "all: true"' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()
    let targetSkus: string[] = []

    if (all) {
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

      targetSkus = [...new Set(data?.map((record) => record.master_sku) || [])]
    } else if (skus) {
      targetSkus = skus
    }

    if (targetSkus.length === 0) {
      return NextResponse.json(
        { error: 'No SKUs to regenerate' },
        { status: 400 }
      )
    }

    const targetPlatforms = platforms || [...PLATFORMS]
    const targetContentTypes = content_types || [...CONTENT_TYPES]
    const totalOperations =
      targetSkus.length * targetPlatforms.length * targetContentTypes.length

    const regenerateEndpoint = getRegenerateEndpoint(request)

    const results: RegenerateResult[] = []
    let completed = 0
    let successful = 0
    let failed = 0

    for (const sku of targetSkus) {
      for (const platform of targetPlatforms) {
        for (const contentType of targetContentTypes) {
          try {
            const regenerateResponse = await fetch(regenerateEndpoint, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                master_sku: sku,
                content_type: contentType,
                platform,
                mode: 'simple',
              }),
            })

            const payload = await regenerateResponse
              .json()
              .catch(() => ({ error: 'Invalid regenerate response' }))

            if (!regenerateResponse.ok) {
              const errorMessage =
                typeof payload?.error === 'string'
                  ? payload.error
                  : `Regeneration failed with status ${regenerateResponse.status}`
              results.push({
                sku,
                platform,
                content_type: contentType,
                success: false,
                error: errorMessage,
              })
              failed++
            } else {
              results.push({
                sku,
                platform,
                content_type: contentType,
                success: true,
                content:
                  typeof payload?.content === 'string'
                    ? payload.content
                    : undefined,
                version:
                  typeof payload?.version === 'number'
                    ? payload.version
                    : undefined,
              })
              successful++
            }
          } catch (error) {
            results.push({
              sku,
              platform,
              content_type: contentType,
              success: false,
              error:
                error instanceof Error ? error.message : 'Unknown error',
            })
            failed++
          }

          completed++
          if (completed % 10 === 0) {
            console.log(
              `Batch regeneration progress: ${completed}/${totalOperations} (${successful} success, ${failed} failed)`
            )
          }
          await sleep(DELAY_BETWEEN_CALLS_MS)
        }
      }
    }

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

export async function GET() {
  try {
    const supabase = createAdminClient()

    const { data, error } = await supabase
      .from('generated_content')
      .select('master_sku, platform, content_type, candidate_content')
      .not('candidate_content', 'is', null)
      .order('master_sku')

    if (error) {
      return NextResponse.json({ error: 'Failed to fetch content' }, { status: 500 })
    }

    const skus = [...new Set(data?.map((record) => record.master_sku) || [])]
    const totalItems = data?.length || 0

    return NextResponse.json({
      skus,
      total_skus: skus.length,
      total_content_items: totalItems,
      estimated_time_minutes: Math.ceil((totalItems * 1.5) / 60),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
