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

function parseWindowDays(window: string): number {
  if (window === '7d') return 7
  if (window === '60d') return 60
  return 30 // default '30d'
}

function addDays(dateStr: string, days: number): string {
  const date = new Date(dateStr)
  date.setDate(date.getDate() + days)
  return date.toISOString().split('T')[0]
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

  const snapshotWindowDays = parseWindowDays(snapshotWindow)

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

    // 2. Query variant_index to get product titles
    const { data: variantIndexData, error: variantIndexError } = await supabase
      .from('variant_index')
      .select('master_sku, product_title')
      .in('master_sku', uniqueSkus.length > 0 ? uniqueSkus : ['__none__'])

    if (variantIndexError) {
      console.error('Failed to fetch variant index:', variantIndexError)
      warnings.push('Failed to fetch product mapping data')
    }

    // Build SKU to product title mapping (first variant per master_sku)
    const skuToNameMap = new Map<string, string>()
    for (const variant of variantIndexData || []) {
      if (!skuToNameMap.has(variant.master_sku)) {
        skuToNameMap.set(variant.master_sku, variant.product_title || `SKU ${variant.master_sku}`)
      }
    }

    // 3. Query performance_baselines for these SKUs
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

    // Create a map of baselines by SKU-platform
    const baselineMap = new Map<string, {
      avgCtr: number
      avgCvr: number
      avgImpressions: number
      avgClicks: number
    }>()

    for (const baseline of baselines || []) {
      const key = `${baseline.master_sku}|||${baseline.platform}`
      baselineMap.set(key, {
        avgCtr: baseline.avg_ctr || 0,
        avgCvr: baseline.avg_cvr || 0,
        avgImpressions: baseline.avg_impressions || 0,
        avgClicks: baseline.avg_clicks || 0,
      })
    }

    // 4. For each published SKU, find the latest snapshot within the snapshotWindow
    //    snapshot_date >= publish_date AND snapshot_date <= publish_date + snapshotWindowDays
    //    We do a single query for all SKUs and then filter in JS
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

    // Group snapshots by SKU-platform key
    const snapshotsByKey = new Map<string, Array<{
      snapshot_date: string
      impressions: number
      clicks: number
      ctr: number
      cvr: number
      days_since_publish: number | null
    }>>()

    for (const snap of allSnapshots || []) {
      const key = `${snap.master_sku}|||${snap.platform}`
      if (!snapshotsByKey.has(key)) {
        snapshotsByKey.set(key, [])
      }
      snapshotsByKey.get(key)!.push(snap)
    }

    // Check if any snapshots exist at all
    if ((allSnapshots || []).length === 0 && uniqueSkus.length > 0) {
      warnings.push('No performance snapshots found. Run capture-snapshot to populate data.')
    }

    // 5. Build the response
    const skuPerformanceList: SkuPerformance[] = []

    for (const [key, publishInfo] of publishedSkuMap) {
      const skuId = key.split('|||')[0]
      const productName = skuToNameMap.get(skuId) || `SKU ${skuId}`

      const publishDate = publishInfo.publishedAt.split('T')[0]
      const publishDatePlus = addDays(publishDate, snapshotWindowDays)

      // Find the latest snapshot within the window [publishDate, publishDate + snapshotWindowDays]
      const snapshots = snapshotsByKey.get(key) || []
      const windowSnapshot = snapshots.find(s =>
        s.snapshot_date >= publishDate && s.snapshot_date <= publishDatePlus
      )

      const hasSnapshot = !!windowSnapshot

      // daysSincePublish: from snapshot record if available, otherwise compute from today
      const daysSincePublish = hasSnapshot && windowSnapshot!.days_since_publish != null
        ? windowSnapshot!.days_since_publish
        : daysBetween(publishInfo.publishedAt)

      // Get baseline data
      const baselineKey = key
      const baseline = baselineMap.get(baselineKey) || {
        avgCtr: 0,
        avgCvr: 0,
        avgImpressions: 0,
        avgClicks: 0,
      }

      // Current metrics: from the matched snapshot, or zero if no snapshot.
      // impressions/clicks in snapshots are cumulative totals over the window period,
      // while baseline stores daily averages (avg_impressions = total / 30).
      // Divide by snapshotWindowDays to normalize to daily averages for valid delta comparison.
      // CTR and CVR are already rates — no normalization needed.
      const current = hasSnapshot
        ? {
            ctr: windowSnapshot!.ctr || 0,
            cvr: windowSnapshot!.cvr || 0,
            impressions: Math.round((windowSnapshot!.impressions || 0) / snapshotWindowDays),
            clicks: Math.round((windowSnapshot!.clicks || 0) / snapshotWindowDays),
          }
        : {
            ctr: 0,
            cvr: 0,
            impressions: 0,
            clicks: 0,
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
      // Fetch all search_queries rows for this master_sku
      const { data: searchQueryRows } = await supabase
        .from('search_queries')
        .select('gmc_offer_id, finish, finish_code, query_text, impressions, clicks, ctr')
        .eq('master_sku', sku)

      const rows = searchQueryRows || []

      // --- Variant breakdown: group by gmc_offer_id, sum impressions/clicks ---
      const variantMap = new Map<string, {
        finish: string | null
        finish_code: string | null
        impressions: number
        clicks: number
      }>()

      for (const row of rows) {
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
