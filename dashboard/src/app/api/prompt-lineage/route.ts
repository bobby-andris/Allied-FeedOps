import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

interface GenerationMetadata {
  generated_at: string | null
  model_version: string | null
  feature_flags_active: Record<string, unknown> | null
  quality_score: number | null
  tokens_used: number | null
  latency_ms: number | null
}

interface LineageResponse {
  publish_event_id: number
  published_at: string
  prompt_hash: string
  prompt_alias: string | null
  prompt_notes: string | null
  generation: GenerationMetadata | null
}

interface CompareGenerationEntry {
  prompt_hash: string
  prompt_alias: string | null
  prompt_notes: string | null
  generated_at: string | null
  model_version: string | null
  feature_flags_active: Record<string, unknown> | null
  quality_score: number | null
  tokens_used: number | null
  latency_ms: number | null
  new_content: string | null
}

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const masterSku = searchParams.get('master_sku')
    const platform = searchParams.get('platform') ?? 'google'
    const compareMode = searchParams.get('compare') === 'true'
    const hashA = searchParams.get('hash_a')
    const hashB = searchParams.get('hash_b')

    if (!masterSku) {
      return NextResponse.json(
        { error: 'master_sku query parameter is required' },
        { status: 400 }
      )
    }

    // --- Compare mode: side-by-side comparison of two prompt hashes ---
    if (compareMode) {
      if (!hashA || !hashB) {
        return NextResponse.json(
          { error: 'compare mode requires both hash_a and hash_b query parameters' },
          { status: 400 }
        )
      }

      const { data: historyRows, error: historyError } = await supabase
        .from('regeneration_history')
        .select(
          'created_at, prompt_hash, model_version, feature_flags_active, quality_score_after, tokens_used, latency_ms, new_content'
        )
        .eq('master_sku', masterSku)
        .eq('platform', platform)
        .in('prompt_hash', [hashA, hashB])
        .order('created_at', { ascending: false })

      if (historyError) {
        return NextResponse.json(
          { error: `Failed to fetch generation history: ${historyError.message}` },
          { status: 500 }
        )
      }

      // Get aliases for both hashes
      const { data: aliasRows, error: aliasError } = await supabase
        .from('prompt_version_aliases')
        .select('prompt_hash, alias, notes')
        .in('prompt_hash', [hashA, hashB])

      if (aliasError) {
        // Non-fatal: aliases are optional
        console.warn('[prompt-lineage] Failed to fetch aliases for compare mode:', aliasError.message)
      }

      const aliasMap = new Map<string, { alias: string | null; notes: string | null }>()
      for (const row of aliasRows ?? []) {
        aliasMap.set(row.prompt_hash as string, {
          alias: row.alias as string | null,
          notes: row.notes as string | null,
        })
      }

      // Deduplicate: keep latest row per prompt_hash
      const seenHashes = new Set<string>()
      const compareEntries: CompareGenerationEntry[] = []

      for (const row of historyRows ?? []) {
        const hash = row.prompt_hash as string
        if (seenHashes.has(hash)) continue
        seenHashes.add(hash)

        const aliasInfo = aliasMap.get(hash)
        compareEntries.push({
          prompt_hash: hash,
          prompt_alias: aliasInfo?.alias ?? null,
          prompt_notes: aliasInfo?.notes ?? null,
          generated_at: row.created_at as string | null,
          model_version: row.model_version as string | null,
          feature_flags_active: (row.feature_flags_active as Record<string, unknown>) ?? null,
          quality_score: row.quality_score_after != null ? Number(row.quality_score_after) : null,
          tokens_used: row.tokens_used != null ? Number(row.tokens_used) : null,
          latency_ms: row.latency_ms != null ? Number(row.latency_ms) : null,
          new_content: row.new_content as string | null,
        })
      }

      return NextResponse.json({
        compare: true,
        master_sku: masterSku,
        platform,
        hash_a: hashA,
        hash_b: hashB,
        generations: compareEntries,
      })
    }

    // --- Standard mode: get lineage for latest published content ---

    // Step 1: Get the latest successful publish event for this SKU + platform
    const { data: publishEvent, error: publishError } = await supabase
      .from('publish_events')
      .select('id, published_at, prompt_hash, content_version')
      .eq('master_sku', masterSku)
      .eq('platform', platform)
      .eq('status', 'success')
      .order('published_at', { ascending: false })
      .limit(1)
      .single()

    if (publishError) {
      // If PGRST116 (no rows), return a not-found response
      if (publishError.code === 'PGRST116') {
        return NextResponse.json({
          lineage: null,
          note: `No successful publish events found for ${masterSku} on ${platform}`,
        })
      }
      return NextResponse.json(
        { error: `Failed to fetch publish event: ${publishError.message}` },
        { status: 500 }
      )
    }

    // Step 2: Handle null prompt_hash (historical data before Phase 19 lineage tracking)
    if (!publishEvent.prompt_hash) {
      return NextResponse.json({
        lineage: null,
        note: 'Prompt hash not recorded for this publish event — lineage tracking available for content published after Phase 19',
        publish_event_id: publishEvent.id,
        published_at: publishEvent.published_at,
      })
    }

    // Step 3: Look up human-readable alias for this prompt hash
    const { data: aliasRow, error: aliasError } = await supabase
      .from('prompt_version_aliases')
      .select('alias, notes')
      .eq('prompt_hash', publishEvent.prompt_hash)
      .maybeSingle()

    if (aliasError) {
      // Non-fatal: aliases are optional
      console.warn('[prompt-lineage] Failed to fetch prompt alias:', aliasError.message)
    }

    // Step 4: Get generation metadata from regeneration_history
    const { data: historyRow, error: historyError } = await supabase
      .from('regeneration_history')
      .select(
        'created_at, model_version, feature_flags_active, quality_score_after, tokens_used, latency_ms'
      )
      .eq('master_sku', masterSku)
      .eq('platform', platform)
      .eq('prompt_hash', publishEvent.prompt_hash)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (historyError) {
      // Non-fatal: generation history may not always be available
      console.warn('[prompt-lineage] Failed to fetch regeneration history:', historyError.message)
    }

    const generation: GenerationMetadata | null = historyRow
      ? {
          generated_at: historyRow.created_at as string | null,
          model_version: historyRow.model_version as string | null,
          feature_flags_active: (historyRow.feature_flags_active as Record<string, unknown>) ?? null,
          quality_score:
            historyRow.quality_score_after != null ? Number(historyRow.quality_score_after) : null,
          tokens_used: historyRow.tokens_used != null ? Number(historyRow.tokens_used) : null,
          latency_ms: historyRow.latency_ms != null ? Number(historyRow.latency_ms) : null,
        }
      : null

    const lineage: LineageResponse = {
      publish_event_id: publishEvent.id as number,
      published_at: publishEvent.published_at as string,
      prompt_hash: publishEvent.prompt_hash as string,
      prompt_alias: aliasRow?.alias ?? null,
      prompt_notes: aliasRow?.notes ?? null,
      generation,
    }

    return NextResponse.json(lineage)
  } catch (error) {
    console.error('[prompt-lineage] Unexpected error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
