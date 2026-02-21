import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { SupabaseClient } from '@supabase/supabase-js'

type BottleneckClassification =
  | 'coverage_gap'
  | 'code_path_gap'
  | 'propagation_failure'
  | 'query_relevance'
  | 'auction_bid'

interface ClassificationResult {
  master_sku: string
  classification: BottleneckClassification
  confidence: number
  evidence: Record<string, unknown>
  is_override: boolean
}

interface ClassifySignals {
  has_content: boolean
  has_publish_event: boolean
  has_zero_impressions_post_publish: boolean | null
  keyword_gap_count: number
}

async function classifySkuSignals(
  masterSku: string,
  supabase: SupabaseClient
): Promise<{ classification: BottleneckClassification; confidence: number; evidence: Record<string, unknown> }> {
  const signals: ClassifySignals = {
    has_content: false,
    has_publish_event: false,
    has_zero_impressions_post_publish: null,
    keyword_gap_count: 0,
  }

  // Step 1: Check coverage_gap — no generated_content row for this master_sku
  const { data: contentRows, error: contentError } = await supabase
    .from('generated_content')
    .select('id')
    .eq('master_sku', masterSku)
    .limit(1)

  if (contentError) {
    console.error(`[bottleneck/classify] generated_content query error for ${masterSku}:`, contentError.message)
  }

  signals.has_content = !!(contentRows && contentRows.length > 0)

  if (!signals.has_content) {
    return {
      classification: 'coverage_gap',
      confidence: 0.95,
      evidence: {
        check: 'generated_content',
        result: 'no_rows',
        signal: 'No content has been generated for this SKU',
        signals,
      },
    }
  }

  // Step 2: Check code_path_gap — content exists but no successful publish_event
  const { data: publishRows, error: publishError } = await supabase
    .from('publish_events')
    .select('id')
    .eq('master_sku', masterSku)
    .eq('status', 'success')
    .limit(1)

  if (publishError) {
    console.error(`[bottleneck/classify] publish_events query error for ${masterSku}:`, publishError.message)
  }

  signals.has_publish_event = !!(publishRows && publishRows.length > 0)

  if (!signals.has_publish_event) {
    return {
      classification: 'code_path_gap',
      confidence: 0.9,
      evidence: {
        check: 'publish_events',
        result: 'no_success_rows',
        signal: 'Content exists but has never been successfully published',
        signals,
      },
    }
  }

  // Step 3: Check propagation_failure — published but 0 impressions after 7 days
  const { data: snapshotRows, error: snapshotError } = await supabase
    .from('performance_snapshots')
    .select('impressions, days_since_publish')
    .eq('master_sku', masterSku)
    .gt('days_since_publish', 7)
    .order('snapshot_date', { ascending: false })
    .limit(1)

  if (snapshotError) {
    console.error(`[bottleneck/classify] performance_snapshots query error for ${masterSku}:`, snapshotError.message)
  }

  if (snapshotRows && snapshotRows.length > 0) {
    signals.has_zero_impressions_post_publish = snapshotRows[0].impressions === 0

    if (signals.has_zero_impressions_post_publish) {
      return {
        classification: 'propagation_failure',
        confidence: 0.85,
        evidence: {
          check: 'performance_snapshots',
          result: 'zero_impressions_post_7_days',
          signal: 'Published but no impressions after 7+ days — content may not have reached GMC',
          days_since_publish: snapshotRows[0].days_since_publish,
          impressions: snapshotRows[0].impressions,
          signals,
        },
      }
    }
  }

  // Step 4: Check query_relevance — keyword gaps with high volume
  const { data: keywordGapRows, error: keywordError } = await supabase
    .from('keyword_coverage_master')
    .select('keyword, in_title, query_volume')
    .eq('master_sku', masterSku)
    .eq('in_title', false)
    .gt('query_volume', 100)

  if (keywordError) {
    console.error(`[bottleneck/classify] keyword_coverage_master query error for ${masterSku}:`, keywordError.message)
  }

  signals.keyword_gap_count = keywordGapRows?.length ?? 0

  if (signals.keyword_gap_count > 2) {
    const topGaps = (keywordGapRows ?? []).slice(0, 5).map((r) => ({
      keyword: r.keyword,
      query_volume: r.query_volume,
    }))

    return {
      classification: 'query_relevance',
      confidence: 0.75,
      evidence: {
        check: 'keyword_coverage_master',
        result: `${signals.keyword_gap_count}_keyword_gaps`,
        signal: `${signals.keyword_gap_count} high-volume keywords (>100 impressions) missing from title`,
        top_gaps: topGaps,
        signals,
      },
    }
  }

  // Step 5: Default fallback — auction_bid
  return {
    classification: 'auction_bid',
    confidence: 0.6,
    evidence: {
      check: 'fallback',
      result: 'no_other_signal_matched',
      signal: 'Impressions exist but IS may be lost to rank — check campaign bids and quality scores',
      signals,
    },
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const masterSku = searchParams.get('master_sku')
    const overrideBy = searchParams.get('override_by')
    const overrideNote = searchParams.get('override_note')
    const overrideClassification = searchParams.get('override_classification') as BottleneckClassification | null
    const isBatch = searchParams.get('batch') === 'true'

    // --- Batch mode: classify all SKUs with generated_content ---
    if (isBatch) {
      const { data: allContentRows, error: allContentError } = await supabase
        .from('generated_content')
        .select('master_sku')

      if (allContentError) {
        return NextResponse.json(
          { error: `Failed to fetch SKUs for batch classification: ${allContentError.message}` },
          { status: 500 }
        )
      }

      const uniqueSkus = Array.from(new Set((allContentRows ?? []).map((r) => r.master_sku as string)))
      const results: ClassificationResult[] = []
      const errors: { master_sku: string; error: string }[] = []

      // Process in chunks to avoid overwhelming the DB
      const CHUNK_SIZE = 20
      for (let i = 0; i < uniqueSkus.length; i += CHUNK_SIZE) {
        const chunk = uniqueSkus.slice(i, i + CHUNK_SIZE)

        await Promise.all(
          chunk.map(async (sku) => {
            try {
              const classified = await classifySkuSignals(sku, supabase)
              results.push({
                master_sku: sku,
                classification: classified.classification,
                confidence: classified.confidence,
                evidence: classified.evidence,
                is_override: false,
              })
            } catch (err) {
              errors.push({
                master_sku: sku,
                error: err instanceof Error ? err.message : 'Unknown error',
              })
            }
          })
        )
      }

      // Batch upsert results — upsert on master_sku where is_override=false
      // We delete existing auto-classifications and re-insert
      if (results.length > 0) {
        const upsertRows = results.map((r) => ({
          master_sku: r.master_sku,
          classification: r.classification,
          confidence: r.confidence,
          evidence: r.evidence,
          is_override: false,
          classified_at: new Date().toISOString(),
        }))

        // Delete existing auto-classifications for these SKUs
        const skuList = results.map((r) => r.master_sku)
        await supabase
          .from('sku_bottleneck_classifications')
          .delete()
          .in('master_sku', skuList)
          .eq('is_override', false)

        const { error: upsertError } = await supabase
          .from('sku_bottleneck_classifications')
          .insert(upsertRows)

        if (upsertError) {
          return NextResponse.json(
            { error: `Batch classification failed during upsert: ${upsertError.message}` },
            { status: 500 }
          )
        }
      }

      return NextResponse.json({
        success: true,
        batch: true,
        classified_count: results.length,
        error_count: errors.length,
        errors: errors.length > 0 ? errors : undefined,
        classifications: results,
      })
    }

    // --- Single SKU mode ---
    if (!masterSku) {
      return NextResponse.json(
        { error: 'master_sku query parameter is required (or use batch=true for bulk classification)' },
        { status: 400 }
      )
    }

    // Manual override path
    if (overrideClassification) {
      if (!overrideBy) {
        return NextResponse.json(
          { error: 'override_by is required when providing override_classification' },
          { status: 400 }
        )
      }

      const overrideRow = {
        master_sku: masterSku,
        classification: overrideClassification,
        confidence: 1.0,
        evidence: {
          override: true,
          override_by: overrideBy,
          override_note: overrideNote ?? null,
          overridden_at: new Date().toISOString(),
        },
        override_by: overrideBy,
        override_note: overrideNote ?? null,
        is_override: true,
        classified_at: new Date().toISOString(),
      }

      const { error: overrideError } = await supabase
        .from('sku_bottleneck_classifications')
        .insert(overrideRow)

      if (overrideError) {
        return NextResponse.json(
          { error: `Failed to save manual override: ${overrideError.message}` },
          { status: 500 }
        )
      }

      return NextResponse.json({
        master_sku: masterSku,
        classification: overrideClassification,
        confidence: 1.0,
        evidence: overrideRow.evidence,
        is_override: true,
      } satisfies ClassificationResult)
    }

    // Auto-classification decision tree
    const classified = await classifySkuSignals(masterSku, supabase)

    // Upsert: delete old auto-classification, insert new one
    await supabase
      .from('sku_bottleneck_classifications')
      .delete()
      .eq('master_sku', masterSku)
      .eq('is_override', false)

    const { error: insertError } = await supabase
      .from('sku_bottleneck_classifications')
      .insert({
        master_sku: masterSku,
        classification: classified.classification,
        confidence: classified.confidence,
        evidence: classified.evidence,
        is_override: false,
        classified_at: new Date().toISOString(),
      })

    if (insertError) {
      return NextResponse.json(
        { error: `Failed to save classification: ${insertError.message}` },
        { status: 500 }
      )
    }

    return NextResponse.json({
      master_sku: masterSku,
      classification: classified.classification,
      confidence: classified.confidence,
      evidence: classified.evidence,
      is_override: false,
    } satisfies ClassificationResult)
  } catch (error) {
    console.error('[bottleneck/classify] Unexpected error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
