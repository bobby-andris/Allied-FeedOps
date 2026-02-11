import { NextRequest, NextResponse } from 'next/server'
import { FeedbackPreset } from '@/lib/supabase/types'
import { createAdminClient } from '@/lib/supabase/admin'
import { validateGeneratedContent } from '@/lib/regeneration/prompts'
import { ensureSkuData } from '@/lib/data-collection/ensure-data'

// Python Cloud Run pipeline URL
const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL || 'https://feedops-pipeline-623866089882.us-east1.run.app'

// Feedback preset descriptions
const FEEDBACK_PRESETS: Record<FeedbackPreset, string> = {
  shorter: 'Make this shorter and more concise while keeping key information',
  longer: 'Expand this with more detail and product benefits',
  more_specific: 'Replace vague claims with specific, verifiable details',
  different_angle: 'Take a different approach - emphasize different benefits or features',
  more_keywords: 'Include more relevant search keywords naturally',
  less_promotional: 'Remove promotional language, make it more factual',
  better_hook: 'Improve the opening to be more compelling',
}

interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  feedback?: {
    current_content: string
    user_feedback: string
    feedback_type?: FeedbackPreset
    finish?: string // Optional finish for variant-specific regeneration
  }
  options?: {
    num_candidates?: number
  }
}

type SupabaseErrLike = {
  code?: string | null
  message?: string
  details?: string | null
  hint?: string | null
}

function logSupabaseError(context: string, err: SupabaseErrLike | null | undefined) {
  if (!err) return
  console.error(context, {
    code: err.code ?? null,
    message: err.message ?? 'Unknown error',
    details: err.details ?? null,
    hint: err.hint ?? null,
  })
}

function errorResponse(
  status: number,
  payload: {
    error: string
    code?: string | null
    details?: string | null
    hint?: string | null
    step?: string
    actionable_message?: string | null
    validation_errors?: string[]
  }
) {
  const isProd = process.env.NODE_ENV === 'production'
  if (isProd) {
    return NextResponse.json(
      {
        error: payload.error,
        code: payload.code ?? null,
        step: payload.step ?? null,
        actionable_message: payload.actionable_message ?? null,
        validation_errors: payload.validation_errors ?? [],
      },
      { status }
    )
  }
  return NextResponse.json(payload, { status })
}

function normalizeFinishSentences(raw: unknown): Record<string, string> | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null
  }
  const normalized = Object.fromEntries(
    Object.entries(raw as Record<string, unknown>)
      .filter(([finish, sentence]) => {
        return typeof finish === 'string'
          && finish.trim().length > 0
          && typeof sentence === 'string'
          && sentence.trim().length > 0
      })
      .map(([finish, sentence]) => [finish.trim(), (sentence as string).trim()])
  )
  return Object.keys(normalized).length ? normalized : null
}

