import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

// Types for the API response
interface SkuPerformance {
  sku: string
  name: string
  platform: string
  publishedAt: string
  daysSincePublish: number
  hasSnapshot: boolean
  baselineWindow: string
  snapshotWindow: string
  baseline: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
  current: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
}

interface VariantPerformance {
  gmc_offer_id: string
  finish: string | null
  finish_code: string | null
  impressions: number
  clicks: number
  ctr: number
}

interface SearchTerm {
  query_text: string
  impressions: number
  clicks: number
  ctr: number
}

interface SkuDetail {
  variants: VariantPerformance[]
  topSearchTerms: SearchTerm[]
}

interface PerformanceResponse {
  summary: {
    totalPublished: number
    totalWithSnapshot: number
    avgCtrChange: number
    avgCvrChange: number
    totalImpressions: number
    totalClicks: number
  }
  skus: SkuPerformance[]
  skuDetail: SkuDetail | null
  warnings: string[]
}

function daysBetween(publishedAt: string): number {
  const published = new Date(publishedAt)
  const today = new Date()
  const msPerDay = 1000 * 60 * 60 * 24
  return Math.floor((today.getTime() - published.getTime()) / msPerDay)
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const sku = searchParams.get('sku')
  const platform = searchParams.get('platform') || 'google'
  const baselineWindow = searchParams.get('baselineWindow') || '30d'
  const snapshotWindow = searchParams.get('snapshotWindow') || '30d'

  const warnings: string[] = []

  try {
    const supabase = await createClient()

    // 1. Query publish_events for successful publishes
    let publishQuery = supabase
      .from('publish_events')
      .select('master_sku, platform, published_at')
      .eq('status', 'success')
      .eq('action', 'publish')
      .order('published_at', { ascending: false })

    if (platform && platform !== 'all') {
      publishQuery = publishQuery.eq('platform', platform)
    }

    if (sku) {
      publishQuery = publishQuery.eq('master_sku', sku)
    }

    const { data: publishEvents, error: publishError } = await publishQuery

    if (publishError) {
      console.error('Failed to fetch publish events:', publishError)
      return NextResponse.json({ error: publishError.message }, { status: 500 })
    }

    // Get unique SKUs that have been published (first publish per SKU-platform)
    const publishedSkuMap = new Map<string, { publishedAt: string; platform: string }>()
    for (const event of publishEvents || []) {
      const key = `${event.master_sku}|||${event.platform}`
      if (!publishedSkuMap.has(key)) {
        publishedSkuMap.set(key, {
          publishedAt: event.published_at,
          platform: event.platform,
        })
      }
    }

    const uniqueSkus = [...new Set((publishEvents || []).map(e => e.master_sku))]

    // 2. Query variant_index to get product titles and offer IDs for variant-level joins
    const { data: variantIndexData, error: variantIndexError } = await supabase
      .from('variant_index')
      .select('master_sku, product_title, gmc_offer_id')
      .in('master_sku', uniqueSkus.length > 0 ? uniqueSkus : ['__none__'])

    if (variantIndexError) {
      console.error('Failed to fetch variant index:', variantIndexError)
      warnings.push('Failed to fetch product mapping data')
    }

    // Build SKU to product title mapping (first variant per master_sku)
    const skuToNameMap = new Map<string, string>()
    // Build offer ID to master_sku mapping for variant table aggregation
    const offerToSku = new Map<string, string>()
    const skuToOfferIds = new Map<string, string[]>()
    for (const variant of variantIndexData || []) {
      if (!skuToNameMap.has(variant.master_sku)) {
        skuToNameMap.set(variant.master_sku, variant.product_title || `SKU ${variant.master_sku}`)
      }
      if (variant.gmc_offer_id) {
        offerToSku.set(variant.gmc_offer_id, variant.master_sku)
        if (!skuToOfferIds.has(variant.master_sku)) {
          skuToOfferIds.set(variant.master_sku, [])
        }
        skuToOfferIds.get(variant.master_sku)!.push(variant.gmc_offer_id)
      }
    }
    const allOfferIds = [...offerToSku.keys()]

    // 3. Query baselines — prefer variant-level tables, fall back to master-level
    const baselineMap = new Map<string, {
      avgCtr: number
      avgCvr: number
      avgImpressions: number
      avgClicks: number
    }>()

    // 3a. Try variant baselines first (joined through variant_index via offer IDs)
    let usedVariantBaselines = false
    if (allOfferIds.length > 0) {
      let varBaselineQuery = supabase
        .from('performance_baselines_variant')
        .select('gmc_offer_id, platform, avg_ctr, avg_cvr, avg_impressions, avg_clicks')
        .in('gmc_offer_id', allOfferIds)

      if (platform && platform !== 'all') {
        varBaselineQuery = varBaselineQuery.eq('platform', platform)
      }

      const { data: varBaselines } = await varBaselineQuery

      if (varBaselines && varBaselines.length > 0) {
        usedVariantBaselines = true
        // Aggregate variant baselines to master_sku level
        const aggMap = new Map<string, { totalImpr: number; totalClicks: number; totalCvr: number; count: number }>()
        for (const vb of varBaselines) {
          const masterSku = offerToSku.get(vb.gmc_offer_id)
          if (!masterSku) continue
          const key = `${masterSku}|||${vb.platform}`
          if (!aggMap.has(key)) {
            aggMap.set(key, { totalImpr: 0, totalClicks: 0, totalCvr: 0, count: 0 })
          }
          const agg = aggMap.get(key)!
          agg.totalImpr += vb.avg_impressions || 0
          agg.totalClicks += vb.avg_clicks || 0
          agg.totalCvr += (vb.avg_cvr || 0) * (vb.avg_impressions || 0) // weighted CVR
          agg.count++
        }
        for (const [key, agg] of aggMap) {
          const avgCtr = agg.totalImpr > 0 ? agg.totalClicks / agg.totalImpr : 0
          const avgCvr = agg.totalImpr > 0 ? agg.totalCvr / agg.totalImpr : 0
          baselineMap.set(key, {
            avgCtr,
            avgCvr,
            avgImpressions: agg.totalImpr,
            avgClicks: agg.totalClicks,
          })
        }
      }
    }

    // 3b. Fall back to master-level baselines if variant tables empty
    if (!usedVariantBaselines) {
      let baselineQuery = supabase
        .from('performance_baselines')
        .select('master_sku, platform, avg_ctr, avg_cvr, avg_impressions, avg_clicks')

      if (uniqueSkus.length > 0) {
        baselineQuery = baselineQuery.in('master_sku', uniqueSkus)
      }

      if (platform && platform !== 'all') {
        baselineQuery = baselineQuery.eq('platform', platform)
      }

      const { data: baselines, error: baselineError } = await baselineQuery

      if (baselineError) {
        console.error('Failed to fetch baselines:', baselineError)
        warnings.push('Failed to fetch baseline data')
      }

      for (const baseline of baselines || []) {
        const key = `${baseline.master_sku}|||${baseline.platform}`
        baselineMap.set(key, {
          avgCtr: baseline.avg_ctr || 0,
          avgCvr: baseline.avg_cvr || 0,
          avgImpressions: baseline.avg_impressions || 0,
          avgClicks: baseline.avg_clicks || 0,
        })
      }
    }

    // 4. Query snapshots — prefer variant-level tables, fall back to master-level
    const snapshotsByKey = new Map<string, Array<{
      snapshot_date: string
      impressions: number
      clicks: number
      ctr: number
      cvr: number
      days_since_publish: number | null
    }>>()

    // 4a. Try variant snapshots first
    let usedVariantSnapshots = false
    if (allOfferIds.length > 0) {
      let varSnapQuery = supabase
        .from('performance_snapshots_variant')
        .select('gmc_offer_id, master_sku, platform, snapshot_date, impressions, clicks, ctr, roas')
        .order('snapshot_date', { ascending: false })
        .in('gmc_offer_id', allOfferIds)

      if (platform && platform !== 'all') {
        varSnapQuery = varSnapQuery.eq('platform', platform)
      }

      const { data: varSnapshots } = await varSnapQuery

      if (varSnapshots && varSnapshots.length > 0) {
        usedVariantSnapshots = true
        // Aggregate variant snapshots to master_sku level by date
        // Group by master_sku + platform + snapshot_date, then collapse to SKU-platform
        const dateAgg = new Map<string, { impressions: number; clicks: number }>()
        for (const vs of varSnapshots) {
          const masterSku = vs.master_sku || offerToSku.get(vs.gmc_offer_id)
          if (!masterSku) continue
          const dateKey = `${masterSku}|||${vs.platform}|||${vs.snapshot_date}`
          if (!dateAgg.has(dateKey)) {
            dateAgg.set(dateKey, { impressions: 0, clicks: 0 })
          }
          const entry = dateAgg.get(dateKey)!
          entry.impressions += vs.impressions || 0
          entry.clicks += vs.clicks || 0
        }

        // Convert date-aggregated data to snapshotsByKey format
        for (const [dateKey, data] of dateAgg) {
          const [masterSku, plat, snapDate] = dateKey.split('|||')
          const key = `${masterSku}|||${plat}`
          if (!snapshotsByKey.has(key)) {
            snapshotsByKey.set(key, [])
          }
          const ctr = data.impressions > 0 ? data.clicks / data.impressions : 0
          snapshotsByKey.get(key)!.push({
            snapshot_date: snapDate,
            impressions: data.impressions,
            clicks: data.clicks,
            ctr,
            cvr: 0,
            days_since_publish: null,
          })
        }

        // Sort each group by date descending
        for (const snaps of snapshotsByKey.values()) {
          snaps.sort((a, b) => b.snapshot_date.localeCompare(a.snapshot_date))
        }
      }
    }

    // 4b. Fall back to master-level snapshots if variant tables empty
    if (!usedVariantSnapshots) {
      let snapshotQuery = supabase
        .from('performance_snapshots')
        .select('master_sku, platform, snapshot_date, impressions, clicks, ctr, cvr, days_since_publish')
        .order('snapshot_date', { ascending: false })

      if (uniqueSkus.length > 0) {
        snapshotQuery = snapshotQuery.in('master_sku', uniqueSkus)
      }

      if (platform && platform !== 'all') {
        snapshotQuery = snapshotQuery.eq('platform', platform)
      }

      const { data: allSnapshots } = await snapshotQuery

      for (const snap of allSnapshots || []) {
        const key = `${snap.master_sku}|||${snap.platform}`
        if (!snapshotsByKey.has(key)) {
          snapshotsByKey.set(key, [])
        }
        snapshotsByKey.get(key)!.push(snap)
      }
    }

    // Check if any snapshots exist at all
    if (snapshotsByKey.size === 0 && uniqueSkus.length > 0) {
      warnings.push('No performance snapshots found. Run capture-snapshot to populate data.')
    }

    // 5. Build the response
    const skuPerformanceList: SkuPerformance[] = []

    for (const [key, publishInfo] of publishedSkuMap) {
      const skuId = key.split('|||')[0]
      const productName = skuToNameMap.get(skuId) || `SKU ${skuId}`

      const publishDate = publishInfo.publishedAt.split('T')[0]

      // Aggregate all snapshots for this SKU-platform to compute daily averages.
      // Each snapshot row contains ONE day of data (not cumulative).
      // Baselines store daily averages, so we must average snapshots the same way.
      const snapshots = snapshotsByKey.get(key) || []
      const hasSnapshot = snapshots.length > 0

      // daysSincePublish: from most recent snapshot if available, otherwise compute from today
      const daysSincePublish = hasSnapshot && snapshots[0].days_since_publish != null
        ? snapshots[0].days_since_publish
        : daysBetween(publishInfo.publishedAt)

      // Get baseline data
      const baselineKey = key
      const baseline = baselineMap.get(baselineKey) || {
        avgCtr: 0,
        avgCvr: 0,
        avgImpressions: 0,
        avgClicks: 0,
      }

      // Current metrics: average daily values across all snapshots in the window.
      // Each snapshot is 1 day of data. Sum and divide by actual snapshot count
      // to get daily averages comparable to baseline daily averages.
      // CTR and CVR are already rates — use the most recent snapshot's values.
      let current: { ctr: number; cvr: number; impressions: number; clicks: number }
      if (hasSnapshot) {
        const totalImpr = snapshots.reduce((sum, s) => sum + (s.impressions || 0), 0)
        const totalClk = snapshots.reduce((sum, s) => sum + (s.clicks || 0), 0)
        const snapshotCount = snapshots.length
        current = {
          ctr: snapshots[0].ctr || 0,
          cvr: snapshots[0].cvr || 0,
          impressions: Math.round(totalImpr / snapshotCount),
          clicks: Math.round(totalClk / snapshotCount),
        }
      } else {
        current = { ctr: 0, cvr: 0, impressions: 0, clicks: 0 }
      }

      skuPerformanceList.push({
        sku: skuId,
        name: productName,
        platform: publishInfo.platform,
        publishedAt: publishDate,
        daysSincePublish,
        hasSnapshot,
        baselineWindow,
        snapshotWindow,
        baseline: {
          ctr: baseline.avgCtr,
          cvr: baseline.avgCvr,
          impressions: baseline.avgImpressions,
          clicks: baseline.avgClicks,
        },
        current,
      })
    }

    // Calculate summary stats (only count hasSnapshot SKUs for avg changes)
    let totalCtrChange = 0
    let totalCvrChange = 0
    let validCtrCount = 0
    let validCvrCount = 0
    let totalImpressions = 0
    let totalClicks = 0
    let totalWithSnapshot = 0

    for (const skuPerf of skuPerformanceList) {
      if (skuPerf.hasSnapshot) {
        totalWithSnapshot++
        totalImpressions += skuPerf.current.impressions
        totalClicks += skuPerf.current.clicks

        if (skuPerf.baseline.ctr > 0) {
          const ctrChange = ((skuPerf.current.ctr - skuPerf.baseline.ctr) / skuPerf.baseline.ctr) * 100
          totalCtrChange += ctrChange
          validCtrCount++
        }

        if (skuPerf.baseline.cvr > 0) {
          const cvrChange = ((skuPerf.current.cvr - skuPerf.baseline.cvr) / skuPerf.baseline.cvr) * 100
          totalCvrChange += cvrChange
          validCvrCount++
        }
      }
    }

    // 6. If sku param is provided, build skuDetail (variant breakdown + top search terms)
    let skuDetail: SkuDetail | null = null

    if (sku) {
      // Step 1: Get all gmc_offer_ids for this master_sku from variant_index.
      // Querying search_queries by master_sku fails for historical rows where
      // master_sku is null (synced before the lowercase fix). Using offer IDs
      // from variant_index is resilient to that null.
      const { data: variantRows } = await supabase
        .from('variant_index')
        .select('gmc_offer_id, finish, finish_code')
        .eq('master_sku', sku)

      const offerIds = (variantRows || [])
        .map(v => v.gmc_offer_id)
        .filter(Boolean) as string[]

      // Build finish/finish_code lookup by offer_id for enrichment of null-finish rows
      const offerFinishMap = new Map<string, { finish: string | null; finish_code: string | null }>()
      for (const v of variantRows || []) {
        if (v.gmc_offer_id) {
          offerFinishMap.set(v.gmc_offer_id, {
            finish: v.finish ?? null,
            finish_code: v.finish_code ?? null,
          })
        }
      }

      // Step 2: Query search_queries by gmc_offer_id (resilient to null master_sku in historical rows)
      // variant_index stores lowercase shopify_us_ but search_queries stores uppercase shopify_US_
      const upperOfferIds = offerIds.map(id => id.replace('shopify_us_', 'shopify_US_'))

      const { data: searchQueryRows } = offerIds.length > 0
        ? await supabase
            .from('search_queries')
            .select('gmc_offer_id, finish, finish_code, query_text, impressions, clicks, ctr')
            .in('gmc_offer_id', upperOfferIds)
        : { data: [] }

      const rows = (searchQueryRows || []) as Array<{
        gmc_offer_id: string
        finish: string | null
        finish_code: string | null
        query_text: string
        impressions: number
        clicks: number
        ctr: number
      }>

      // --- Variant breakdown: group by gmc_offer_id, sum impressions/clicks ---
      const variantMap = new Map<string, {
        finish: string | null
        finish_code: string | null
        impressions: number
        clicks: number
      }>()

      for (const row of rows) {
        // Enrich finish from variant_index if missing on the search_queries row (historical data)
        if (!row.finish || !row.finish_code) {
          const offerKey = offerFinishMap.get(row.gmc_offer_id)
            ?? offerFinishMap.get(row.gmc_offer_id?.toLowerCase?.())
          if (offerKey) {
            if (!row.finish) row.finish = offerKey.finish
            if (!row.finish_code) row.finish_code = offerKey.finish_code
          }
        }

        const offerId: string = row.gmc_offer_id
        if (!variantMap.has(offerId)) {
          variantMap.set(offerId, {
            finish: row.finish ?? null,
            finish_code: row.finish_code ?? null,
            impressions: 0,
            clicks: 0,
          })
        }
        const entry = variantMap.get(offerId)!
        entry.impressions += row.impressions || 0
        entry.clicks += row.clicks || 0
        // Use finish from this row if we haven't set it yet
        if (!entry.finish && row.finish) {
          entry.finish = row.finish
        }
        if (!entry.finish_code && row.finish_code) {
          entry.finish_code = row.finish_code
        }
      }

      const variants: VariantPerformance[] = []
      for (const [offerId, data] of variantMap) {
        if (data.impressions === 0) continue // skip zero-impression variants
        const ctr = data.impressions > 0
          ? Math.round((data.clicks / data.impressions) * 10000) / 100
          : 0
        variants.push({
          gmc_offer_id: offerId,
          finish: data.finish,
          finish_code: data.finish_code,
          impressions: data.impressions,
          clicks: data.clicks,
          ctr,
        })
      }

      // Sort by impressions descending, take top 20
      variants.sort((a, b) => b.impressions - a.impressions)
      const topVariants = variants.slice(0, 20)

      // --- Top search terms: group by query_text, sum impressions/clicks ---
      const termMap = new Map<string, { impressions: number; clicks: number }>()

      for (const row of rows) {
        const qt: string = row.query_text
        if (!termMap.has(qt)) {
          termMap.set(qt, { impressions: 0, clicks: 0 })
        }
        const entry = termMap.get(qt)!
        entry.impressions += row.impressions || 0
        entry.clicks += row.clicks || 0
      }

      const allTerms: SearchTerm[] = []
      for (const [queryText, data] of termMap) {
        const termCtr = data.impressions > 0
          ? Math.round((data.clicks / data.impressions) * 10000) / 100
          : 0
        allTerms.push({
          query_text: queryText,
          impressions: data.impressions,
          clicks: data.clicks,
          ctr: termCtr,
        })
      }

      // Sort by impressions descending, take top 10 after dedup
      allTerms.sort((a, b) => b.impressions - a.impressions)
      const topSearchTerms = allTerms.slice(0, 10)

      skuDetail = {
        variants: topVariants,
        topSearchTerms,
      }
    }

    const response: PerformanceResponse = {
      summary: {
        totalPublished: skuPerformanceList.length,
        totalWithSnapshot,
        avgCtrChange: validCtrCount > 0 ? totalCtrChange / validCtrCount : 0,
        avgCvrChange: validCvrCount > 0 ? totalCvrChange / validCvrCount : 0,
        totalImpressions,
        totalClicks,
      },
      skus: skuPerformanceList,
      skuDetail,
      warnings,
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Performance API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
