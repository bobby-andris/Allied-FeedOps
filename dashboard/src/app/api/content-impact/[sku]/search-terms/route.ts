import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { getSkuCandidates } from '@/lib/sku-utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SearchTermDelta {
  search_term: string
  pre_impressions: number
  post_impressions: number
  impression_delta: number
  pre_clicks: number
  post_clicks: number
  click_delta: number
  is_new: boolean
}

interface SearchTermsResponse {
  gained: SearchTermDelta[]
  lost: SearchTermDelta[]
  pre_snapshot_date: string | null
  post_snapshot_date: string | null
}

// ---------------------------------------------------------------------------
// SKU resolver
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

    if (!eventIdParam) {
      return NextResponse.json(
        { error: 'event_id query parameter is required' },
        { status: 400 }
      )
    }

    // Resolve SKU
    const masterSku = await resolveSkuFromPublishEvents(supabase, urlSku)
    if (!masterSku) {
      return NextResponse.json(
        { error: `No publish events found for SKU: ${urlSku}` },
        { status: 404 }
      )
    }

    // 1. Get the publish event to determine published_at date
    const { data: publishEvent, error: publishError } = await supabase
      .from('publish_events')
      .select('id, published_at')
      .eq('id', parseInt(eventIdParam))
      .single()

    if (publishError || !publishEvent) {
      return NextResponse.json(
        { error: `Publish event ${eventIdParam} not found` },
        { status: 404 }
      )
    }

    const publishedAt = publishEvent.published_at
    const publishDate = publishedAt.split('T')[0] // YYYY-MM-DD

    // 2. Query pre-publish snapshots (closest snapshot before publish date)
    const { data: preSnapshots } = await supabase
      .from('search_query_snapshots')
      .select('query_text, impressions, clicks, snapshot_date')
      .eq('master_sku', masterSku)
      .lt('snapshot_date', publishDate)
      .order('snapshot_date', { ascending: false })

    // 3. Query post-publish snapshots (closest snapshot 7-14 days after)
    const { data: postSnapshots } = await supabase
      .from('search_query_snapshots')
      .select('query_text, impressions, clicks, snapshot_date')
      .eq('master_sku', masterSku)
      .gt('snapshot_date', publishDate)
      .order('snapshot_date', { ascending: true })

    // Aggregate pre-publish: use the latest pre-publish snapshot per query
    const preMap = new Map<string, { impressions: number; clicks: number }>()
    let preSnapshotDate: string | null = null
    for (const snap of preSnapshots || []) {
      if (!preSnapshotDate) preSnapshotDate = snap.snapshot_date
      if (!preMap.has(snap.query_text)) {
        preMap.set(snap.query_text, {
          impressions: snap.impressions ?? 0,
          clicks: snap.clicks ?? 0,
        })
      }
    }

    // Aggregate post-publish: use the earliest post-publish snapshot per query
    const postMap = new Map<string, { impressions: number; clicks: number }>()
    let postSnapshotDate: string | null = null
    for (const snap of postSnapshots || []) {
      if (!postSnapshotDate) postSnapshotDate = snap.snapshot_date
      if (!postMap.has(snap.query_text)) {
        postMap.set(snap.query_text, {
          impressions: snap.impressions ?? 0,
          clicks: snap.clicks ?? 0,
        })
      }
    }

    // 4. Compare: compute deltas for all terms
    const allTerms = new Set([...preMap.keys(), ...postMap.keys()])
    const gained: SearchTermDelta[] = []
    const lost: SearchTermDelta[] = []

    for (const term of allTerms) {
      const pre = preMap.get(term)
      const post = postMap.get(term)

      const preImpressions = pre?.impressions ?? 0
      const postImpressions = post?.impressions ?? 0
      const preClicks = pre?.clicks ?? 0
      const postClicks = post?.clicks ?? 0

      const impressionDelta = postImpressions - preImpressions
      const clickDelta = postClicks - preClicks
      const isNew = preImpressions === 0 && postImpressions > 0

      const delta: SearchTermDelta = {
        search_term: term,
        pre_impressions: preImpressions,
        post_impressions: postImpressions,
        impression_delta: impressionDelta,
        pre_clicks: preClicks,
        post_clicks: postClicks,
        click_delta: clickDelta,
        is_new: isNew,
      }

      if (impressionDelta > 0) {
        gained.push(delta)
      } else if (impressionDelta < 0) {
        lost.push(delta)
      }
      // Terms with zero delta are excluded from both lists
    }

    // 5. Sort: gained by impression_delta DESC, lost by impression_delta ASC
    gained.sort((a, b) => b.impression_delta - a.impression_delta)
    lost.sort((a, b) => a.impression_delta - b.impression_delta)

    const response: SearchTermsResponse = {
      gained,
      lost,
      pre_snapshot_date: preSnapshotDate,
      post_snapshot_date: postSnapshotDate,
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Content Impact Search Terms API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
