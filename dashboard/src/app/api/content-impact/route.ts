import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

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

interface ContentImpactRow {
  publish_event_id: number
  master_sku: string
  platform: string
  published_at: string
  prompt_hash: string | null
  has_baseline: boolean
  baseline: { avg_ctr: number; avg_cvr: number } | null
  windows: {
    d7: WindowMetrics | null
    d14: WindowMetrics | null
    d30: WindowMetrics | null
  }
  impact: {
    tier: ImpactTier
    label: string
    color: string
    ctr_lift: number | null
    cvr_lift: number | null
  }
  is_latest_publish: boolean
}

// ---------------------------------------------------------------------------
// Impact classification
// ---------------------------------------------------------------------------

interface ImpactScore {
  did_lift_pct: number | null
  sample_size_treated: number
  sample_size_control: number
}

function classifyImpact(
  score: ImpactScore | null
): { tier: ImpactTier; label: string; color: string } {
  if (!score || score.sample_size_treated < 7 || score.sample_size_control < 7) {
    return { tier: 'insufficient_data', label: 'Insufficient Data', color: 'gray' }
  }
  const lift = score.did_lift_pct
  if (lift === null) {
    return { tier: 'insufficient_data', label: 'Insufficient Data', color: 'gray' }
  }
  if (lift >= 10) return { tier: 'strong_improvement', label: 'Strong Improvement', color: 'green' }
  if (lift >= 3) return { tier: 'moderate_improvement', label: 'Moderate Improvement', color: 'emerald' }
  if (lift <= -10) return { tier: 'decline', label: 'Decline', color: 'red' }
  if (lift <= -3) return { tier: 'moderate_decline', label: 'Moderate Decline', color: 'orange' }
  return { tier: 'no_change', label: 'No Significant Change', color: 'gray' }
}

// ---------------------------------------------------------------------------
// Window aggregation helper
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
  // Filter snapshots to the window (exclude day 0 per research pitfall #4)
  const inWindow = snapshots.filter(
    (s) =>
      s.days_since_publish !== null &&
      s.days_since_publish >= 1 &&
      s.days_since_publish <= windowSize
  )

  if (inWindow.length === 0) {
    // Not yet available
    const pending = Math.max(0, windowSize - daysElapsed)
    if (pending > 0) {
      return { available: false, pending_days: pending }
    }
    // Window elapsed but no data
    return null
  }

  // Check minimum impression threshold: total window impressions < 50 => insufficient
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
// GET handler
// ---------------------------------------------------------------------------

