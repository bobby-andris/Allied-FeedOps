import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

type ImpactLabel = 'positive' | 'negative' | 'neutral'

interface MetricDelta {
  pre_value: number | null
  post_value: number | null
  control_pre: number | null
  control_post: number | null
  did_lift_pct: number | null
}

interface PerformanceDelta {
  master_sku: string
  platform: string
  environment: string
  publish_event_id: number
  content_version: number | null
  published_at: string | null
  days_since_publish: number | null
  label: ImpactLabel
  confidence: number
  sample_size_treated: number
  sample_size_control: number
  primary_roas_did_lift_pct: number | null
  guardrails: {
    impressions: number | null
    conversions: number | null
    ctr: number | null
    cvr: number | null
    clicks: number | null
    cost: number | null
    conversion_value: number | null
  }
  metrics: Record<string, MetricDelta>
}

const metricNames = [
  'roas',
  'cvr',
  'ctr',
  'clicks',
  'conversions',
  'cost',
  'conversion_value',
  'impressions',
] as const

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const getSignificance = (confidence: number): 'high' | 'medium' | 'low' => {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.55) return 'medium'
  return 'low'
}

const parseDate = (value: unknown): Date | null => {
  if (!value) return null
  const dt = new Date(String(value))
  return Number.isNaN(dt.getTime()) ? null : dt
}

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const filterSku = searchParams.get('master_sku')
    const filterPlatform = searchParams.get('platform') || 'google'
    const filterEnvironment = searchParams.get('environment') || 'production'

    let impactQuery = supabase
      .from('performance_impact_scores')
      .select(
        'publish_event_id,master_sku,platform,environment,metric_name,pre_value,post_value,control_pre,control_post,did_lift_pct,label,confidence,sample_size_treated,sample_size_control,window_pre_days,window_post_days,run_date,computed_at'
      )
      .eq('platform', filterPlatform)
      .eq('environment', filterEnvironment)
      .in('metric_name', [...metricNames])
      .order('computed_at', { ascending: false })
      .limit(10000)

    if (filterSku) {
      impactQuery = impactQuery.eq('master_sku', filterSku)
    }

    const { data: impactRows, error: impactError } = await impactQuery
    if (impactError) {
      return NextResponse.json(
        { error: `Failed to fetch impact scores: ${impactError.message}` },
        { status: 500 }
      )
    }

    const { data: latestSnapshotRows, error: snapshotError } = await supabase
      .from('performance_snapshots')
      .select('snapshot_date')
      .eq('platform', filterPlatform)
      .eq('environment', filterEnvironment)
      .order('snapshot_date', { ascending: false })
      .limit(1)

    if (snapshotError) {
      return NextResponse.json(
        { error: `Failed to fetch snapshot freshness: ${snapshotError.message}` },
        { status: 500 }
      )
    }

    const latestSnapshotDate = parseDate(latestSnapshotRows?.[0]?.snapshot_date)
    const daysStale =
      latestSnapshotDate !== null
        ? Math.floor(
            (Date.now() - latestSnapshotDate.getTime()) / (1000 * 60 * 60 * 24)
          )
        : null

    if (!impactRows || impactRows.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No impact scorecards found',
        deltas: [],
        summary: {
          total: 0,
          positive: 0,
          negative: 0,
          neutral: 0,
          avg_roas_did_lift_pct: 0,
        },
        staleness: {
          latest_snapshot_date:
            latestSnapshotDate !== null
              ? latestSnapshotDate.toISOString().slice(0, 10)
              : null,
          days_stale: daysStale,
          is_stale: daysStale === null || daysStale > 2,
        },
      })
    }

    const eventIds = Array.from(
      new Set(impactRows.map((row) => Number(row.publish_event_id)).filter(Number.isFinite))
    )
    const publishEventMap = new Map<number, { published_at: string | null; content_version: number | null }>()
    if (eventIds.length > 0) {
      const { data: publishEvents } = await supabase
        .from('publish_events')
        .select('id,published_at,content_version')
        .in('id', eventIds)

      for (const event of publishEvents || []) {
        publishEventMap.set(Number(event.id), {
          published_at: event.published_at ?? null,
          content_version:
            event.content_version === null || event.content_version === undefined
              ? null
              : Number(event.content_version),
        })
      }
    }

    const scorecards = new Map<number, PerformanceDelta>()

    for (const row of impactRows) {
      const eventId = Number(row.publish_event_id)
      if (!Number.isFinite(eventId)) continue

      if (!scorecards.has(eventId)) {
        const publishEvent = publishEventMap.get(eventId)
        const publishedAtDate = parseDate(publishEvent?.published_at ?? null)
        const daysSincePublish =
          publishedAtDate !== null
            ? Math.floor(
                (Date.now() - publishedAtDate.getTime()) / (1000 * 60 * 60 * 24)
              )
            : null

        scorecards.set(eventId, {
          master_sku: String(row.master_sku),
          platform: String(row.platform),
          environment: String(row.environment),
          publish_event_id: eventId,
          content_version: publishEvent?.content_version ?? null,
          published_at: publishEvent?.published_at ?? null,
          days_since_publish: daysSincePublish,
          label: (row.label as ImpactLabel) || 'neutral',
          confidence: toNumber(row.confidence) ?? 0,
          sample_size_treated: Number(row.sample_size_treated || 0),
          sample_size_control: Number(row.sample_size_control || 0),
          primary_roas_did_lift_pct: null,
          guardrails: {
            impressions: null,
            conversions: null,
            ctr: null,
            cvr: null,
            clicks: null,
            cost: null,
            conversion_value: null,
          },
          metrics: {},
        })
      }

      const card = scorecards.get(eventId)!
      const metricName = String(row.metric_name)
      const metricDelta: MetricDelta = {
        pre_value: toNumber(row.pre_value),
        post_value: toNumber(row.post_value),
        control_pre: toNumber(row.control_pre),
        control_post: toNumber(row.control_post),
        did_lift_pct: toNumber(row.did_lift_pct),
      }

      card.metrics[metricName] = metricDelta

      if (metricName === 'roas') {
        card.primary_roas_did_lift_pct = metricDelta.did_lift_pct
        card.label = (row.label as ImpactLabel) || card.label
        card.confidence = toNumber(row.confidence) ?? card.confidence
        card.sample_size_treated = Number(row.sample_size_treated || card.sample_size_treated)
        card.sample_size_control = Number(row.sample_size_control || card.sample_size_control)
      }

      if (metricName in card.guardrails) {
        card.guardrails[metricName as keyof PerformanceDelta['guardrails']] =
          metricDelta.did_lift_pct
      }
    }

    const deltas = Array.from(scorecards.values()).sort((a, b) => {
      const labelOrder: Record<ImpactLabel, number> = {
        positive: 0,
        neutral: 1,
        negative: 2,
      }
      const byLabel = labelOrder[a.label] - labelOrder[b.label]
      if (byLabel !== 0) return byLabel
      return (b.primary_roas_did_lift_pct ?? -Infinity) - (a.primary_roas_did_lift_pct ?? -Infinity)
    })

    const summary = {
      total: deltas.length,
      positive: deltas.filter((d) => d.label === 'positive').length,
      negative: deltas.filter((d) => d.label === 'negative').length,
      neutral: deltas.filter((d) => d.label === 'neutral').length,
      avg_roas_did_lift_pct:
        deltas.reduce((acc, item) => acc + (item.primary_roas_did_lift_pct ?? 0), 0) /
          (deltas.length || 1),
      significance_breakdown: {
        high: deltas.filter((d) => getSignificance(d.confidence) === 'high').length,
        medium: deltas.filter((d) => getSignificance(d.confidence) === 'medium').length,
        low: deltas.filter((d) => getSignificance(d.confidence) === 'low').length,
      },
    }

    return NextResponse.json({
      success: true,
      deltas,
      summary,
      staleness: {
        latest_snapshot_date:
          latestSnapshotDate !== null
            ? latestSnapshotDate.toISOString().slice(0, 10)
            : null,
        days_stale: daysStale,
        is_stale: daysStale === null || daysStale > 2,
      },
    })
  } catch (error) {
    console.error('Performance delta calculation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
