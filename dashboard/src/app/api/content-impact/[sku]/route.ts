import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { getSkuCandidates } from '@/lib/sku-utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ImpactTier =
  | 'strong_improvement'
  | 'moderate_improvement'
  | 'no_change'
  | 'moderate_decline'
  | 'decline'
  | 'insufficient_data'

interface WindowMetrics {
  available: boolean
  avg_ctr?: number
  avg_cvr?: number
  ctr_delta?: number
  cvr_delta?: number
  data_points?: number
  pending_days?: number
}

interface SnapshotDataPoint {
  snapshot_date: string
  days_since_publish: number | null
  ctr: number | null
  cvr: number | null
  impressions: number | null
  clicks: number | null
}

interface ImpactScoreDetail {
  metric_name: string
  pre_value: number | null
  post_value: number | null
  control_pre: number | null
  control_post: number | null
  did_lift_pct: number | null
  label: string | null
  confidence: number | null
  sample_size_treated: number
  sample_size_control: number
}

interface ControlSku {
  master_sku: string
  product_category: string | null
  avg_ctr: number | null
  avg_cvr: number | null
}

interface PublishHistoryEntry {
  publish_event_id: number
  published_at: string
  prompt_hash: string | null
  content_version: number | null
  impact_tier: ImpactTier
  impact_label: string
}

interface DetailResponse {
  publish_event_id: number
  master_sku: string
  platform: string
  published_at: string
  prompt_hash: string | null
  content_version: number | null
  baseline: { avg_ctr: number; avg_cvr: number; avg_impressions: number; avg_clicks: number } | null
  windows: {
    d7: WindowMetrics | null
    d14: WindowMetrics | null
    d30: WindowMetrics | null
  }
  snapshots: SnapshotDataPoint[]
  impact_scores: ImpactScoreDetail[]
  control_skus: ControlSku[]
  publish_history: PublishHistoryEntry[]
}

// ---------------------------------------------------------------------------
// Impact classification (same as landing route)
// ---------------------------------------------------------------------------

function classifyImpact(
  score: { did_lift_pct: number | null; sample_size_treated: number; sample_size_control: number } | null
): { tier: ImpactTier; label: string } {
  if (!score || score.sample_size_treated < 7 || score.sample_size_control < 7) {
    return { tier: 'insufficient_data', label: 'Insufficient Data' }
  }
  const lift = score.did_lift_pct
  if (lift === null) {
    return { tier: 'insufficient_data', label: 'Insufficient Data' }
  }
  if (lift >= 10) return { tier: 'strong_improvement', label: 'Strong Improvement' }
  if (lift >= 3) return { tier: 'moderate_improvement', label: 'Moderate Improvement' }
  if (lift <= -10) return { tier: 'decline', label: 'Decline' }
  if (lift <= -3) return { tier: 'moderate_decline', label: 'Moderate Decline' }
  return { tier: 'no_change', label: 'No Significant Change' }
}

// ---------------------------------------------------------------------------
// Window aggregation (same as landing route)
// ---------------------------------------------------------------------------

function aggregateWindow(
  snapshots: Array<{
    days_since_publish: number | null
    ctr: number | null
    cvr: number | null
    impressions: number | null
  }>,
  windowSize: number,
  daysElapsed: number,
  baseline: { avg_ctr: number; avg_cvr: number } | null
): WindowMetrics | null {
  const inWindow = snapshots.filter(
    (s) =>
      s.days_since_publish !== null &&
      s.days_since_publish >= 1 &&
      s.days_since_publish <= windowSize
  )

  if (inWindow.length === 0) {
    const pending = Math.max(0, windowSize - daysElapsed)
    if (pending > 0) {
      return { available: false, pending_days: pending }
    }
    return null
  }

  const totalImpressions = inWindow.reduce(
    (sum, s) => sum + (s.impressions ?? 0),
    0
  )
  if (totalImpressions < 50) {
    return null
  }

  const avgCtr =
    inWindow.reduce((sum, s) => sum + (s.ctr ?? 0), 0) / inWindow.length
  const avgCvr =
    inWindow.reduce((sum, s) => sum + (s.cvr ?? 0), 0) / inWindow.length

  return {
    available: true,
    avg_ctr: avgCtr,
    avg_cvr: avgCvr,
    ctr_delta: baseline ? avgCtr - baseline.avg_ctr : undefined,
    cvr_delta: baseline ? avgCvr - baseline.avg_cvr : undefined,
    data_points: inWindow.length,
  }
}

// ---------------------------------------------------------------------------
// SKU resolver: try candidates until one matches
// ---------------------------------------------------------------------------