export async function GET() {
  try {
    const supabase = await createClient()

    // 1. Fetch successful publish events
    const { data: publishEvents, error: publishError } = await supabase
      .from('publish_events')
      .select(
        'id, master_sku, platform, published_at, prompt_hash, content_version, product_category'
      )
      .eq('status', 'success')
      .eq('action', 'publish')
      .order('published_at', { ascending: false })

    if (publishError) {
      console.error('Failed to fetch publish events:', publishError)
      return NextResponse.json({ error: publishError.message }, { status: 500 })
    }

    if (!publishEvents || publishEvents.length === 0) {
      return NextResponse.json([])
    }

    // 2. Extract unique master_skus and event IDs
    const uniqueSkus = [...new Set(publishEvents.map((e) => e.master_sku))]
    const eventIds = publishEvents.map((e) => e.id)

    // 3. Query performance_baselines
    const { data: baselines } = await supabase
      .from('performance_baselines')
      .select('master_sku, platform, avg_ctr, avg_cvr, avg_impressions, avg_clicks')
      .in('master_sku', uniqueSkus)

    const baselineMap = new Map<
      string,
      { avg_ctr: number; avg_cvr: number }
    >()
    for (const b of baselines || []) {
      baselineMap.set(`${b.master_sku}|||${b.platform}`, {
        avg_ctr: b.avg_ctr ?? 0,
        avg_cvr: b.avg_cvr ?? 0,
      })
    }

    // 4. Query performance_snapshots for these SKUs
    const { data: snapshots } = await supabase
      .from('performance_snapshots')
      .select(
        'master_sku, platform, snapshot_date, ctr, cvr, impressions, clicks, days_since_publish, publish_event_id'
      )
      .in('master_sku', uniqueSkus)
      .order('snapshot_date', { ascending: false })

    // Group snapshots by publish_event_id
    const snapshotsByEvent = new Map<
      number,
      Array<{
        days_since_publish: number | null
        ctr: number | null
        cvr: number | null
        impressions: number | null
      }>
    >()
    for (const s of snapshots || []) {
      if (s.publish_event_id == null) continue
      if (!snapshotsByEvent.has(s.publish_event_id)) {
        snapshotsByEvent.set(s.publish_event_id, [])
      }
      snapshotsByEvent.get(s.publish_event_id)!.push({
        days_since_publish: s.days_since_publish,
        ctr: s.ctr,
        cvr: s.cvr,
        impressions: s.impressions,
      })
    }

    // 5. Query performance_impact_scores for event IDs (CTR + CVR)
    const { data: impactScores } = await supabase
      .from('performance_impact_scores')
      .select(
        'publish_event_id, metric_name, did_lift_pct, label, confidence, sample_size_treated, sample_size_control'
      )
      .in('publish_event_id', eventIds)
      .in('metric_name', ['ctr', 'cvr'])

    // Group impact scores by event and metric
    const impactMap = new Map<
      string,
      {
        did_lift_pct: number | null
        sample_size_treated: number
        sample_size_control: number
      }
    >()
    for (const score of impactScores || []) {
      impactMap.set(`${score.publish_event_id}|||${score.metric_name}`, {
        did_lift_pct:
          score.did_lift_pct !== null ? Number(score.did_lift_pct) : null,
        sample_size_treated: score.sample_size_treated,
        sample_size_control: score.sample_size_control,
      })
    }

    // 6. Determine latest publish per (master_sku, platform)
    const latestPublishMap = new Map<string, number>()
    for (const event of publishEvents) {
      const key = `${event.master_sku}|||${event.platform}`
      if (!latestPublishMap.has(key)) {
        // Events are already sorted by published_at DESC, so first seen = latest
        latestPublishMap.set(key, event.id)
      }
    }

    // 7. Build response rows
    const now = new Date()
    const rows: ContentImpactRow[] = publishEvents.map((event) => {
      const skuPlatformKey = `${event.master_sku}|||${event.platform}`
      const baseline = baselineMap.get(skuPlatformKey) ?? null
      const eventSnapshots = snapshotsByEvent.get(event.id) || []

      // Days elapsed since publish
      const publishDate = new Date(event.published_at)
      const daysElapsed = Math.floor(
        (now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24)
      )

      // Window aggregation
      const d7 = aggregateWindow(eventSnapshots, 7, daysElapsed, baseline)
      const d14 = aggregateWindow(eventSnapshots, 14, daysElapsed, baseline)
      const d30 = aggregateWindow(eventSnapshots, 30, daysElapsed, baseline)

      // Impact classification — prefer CTR score
      const ctrScore = impactMap.get(`${event.id}|||ctr`) ?? null
      const cvrScore = impactMap.get(`${event.id}|||cvr`) ?? null
      const impactClassification = classifyImpact(ctrScore)

      return {
        publish_event_id: event.id,
        master_sku: event.master_sku,
        platform: event.platform,
        published_at: event.published_at,
        prompt_hash: event.prompt_hash ?? null,
        has_baseline: baseline !== null,
        baseline,
        windows: { d7, d14, d30 },
        impact: {
          ...impactClassification,
          ctr_lift: ctrScore?.did_lift_pct ?? null,
          cvr_lift: cvrScore?.did_lift_pct ?? null,
        },
        is_latest_publish: latestPublishMap.get(skuPlatformKey) === event.id,
      }
    })

    return NextResponse.json(rows)
  } catch (error) {
    console.error('Content Impact API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
