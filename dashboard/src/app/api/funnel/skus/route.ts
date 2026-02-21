import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

type FunnelStage = 'total_catalog' | 'has_generated' | 'approved' | 'published'

const VALID_STAGES: FunnelStage[] = ['total_catalog', 'has_generated', 'approved', 'published']

interface SkuRow {
  master_sku: string
  detail?: string
}

interface FunnelSkusResponse {
  stage: string
  skus: SkuRow[]
  total: number
  limit: number
  offset: number
}

/**
 * GET /api/funnel/skus?stage=total_catalog|has_generated|approved|published&limit=100&offset=0
 *
 * Returns paginated list of SKUs at the specified funnel stage.
 * Used by CoverageFunnel component when user clicks a stage to expand the SKU list.
 *
 * Stage queries:
 *   - total_catalog:  DISTINCT master_sku FROM variant_index
 *   - has_generated:  DISTINCT master_sku FROM generated_content
 *   - approved:       master_sku FROM sku_approvals WHERE approval_status = 'approved'
 *   - published:      DISTINCT master_sku FROM publish_events WHERE status='success' AND action='publish'
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl
  const stage = searchParams.get('stage') as FunnelStage | null
  const limit = Math.min(parseInt(searchParams.get('limit') || '100', 10), 500)
  const offset = parseInt(searchParams.get('offset') || '0', 10)

  // Validate stage param
  if (!stage || !VALID_STAGES.includes(stage)) {
    return NextResponse.json(
      {
        error: `Invalid stage. Must be one of: ${VALID_STAGES.join(', ')}`,
      },
      { status: 400 }
    )
  }

  // Validate pagination params
  if (isNaN(limit) || limit < 1) {
    return NextResponse.json({ error: 'Invalid limit parameter' }, { status: 400 })
  }
  if (isNaN(offset) || offset < 0) {
    return NextResponse.json({ error: 'Invalid offset parameter' }, { status: 400 })
  }

  try {
    const supabase = await createClient()
    let skus: SkuRow[] = []
    let total = 0

    if (stage === 'total_catalog') {
      // All distinct master_skus in variant_index, paginated alphabetically
      // Fetch a large batch to deduplicate (variant_index has many rows per master_sku)
      // For offset pagination with DISTINCT, we fetch all distinct values then slice
      const { data } = await supabase
        .from('variant_index')
        .select('master_sku')
        .order('master_sku', { ascending: true })
        .limit(100000)

      const distinctSkus = [...new Set((data || []).map((r) => r.master_sku))].sort()
      total = distinctSkus.length
      skus = distinctSkus.slice(offset, offset + limit).map((sku) => ({ master_sku: sku }))
    } else if (stage === 'has_generated') {
      // Distinct master_skus with any generated content
      const { data } = await supabase
        .from('generated_content')
        .select('master_sku')
        .order('master_sku', { ascending: true })
        .limit(10000)

      const distinctSkus = [...new Set((data || []).map((r) => r.master_sku))].sort()
      total = distinctSkus.length
      skus = distinctSkus.slice(offset, offset + limit).map((sku) => ({ master_sku: sku }))
    } else if (stage === 'approved') {
      // Approved SKUs with their approval date as detail
      const { data, count } = await supabase
        .from('sku_approvals')
        .select('master_sku, approved_at', { count: 'exact' })
        .eq('approval_status', 'approved')
        .order('approved_at', { ascending: false })
        .range(offset, offset + limit - 1)

      total = count ?? 0
      skus = (data || []).map((r) => ({
        master_sku: r.master_sku,
        detail: r.approved_at
          ? `Approved ${new Date(r.approved_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}`
          : undefined,
      }))
    } else if (stage === 'published') {
      // Distinct master_skus with successful publish events, most recent publish date as detail
      const { data } = await supabase
        .from('publish_events')
        .select('master_sku, created_at')
        .eq('status', 'success')
        .eq('action', 'publish')
        .order('master_sku', { ascending: true })
        .limit(10000)

      // Deduplicate keeping most recent publish date per SKU
      const skuMap = new Map<string, string>()
      for (const row of data || []) {
        const existing = skuMap.get(row.master_sku)
        if (!existing || row.created_at > existing) {
          skuMap.set(row.master_sku, row.created_at)
        }
      }

      const sortedSkus = [...skuMap.entries()].sort(([a], [b]) => a.localeCompare(b))
      total = sortedSkus.length
      skus = sortedSkus.slice(offset, offset + limit).map(([sku, publishedAt]) => ({
        master_sku: sku,
        detail: `Published ${new Date(publishedAt).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })}`,
      }))
    }

    const response: FunnelSkusResponse = {
      stage,
      skus,
      total,
      limit,
      offset,
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Funnel SKUs API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
