import { NextRequest, NextResponse } from 'next/server'
import { randomUUID } from 'crypto'

import { createClient } from '@/lib/supabase/server'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'
import { validateManualTitleForPlatform, type ManualTitlePlatform } from '@/lib/review/manual-title'

interface ManualTitleRequest {
  master_sku: string
  platform: ManualTitlePlatform
  title: string
}

interface GeneratedContentRow {
  id: string
  candidate_content: string | null
  version: number | null
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<ManualTitleRequest>
    const masterSku = body.master_sku?.trim()
    const platform = body.platform
    const title = body.title ?? ''

    if (!masterSku || !platform || typeof title !== 'string') {
      return NextResponse.json(
        {
          error: 'master_sku, platform, and title are required.',
          code: 'manual_title_missing_required_fields',
        },
        { status: 400 },
      )
    }

    if (platform !== 'google' && platform !== 'bing' && platform !== 'shopify') {
      return NextResponse.json(
        {
          error: 'Manual title editing supports google, bing, or shopify.',
          code: 'manual_title_invalid_platform',
        },
        { status: 400 },
      )
    }

    const validation = validateManualTitleForPlatform(title, platform)
    if (!validation.ok) {
      return NextResponse.json(
        {
          error: 'Manual title is invalid.',
          code: 'manual_title_validation_failed',
          validation_errors: validation.errors,
        },
        { status: 400 },
      )
    }

    const supabase = await createClient()
    const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, masterSku)

    const { data: existingRow, error: existingError } = await supabase
      .from('generated_content')
      .select('id, candidate_content, version')
      .eq('master_sku', canonicalMasterSku)
      .eq('platform', platform)
      .eq('content_type', 'title')
      .maybeSingle<GeneratedContentRow>()

    if (existingError) {
      return NextResponse.json(
        {
          error: `Failed to load current title: ${existingError.message}`,
          code: existingError.code || 'manual_title_lookup_failed',
        },
        { status: 500 },
      )
    }

    if (!existingRow) {
      return NextResponse.json(
        {
          error: `No ${platform} title content found for ${canonicalMasterSku}. Generate title content first.`,
          code: 'manual_title_not_found',
        },
        { status: 404 },
      )
    }

    const normalizedCurrent = (existingRow.candidate_content || '').trim()
    if (normalizedCurrent === validation.normalizedTitle) {
      return NextResponse.json({
        success: true,
        state: 'no_change',
        title: validation.normalizedTitle,
      })
    }

    const now = new Date().toISOString()
    const nextVersion = (existingRow.version || 0) + 1
    const requestId = request.headers.get('x-request-id')?.trim() || randomUUID()

    const { error: updateError } = await supabase
      .from('generated_content')
      .update({
        candidate_content: validation.normalizedTitle,
        version: nextVersion,
        generation_model: 'manual_title_override',
        generation_timestamp: now,
        approved_content: null,
        approved_at: null,
        approved_version: null,
        updated_at: now,
      })
      .eq('id', existingRow.id)

    if (updateError) {
      return NextResponse.json(
        {
          error: `Failed to save title override: ${updateError.message}`,
          code: updateError.code || 'manual_title_save_failed',
        },
        { status: 500 },
      )
    }

    // Best-effort audit trail; failure should not block operator save.
    await supabase.from('regeneration_history').insert({
      master_sku: canonicalMasterSku,
      content_type: 'title',
      platform,
      mode: 'manual_title_override',
      feedback_text:
        platform === 'shopify'
          ? 'Manual Shopify title edit applied.'
          : 'Manual base title edit applied to variant template.',
      previous_content: existingRow.candidate_content,
      new_content: validation.normalizedTitle,
      model_version: 'manual_title_override',
      generated_content_id: existingRow.id,
      request_id: requestId,
      result_state: 'completed',
      result_version: nextVersion,
      result_idempotent: false,
      idempotency_key: `manual-title:${existingRow.id}:${nextVersion}`,
      provider_attempt_count: 0,
      parse_retry_count: 0,
      latency_ms: 0,
      created_at: now,
    })

    return NextResponse.json({
      success: true,
      state: 'updated',
      title: validation.normalizedTitle,
      version: nextVersion,
    })
  } catch (error) {
    console.error('Manual title save error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
        code: 'manual_title_unhandled_exception',
      },
      { status: 500 },
    )
  }
}
