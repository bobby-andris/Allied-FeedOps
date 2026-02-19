import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export interface VariantDataEntry {
  finish: string
  finish_code: string
  total_impressions: number
  total_clicks: number
  has_lifestyle_image: boolean
  lifestyle_image_url: string | null
  lifestyle_image_created_at: string | null
}

export interface VariantDataResponse {
  variants: VariantDataEntry[]
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const masterSku = searchParams.get('master_sku')

    if (!masterSku) {
      return NextResponse.json(
        { error: 'master_sku query parameter is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // 1. Get full list of finishes from variant_index (source of truth)
    // Include gmc_offer_id to build reverse map for resolving search_queries with null finish_code
    const { data: variantIndexData, error: variantIndexError } = await supabase
      .from('variant_index')
      .select('finish, finish_code, gmc_offer_id')
      .eq('master_sku', masterSku)
      .not('finish', 'is', null)
      .not('finish_code', 'is', null)

    if (variantIndexError) {
      console.error('Error querying variant_index:', variantIndexError)
      return NextResponse.json(
        { error: 'Failed to fetch variant data' },
        { status: 500 }
      )
    }

    // Deduplicate finishes from variant_index (multiple variants can share same finish)
    // Also build gmc_offer_id → finish_code map for resolving search_queries rows with null finish_code
    const finishMap = new Map<string, { finish: string; finish_code: string }>()
    const offerIdToFinishCode = new Map<string, string>()
    for (const row of variantIndexData ?? []) {
      if (row.finish_code && !finishMap.has(row.finish_code)) {
        finishMap.set(row.finish_code, {
          finish: row.finish ?? '',
          finish_code: row.finish_code,
        })
      }
      if (row.gmc_offer_id && row.finish_code) {
        offerIdToFinishCode.set(row.gmc_offer_id, row.finish_code)
      }
    }

    // 2. Query search_queries for impression/click data
    // Fetch all rows (including those with null finish_code) — resolve via gmc_offer_id if needed
    const { data: searchData, error: searchError } = await supabase
      .from('search_queries')
      .select('finish_code, gmc_offer_id, impressions, clicks')
      .eq('master_sku', masterSku)

    if (searchError) {
      console.error('Error querying search_queries:', searchError)
      return NextResponse.json(
        { error: 'Failed to fetch search data' },
        { status: 500 }
      )
    }

    // Aggregate impressions/clicks by finish_code in JS
    // For rows with null finish_code, resolve via gmc_offer_id → variant_index lookup
    const impressionsByFinish = new Map<
      string,
      { total_impressions: number; total_clicks: number }
    >()
    for (const row of searchData ?? []) {
      const finishCode =
        row.finish_code ??
        (row.gmc_offer_id ? offerIdToFinishCode.get(row.gmc_offer_id) : null)
      if (!finishCode) continue
      const existing = impressionsByFinish.get(finishCode) ?? {
        total_impressions: 0,
        total_clicks: 0,
      }
      impressionsByFinish.set(finishCode, {
        total_impressions: existing.total_impressions + (row.impressions ?? 0),
        total_clicks: existing.total_clicks + (row.clicks ?? 0),
      })
    }

    // 3. Query variant_lifestyle_images for coverage data (most recent per finish_code)
    const { data: imageData, error: imageError } = await supabase
      .from('variant_lifestyle_images')
      .select('finish_code, thumbnail_url, image_url, created_at')
      .eq('master_sku', masterSku)
      .order('created_at', { ascending: false })

    if (imageError) {
      console.error('Error querying variant_lifestyle_images:', imageError)
      return NextResponse.json(
        { error: 'Failed to fetch image data' },
        { status: 500 }
      )
    }

    // Keep only the most recent image per finish_code
    const imageByFinish = new Map<
      string,
      { image_url: string | null; thumbnail_url: string | null; created_at: string | null }
    >()
    for (const row of imageData ?? []) {
      if (!row.finish_code) continue
      if (!imageByFinish.has(row.finish_code)) {
        imageByFinish.set(row.finish_code, {
          image_url: row.image_url ?? null,
          thumbnail_url: row.thumbnail_url ?? null,
          created_at: row.created_at ?? null,
        })
      }
    }

    // 4. Merge: build one entry per finish from variant_index
    const variants: VariantDataEntry[] = []
    for (const [finish_code, { finish }] of finishMap) {
      const impressions = impressionsByFinish.get(finish_code)
      const image = imageByFinish.get(finish_code)

      variants.push({
        finish,
        finish_code,
        total_impressions: impressions?.total_impressions ?? 0,
        total_clicks: impressions?.total_clicks ?? 0,
        has_lifestyle_image: imageByFinish.has(finish_code),
        lifestyle_image_url: image?.thumbnail_url ?? image?.image_url ?? null,
        lifestyle_image_created_at: image?.created_at ?? null,
      })
    }

    // 5. Sort by total_impressions descending (finishes with no search data sort to end)
    variants.sort((a, b) => b.total_impressions - a.total_impressions)

    return NextResponse.json({ variants } satisfies VariantDataResponse)
  } catch (error) {
    console.error('Variant data API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
