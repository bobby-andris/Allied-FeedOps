import { NextRequest, NextResponse } from 'next/server'

import { createClient } from '@/lib/supabase/server'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'
import {
  validateManualDescriptionForPlatform,
  type ManualDescriptionPlatform,
} from '@/lib/review/manual-description'

interface ManualDescriptionRequest {
  master_sku: string
  platform: ManualDescriptionPlatform
  description: string
}

interface GeneratedContentRow {
  id: string
  candidate_content: string | null
  version: number | null
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<ManualDescriptionRequest>
    const masterSku = body.master_sku?.trim()
    const platform = body.platform
    const description = body.description ?? ''

    if (!masterSku || !platform || typeof description !== 'string') {
      return NextResponse.json(
        {
          error: 'master_sku, platform, and description are required.',
          code: 'manual_description_missing_required_fields',
        },
        { status: 400 },
      )
    }

    if (platform !== 'google' && platform !== 'bing' && platform !== 'shopify') {
      return NextResponse.json(
        {
          error: 'Manual description editing supports google, bing, or shopify.',
          code: 'manual_description_invalid_platform',
        },
        { status: 400 },
      )
    }

    const validation = validateManualDescriptionForPlatform(description, platform)
    if (!validation.ok) {
      return NextResponse.json(
        {
          error: 'Manual description is invalid.',
          code: 'manual_description_validation_failed',
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
      .eq('content_type', 'description')
      .maybeSingle<GeneratedContentRow>()

    if (existingError) {
      return NextResponse.json(
        {
          error: `Failed to load current description: ${existingError.message}`,
          code: existingError.code || 'manual_description_lookup_failed',
        },
        { status: 500 },
      )
    }

    if (!existingRow) {
      return NextResponse.json(
        {
          error: `No ${platform} description content found for ${canonicalMasterSku}. Generate description content first.`,
          code: 'manual_description_not_found',
        },
        { status: 404 },
      )
    }

    const normalizedCurrent = (existingRow.candidate_content || '').trim()
    if (normalizedCurrent === validation.normalizedDescription) {
      return NextResponse.json({
        success: true,
        state: 'no_change',
        description: validation.normalizedDescription,
      })
    }

    const now = new Date().toISOString()
    const nextVersion = (existingRow.version || 0) + 1

    const { error: updateError } = await supabase
      .from('generated_content')
      .update({
        candidate_content: validation.normalizedDescription,
        version: nextVersion,
        generation_model: 'manual_description_override',
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
          error: `Failed to save description override: ${updateError.message}`,
          code: updateError.code || 'manual_description_save_failed',
        },
        { status: 500 },
      )
    }

    // Best-effort audit trail; failure should not block operator save.
    await supabase.from('regeneration_history').insert({
      master_sku: canonicalMasterSku,
      content_type: 'description',
      platform,
      mode: 'simple',
      feedback_text:
        platform === 'shopify'
          ? 'Manual Shopify description edit applied.'
          : 'Manual base description edit applied to variant template.',
      previous_content: existingRow.candidate_content,
      new_content: validation.normalizedDescription,
      model_version: 'manual_description_override',
      generated_content_id: existingRow.id,
      created_at: now,
    })

    return NextResponse.json({
      success: true,
      state: 'updated',
      description: validation.normalizedDescription,
      version: nextVersion,
    })
  } catch (error) {
    console.error('Manual description save error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
        code: 'manual_description_unhandled_exception',
      },
      { status: 500 },
    )
  }
}
