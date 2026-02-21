import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

type BottleneckClassification =
  | 'coverage_gap'
  | 'code_path_gap'
  | 'propagation_failure'
  | 'query_relevance'
  | 'auction_bid'

const ALL_CATEGORIES: BottleneckClassification[] = [
  'coverage_gap',
  'code_path_gap',
  'propagation_failure',
  'query_relevance',
  'auction_bid',
]

interface BottleneckRow {
  id: number
  master_sku: string
  classification: BottleneckClassification
  confidence: number
  evidence: Record<string, unknown>
  override_by: string | null
  override_note: string | null
  is_override: boolean
  classified_at: string
  publish_event_id: number | null
}

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const masterSku = searchParams.get('master_sku')
    const classificationFilter = searchParams.get('classification') as BottleneckClassification | null
    const limit = Math.min(parseInt(searchParams.get('limit') ?? '100', 10), 1000)

    // Validate classification filter if provided
    if (classificationFilter && !ALL_CATEGORIES.includes(classificationFilter)) {
      return NextResponse.json(
        {
          error: `Invalid classification filter. Must be one of: ${ALL_CATEGORIES.join(', ')}`,
        },
        { status: 400 }
      )
    }

    // Build filtered query for classifications
    let query = supabase
      .from('sku_bottleneck_classifications')
      .select(
        'id, master_sku, classification, confidence, evidence, override_by, override_note, is_override, classified_at, publish_event_id'
      )
      .order('classified_at', { ascending: false })
      .limit(limit)

    if (masterSku) {
      query = query.eq('master_sku', masterSku)
    }

    if (classificationFilter) {
      query = query.eq('classification', classificationFilter)
    }

    const { data: classificationRows, error: classificationError } = await query

    if (classificationError) {
      return NextResponse.json(
        { error: `Failed to fetch bottleneck classifications: ${classificationError.message}` },
        { status: 500 }
      )
    }

    // For each SKU, prefer override over auto-classification
    // Group by master_sku, pick the override if exists, otherwise latest auto
    const bySkuMap = new Map<string, BottleneckRow>()

    for (const row of classificationRows ?? []) {
      const existing = bySkuMap.get(row.master_sku as string)

      // Always prefer override rows over auto-classification rows
      if (!existing) {
        bySkuMap.set(row.master_sku as string, row as BottleneckRow)
      } else if (!existing.is_override && row.is_override) {
        // Upgrade to override
        bySkuMap.set(row.master_sku as string, row as BottleneckRow)
      }
      // If both are overrides or both are auto, keep the most recent (already sorted by classified_at DESC)
    }

    const classifications = Array.from(bySkuMap.values())

    // Compute category summary counts — always over ALL classifications regardless of filters
    // Fetch full summary counts separately
    const { data: allRows, error: allRowsError } = await supabase
      .from('sku_bottleneck_classifications')
      .select('master_sku, classification, is_override, classified_at')
      .order('classified_at', { ascending: false })

    const summaryCounts: Record<BottleneckClassification, number> = {
      coverage_gap: 0,
      code_path_gap: 0,
      propagation_failure: 0,
      query_relevance: 0,
      auction_bid: 0,
    }

    if (!allRowsError && allRows) {
      // Deduplicate: prefer override per SKU for summary
      const summaryMap = new Map<string, BottleneckClassification>()

      for (const row of allRows) {
        const existing = summaryMap.get(row.master_sku as string)
        if (!existing) {
          summaryMap.set(row.master_sku as string, row.classification as BottleneckClassification)
        }
        // Keep first (most recent due to ORDER BY classified_at DESC)
        // Override rows come in based on classified_at, we also need to prefer overrides
      }

      // Re-pass to prefer overrides: rebuild using is_override awareness
      const summaryMapWithOverride = new Map<
        string,
        { classification: BottleneckClassification; is_override: boolean }
      >()
      for (const row of allRows) {
        const existing = summaryMapWithOverride.get(row.master_sku as string)
        if (!existing) {
          summaryMapWithOverride.set(row.master_sku as string, {
            classification: row.classification as BottleneckClassification,
            is_override: !!row.is_override,
          })
        } else if (!existing.is_override && row.is_override) {
          summaryMapWithOverride.set(row.master_sku as string, {
            classification: row.classification as BottleneckClassification,
            is_override: true,
          })
        }
      }

      for (const entry of summaryMapWithOverride.values()) {
        if (entry.classification in summaryCounts) {
          summaryCounts[entry.classification]++
        }
      }
    }

    return NextResponse.json({
      classifications,
      total_count: classifications.length,
      by_category: summaryCounts,
    })
  } catch (error) {
    console.error('[bottleneck/status] Unexpected error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