async function resolveSkuFromPublishEvents(
  supabase: Awaited<ReturnType<typeof createClient>>,
  urlSku: string
): Promise<string | null> {
  const candidates = getSkuCandidates(urlSku)
  for (const candidate of candidates) {
    const { data } = await supabase
      .from('publish_events')
      .select('master_sku')
      .eq('master_sku', candidate)
      .limit(1)
    if (data && data.length > 0) {
      return data[0].master_sku
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// GET handler
// ---------------------------------------------------------------------------

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sku: string }> }
) {
  try {
    const supabase = await createClient()
    const { sku: urlSku } = await params
    const { searchParams } = new URL(request.url)
    const eventIdParam = searchParams.get('event_id')

    // Resolve SKU from URL format to database format
    const masterSku = await resolveSkuFromPublishEvents(supabase, urlSku)
    if (!masterSku) {
      return NextResponse.json(
        { error: `No publish events found for SKU: ${urlSku}` },
        { status: 404 }
      )
    }

    // 1. Get the target publish event
    let targetEvent: {
      id: number
      master_sku: string
      platform: string
      published_at: string
      prompt_hash: string | null
      content_version: number | null
      product_category: string | null
    }

    if (eventIdParam) {
      const { data, error } = await supabase
        .from('publish_events')
        .select('id, master_sku, platform, published_at, prompt_hash, content_version, product_category')
        .eq('id', parseInt(eventIdParam))
        .single()

      if (error || !data) {
        return NextResponse.json(
          { error: `Publish event ${eventIdParam} not found` },
          { status: 404 }
        )
      }
      targetEvent = data
    } else {
      // Use latest publish event for this SKU
      const { data, error } = await supabase
        .from('publish_events')
        .select('id, master_sku, platform, published_at, prompt_hash, content_version, product_category')
        .eq('master_sku', masterSku)
        .eq('status', 'success')
        .eq('action', 'publish')
        .order('published_at', { ascending: false })
        .limit(1)
        .single()

      if (error || !data) {
        return NextResponse.json(
          { error: `No publish events found for SKU: ${masterSku}` },
          { status: 404 }
        )
      }
      targetEvent = data
    }

    // 2. Fetch baseline metrics
    const { data: baselineData } = await supabase
      .from('performance_baselines')
      .select('avg_ctr, avg_cvr, avg_impressions, avg_clicks')
      .eq('master_sku', targetEvent.master_sku)
      .eq('platform', targetEvent.platform)
      .limit(1)
      .single()

    const baseline = baselineData
      ? {
          avg_ctr: baselineData.avg_ctr ?? 0,
          avg_cvr: baselineData.avg_cvr ?? 0,
          avg_impressions: baselineData.avg_impressions ?? 0,
          avg_clicks: baselineData.avg_clicks ?? 0,
        }
      : null

    // 3. Fetch performance snapshots (treated cohort) for this event
    const { data: snapshotsRaw } = await supabase
      .from('performance_snapshots')
      .select('snapshot_date, days_since_publish, ctr, cvr, impressions, clicks, cohort_type')
      .eq('publish_event_id', targetEvent.id)
      .order('snapshot_date', { ascending: true })

    // Separate treated and all snapshots
    const treatedSnapshots = (snapshotsRaw || []).filter(
      (s) => !s.cohort_type || s.cohort_type === 'treated'
    )

    const snapshotDataPoints: SnapshotDataPoint[] = treatedSnapshots.map((s) => ({
      snapshot_date: s.snapshot_date,
      days_since_publish: s.days_since_publish,
      ctr: s.ctr,
      cvr: s.cvr,
      impressions: s.impressions,
      clicks: s.clicks,
    }))

    // 4. Window aggregation
    const now = new Date()
    const publishDate = new Date(targetEvent.published_at)
    const daysElapsed = Math.floor(
      (now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24)
    )

    const baselineForWindows = baseline
      ? { avg_ctr: baseline.avg_ctr, avg_cvr: baseline.avg_cvr }
      : null

    const d7 = aggregateWindow(treatedSnapshots, 7, daysElapsed, baselineForWindows)
    const d14 = aggregateWindow(treatedSnapshots, 14, daysElapsed, baselineForWindows)
    const d30 = aggregateWindow(treatedSnapshots, 30, daysElapsed, baselineForWindows)

    // 5. Fetch impact scores for this event
    const { data: impactScoresRaw } = await supabase
      .from('performance_impact_scores')
      .select(
        'metric_name, pre_value, post_value, control_pre, control_post, did_lift_pct, label, confidence, sample_size_treated, sample_size_control'
      )
      .eq('publish_event_id', targetEvent.id)

    const impactScores: ImpactScoreDetail[] = (impactScoresRaw || []).map((s) => ({
      metric_name: s.metric_name,
      pre_value: s.pre_value !== null ? Number(s.pre_value) : null,
      post_value: s.post_value !== null ? Number(s.post_value) : null,
      control_pre: s.control_pre !== null ? Number(s.control_pre) : null,
      control_post: s.control_post !== null ? Number(s.control_post) : null,
      did_lift_pct: s.did_lift_pct !== null ? Number(s.did_lift_pct) : null,
      label: s.label,
      confidence: s.confidence !== null ? Number(s.confidence) : null,
      sample_size_treated: s.sample_size_treated,
      sample_size_control: s.sample_size_control,
    }))

    // 6. Fetch control cohort SKUs
    const controlSnapshots = (snapshotsRaw || []).filter(
      (s) => s.cohort_type === 'control'
    )

    // Get distinct control SKUs from performance_snapshots with cohort_type = 'control'
    // Since control snapshots may have master_sku info, we query separately
    const { data: controlSnapshotSkus } = await supabase
      .from('performance_snapshots')
      .select('master_sku, ctr, cvr')
      .eq('publish_event_id', targetEvent.id)
      .eq('cohort_type', 'control')

    // Aggregate control SKUs
    const controlSkuMap = new Map<string, { ctrs: number[]; cvrs: number[] }>()
    for (const cs of controlSnapshotSkus || []) {
      if (!controlSkuMap.has(cs.master_sku)) {
        controlSkuMap.set(cs.master_sku, { ctrs: [], cvrs: [] })
      }
      const entry = controlSkuMap.get(cs.master_sku)!
      if (cs.ctr !== null) entry.ctrs.push(Number(cs.ctr))
      if (cs.cvr !== null) entry.cvrs.push(Number(cs.cvr))
    }

    // Fetch product_category for control SKUs from publish_events or baselines
    const controlSkuNames = [...controlSkuMap.keys()]
    const controlCategories = new Map<string, string | null>()
    if (controlSkuNames.length > 0) {
      const { data: catData } = await supabase
        .from('performance_baselines')
        .select('master_sku, product_category')
        .in('master_sku', controlSkuNames)

      for (const c of catData || []) {
        controlCategories.set(c.master_sku, c.product_category ?? null)
      }
    }

    const controlSkus: ControlSku[] = controlSkuNames.map((sku) => {
      const entry = controlSkuMap.get(sku)!
      const avgCtr = entry.ctrs.length > 0
        ? entry.ctrs.reduce((a, b) => a + b, 0) / entry.ctrs.length
        : null
      const avgCvr = entry.cvrs.length > 0
        ? entry.cvrs.reduce((a, b) => a + b, 0) / entry.cvrs.length
        : null
      return {
        master_sku: sku,
        product_category: controlCategories.get(sku) ?? null,
        avg_ctr: avgCtr,
        avg_cvr: avgCvr,
      }
    })

    // 7. Fetch publish history for this SKU + platform
    const { data: historyRaw } = await supabase
      .from('publish_events')
      .select('id, published_at, prompt_hash, content_version')
      .eq('master_sku', targetEvent.master_sku)
      .eq('platform', targetEvent.platform)
      .eq('status', 'success')
      .eq('action', 'publish')
      .order('published_at', { ascending: false })

    // For each historical event, get its CTR impact score for tier classification
    const historyEventIds = (historyRaw || []).map((h) => h.id)
    const { data: historyScores } = historyEventIds.length > 0
      ? await supabase
          .from('performance_impact_scores')
          .select('publish_event_id, did_lift_pct, sample_size_treated, sample_size_control')
          .in('publish_event_id', historyEventIds)
          .eq('metric_name', 'ctr')
      : { data: [] }

    const historyScoreMap = new Map<number, { did_lift_pct: number | null; sample_size_treated: number; sample_size_control: number }>()
    for (const hs of historyScores || []) {
      historyScoreMap.set(hs.publish_event_id, {
        did_lift_pct: hs.did_lift_pct !== null ? Number(hs.did_lift_pct) : null,
        sample_size_treated: hs.sample_size_treated,
        sample_size_control: hs.sample_size_control,
      })
    }

    const publishHistory: PublishHistoryEntry[] = (historyRaw || []).map((h) => {
      const score = historyScoreMap.get(h.id) ?? null
      const classification = classifyImpact(score)
      return {
        publish_event_id: h.id,
        published_at: h.published_at,
        prompt_hash: h.prompt_hash,
        content_version: h.content_version,
        impact_tier: classification.tier,
        impact_label: classification.label,
      }
    })

    // 8. Build response
    // Suppress unused variable warning — controlSnapshots used for filtering logic
    void controlSnapshots

    const response: DetailResponse = {
      publish_event_id: targetEvent.id,
      master_sku: targetEvent.master_sku,
      platform: targetEvent.platform,
      published_at: targetEvent.published_at,
      prompt_hash: targetEvent.prompt_hash,
      content_version: targetEvent.content_version,
      baseline,
      windows: { d7, d14, d30 },
      snapshots: snapshotDataPoints,
      impact_scores: impactScores,
      control_skus: controlSkus,
      publish_history: publishHistory,
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Content Impact Detail API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