export async function POST(request: NextRequest) {
  try {
    const body: RegenerateRequest = await request.json()
    const { master_sku, content_type, platform, mode, feedback } = body

    // Validate required fields
    if (!master_sku || !content_type || !platform || !mode) {
      return errorResponse(400, {
        error: 'Missing required fields: master_sku, content_type, platform, mode',
        code: 'regenerate_missing_required_fields',
        step: 'request_validation',
        actionable_message:
          'Provide master_sku, content_type, platform, and mode, then retry.',
      })
    }

    if (mode === 'with_feedback' && (!feedback?.user_feedback || !feedback?.current_content)) {
      return errorResponse(400, {
        error: 'Feedback mode requires feedback.user_feedback and feedback.current_content',
        code: 'regenerate_feedback_missing_fields',
        step: 'request_validation_feedback',
        actionable_message:
          'Provide both feedback.user_feedback and feedback.current_content for feedback regeneration.',
      })
    }

    const supabase = createAdminClient()

    // Ensure data collection before regeneration (non-blocking, best-effort)
    ensureSkuData(master_sku, supabase)
      .then((result) => {
        if (result.success && result.details) {
          console.log(`Data collection for ${master_sku}:`, result.details)
        }
      })
      .catch((error) => {
        console.warn('Background data collection failed:', error)
      })

    // Quick schema sanity check (migration 004 must be applied)
    const schemaCheck = await supabase
      .from('generated_content')
      .select('id,version,is_current')
      .limit(1)

    if (schemaCheck.error) {
      logSupabaseError('Supabase schema check failed (generated_content)', schemaCheck.error)
      return errorResponse(500, {
        error:
          'Supabase schema is out of date for regeneration (run migration 004_regeneration_history.sql)',
        code: schemaCheck.error.code ?? null,
        details: schemaCheck.error.message ?? null,
        hint: schemaCheck.error.hint ?? null,
        step: 'schema_check_generated_content',
        actionable_message:
          'Apply dashboard Supabase migrations before retrying regeneration.',
      })
    }

    // Get variant data for finish info
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('*')
      .eq('master_sku', master_sku)
      .limit(1)
      .maybeSingle()

    if (variantError) {
      logSupabaseError('Failed to fetch variant data', variantError)
    }

    // Get current content for comparison (needed for history logging)
    const { data: currentContentData, error: currentContentError } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('platform', platform)
      .eq('content_type', content_type)
      .maybeSingle()

    if (currentContentError) {
      logSupabaseError('Failed to fetch current generated content', currentContentError)
    }

    // ==================== CALL PYTHON CLOUD RUN PIPELINE ====================
    // Build feedback text for Python endpoint
    let feedbackText: string | null = null
    if (mode === 'with_feedback' && feedback) {
      const presetText = feedback.feedback_type
        ? FEEDBACK_PRESETS[feedback.feedback_type]
        : null
      feedbackText = presetText
        ? `${presetText}. ${feedback.user_feedback}\n\nCURRENT CONTENT:\n${feedback.current_content}`
        : `${feedback.user_feedback}\n\nCURRENT CONTENT:\n${feedback.current_content}`
    }

    const finishCode = feedback?.finish || variantData?.finish_code || null

    console.log(`Calling Python pipeline for ${master_sku} (${platform}/${content_type}, mode=${mode})`)

    const pipelineResponse = await fetch(`${PIPELINE_URL}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        master_sku,
        content_type,
        platform,
        feedback: feedbackText,
        finish_code: finishCode,
      }),
    })

    if (!pipelineResponse.ok) {
      const errorData = await pipelineResponse.json().catch(() => ({ detail: 'Unknown pipeline error' }))
      console.error(`Pipeline error (${pipelineResponse.status}):`, errorData)
      return errorResponse(pipelineResponse.status === 404 ? 404 : 500, {
        error: errorData.detail || `Pipeline returned ${pipelineResponse.status}`,
        step: 'pipeline_call',
        actionable_message:
          'Check Cloud Run pipeline health and FEEDOPS_PIPELINE_URL configuration, then retry.',
      })
    }

    const pipelineData = await pipelineResponse.json()
    const newContent = pipelineData.content?.trim()
    const pipelineModel = pipelineData.model || 'python-pipeline'
    const pipelinePromptHash = typeof pipelineData.prompt_hash === 'string'
      ? pipelineData.prompt_hash.trim()
      : ''

    if (!newContent) {
      return errorResponse(500, {
        error: 'No content generated from pipeline',
        code: 'pipeline_empty_content',
        step: 'pipeline_response_validation',
        actionable_message:
          'Retry regeneration. If it repeats, inspect Python pipeline logs for empty content responses.',
      })
    }

    if (!pipelinePromptHash) {
      return errorResponse(500, {
        error: 'Pipeline response missing prompt_hash',
        step: 'pipeline_prompt_hash_missing',
        actionable_message:
          'Pipeline response contract is incomplete. Fix prompt_hash persistence in Python API before retrying.',
      })
    }

    console.log(`Pipeline returned content (${newContent.length} chars) via model ${pipelineModel}`)

    // ==================== VALIDATE CONTENT ====================
    const violations = validateGeneratedContent(newContent, platform, content_type)
    if (violations.length > 0) {
      console.warn(`Validation violations for ${master_sku}/${platform}/${content_type}: ${violations.join('; ')}`)
      // Log but don't block — Python pipeline has its own quality checks.
      // Surface these violations to operators so they can take action.
    }

    // ==================== FINISH SENTENCES (Python-generated for Google/Bing descriptions) ====================
    const isVariantDescription = content_type === 'description' && (platform === 'google' || platform === 'bing')
    const finishSentences = isVariantDescription
      ? normalizeFinishSentences(pipelineData.finish_sentences)
      : null

    // ==================== SAVE TO DATABASE ====================
    const currentVersion = currentContentData?.version ?? 0
    let savedContentId: string | null = null
    let nextVersion = currentVersion + 1

    const currentCandidate = typeof currentContentData?.candidate_content === 'string'
      ? currentContentData.candidate_content.trim()
      : null
    const isNoChange = currentCandidate !== null && currentCandidate === newContent

    if (isNoChange) {
      return NextResponse.json({
        success: true,
        content: newContent,
        version: currentVersion,
        mode,
        model: pipelineModel,
        generated_content_id: currentContentData?.id ?? null,
        used_evidence: true,
        used_vision: false,
        finish_sentences_count: finishSentences ? Object.keys(finishSentences).length : 0,
        finish_sentences_saved: false,
        pipeline: 'python',
        state: 'no_change',
        idempotent: true,
        validation_errors: violations,
        actionable_message:
          'Generated content is identical to the current candidate content; no database update was needed.',
      })
    }

    if (currentContentData) {
      const { data: updated, error: updateError } = await supabase
        .from('generated_content')
        .update({
          candidate_content: newContent,
          version: nextVersion,
          is_current: true,
          generation_model: pipelineModel,
          generation_prompt_hash: pipelinePromptHash,
          generation_timestamp: new Date().toISOString(),
        })
        .eq('id', currentContentData.id)
        .select('id')
        .single()

      if (updateError) {
        logSupabaseError('Failed to update generated_content', updateError)
        return errorResponse(500, {
          error: 'Failed to save generated content',
          code: updateError.code ?? null,
          details: updateError.message ?? null,
          hint: updateError.hint ?? null,
          step: 'generated_content_update',
          actionable_message:
            'Review Supabase write permissions/schema for generated_content and retry regeneration.',
        })
      }

      savedContentId = updated?.id ?? null
    } else {
      nextVersion = 1
      const { data: inserted, error: insertError } = await supabase
        .from('generated_content')
        .insert({
          master_sku,
          platform,
          content_type,
          candidate_content: newContent,
          baseline_content: null,
          version: nextVersion,
          is_current: true,
          generation_model: pipelineModel,
          generation_prompt_hash: pipelinePromptHash,
          generation_timestamp: new Date().toISOString(),
        })
        .select('id')
        .single()

      if (insertError) {
        logSupabaseError('Failed to insert generated_content', insertError)
        return errorResponse(500, {
          error: 'Failed to save generated content',
          code: insertError.code ?? null,
          details: insertError.message ?? null,
          hint: insertError.hint ?? null,
          step: 'generated_content_insert',
          actionable_message:
            'Review Supabase insert permissions/schema for generated_content and retry regeneration.',
        })
      }

      savedContentId = inserted?.id ?? null
    }

    // Python pipeline already logs history authoritatively (including prompt hash + model metadata).
    // Do not insert a second dashboard-side row; duplicate records break traceability.

    // Save finish_sentences to separate table (for Google/Bing descriptions only)
    let finishSentencesSaved = false
    if (finishSentences && Object.keys(finishSentences).length > 0 && (platform === 'google' || platform === 'bing')) {
      const { error: finishError } = await supabase
        .from('variant_finish_sentences')
        .upsert(
          {
            master_sku,
            platform,
            finish_sentences: finishSentences,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'master_sku,platform' }
        )

      if (finishError) {
        logSupabaseError('Failed to save finish sentences', finishError)
        console.warn('Finish sentences not saved, but content was saved successfully')
      } else {
        finishSentencesSaved = true
        console.log(`Saved ${Object.keys(finishSentences).length} finish sentences for ${master_sku}/${platform}`)
      }
    }

    return NextResponse.json({
      success: true,
      content: newContent,
      version: nextVersion,
      mode,
      model: pipelineModel,
      generated_content_id: savedContentId,
      used_evidence: true, // Python pipeline always uses evidence
      used_vision: false, // Vision handled by Python pipeline internally
      finish_sentences_count: finishSentences ? Object.keys(finishSentences).length : 0,
      finish_sentences_saved: finishSentencesSaved,
      pipeline: 'python', // Indicate content came from Python pipeline
      state: 'completed',
      idempotent: false,
      validation_errors: violations,
      actionable_message:
        violations.length > 0
          ? 'Validation warnings detected. Review violations before approving/publishing this content.'
          : null,
    })
  } catch (error) {
    console.error('Regeneration error:', error)
    return errorResponse(500, {
      error: error instanceof Error ? error.message : 'Internal server error',
      step: 'unhandled_exception',
      actionable_message:
        'Unexpected regeneration failure. Retry once; if it persists, inspect API logs for this request.',
    })
  }
}
