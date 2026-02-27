import { NextRequest, NextResponse } from 'next/server'
import { randomUUID } from 'crypto'
import { FeedbackPreset } from '@/lib/supabase/types'
import { createAdminClient } from '@/lib/supabase/admin'
import { validateGeneratedContent } from '@/lib/regeneration/prompts'
import { ensureSkuData } from '@/lib/data-collection/ensure-data'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'
import { enforcePilotCanaryForSkus } from '@/lib/rollout/pilot-canary'

// Python Cloud Run pipeline URL
const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

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

type ToneStyle = 'formal' | 'conversational' | 'technical' | 'aspirational'
type EmphasisOption = 'finish' | 'dimensions' | 'use_case' | 'compatibility' | 'luxury'
type LengthPreference = 'shorter' | 'standard' | 'longer'

interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  async_mode?: boolean
  feedback?: {
    current_content: string
    user_feedback: string
    feedback_type?: FeedbackPreset
    finish?: string // Optional finish for variant-specific regeneration
  }
  options?: {
    num_candidates?: number
  }
  // Structured feedback fields (FIX-01: persistent corrections)
  tone_style?: ToneStyle
  emphasis?: EmphasisOption[]
  length_preference?: LengthPreference
  save_as_correction?: boolean
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
    const asyncMode = body.async_mode === true

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

    if (!PIPELINE_URL) {
      return errorResponse(503, {
        error: 'Content generation pipeline is not configured (FEEDOPS_PIPELINE_URL not set)',
        code: 'regenerate_pipeline_not_configured',
        step: 'pipeline_config',
        actionable_message:
          'Set FEEDOPS_PIPELINE_URL for this environment before retrying regeneration.',
      })
    }

    const supabase = createAdminClient()
    const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)
    const canaryGuard = enforcePilotCanaryForSkus([canonicalMasterSku], 'regenerate')
    if (!canaryGuard.allowed) {
      return canaryGuard.response!
    }

    // Ensure data collection before regeneration (non-blocking, best-effort)
    ensureSkuData(canonicalMasterSku, supabase)
      .then((result) => {
        if (result.success && result.details) {
          console.log(`Data collection for ${canonicalMasterSku}:`, result.details)
        }
      })
      .catch((error) => {
        console.warn('Background data collection failed:', error)
      })

    // Get variant data for finish info
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('*')
      .eq('master_sku', canonicalMasterSku)
      .limit(1)
      .maybeSingle()

    if (variantError) {
      logSupabaseError('Failed to fetch variant data', variantError)
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

    console.log(`Calling Python pipeline for ${canonicalMasterSku} (${platform}/${content_type}, mode=${mode})`)

    // Extract structured feedback fields forwarded from client (FIX-01)
    const toneStyle = body.tone_style
    const emphasis = body.emphasis
    const lengthPreference = body.length_preference
    const saveAsCorrection = Boolean(body.save_as_correction)

    const pipelinePayload: Record<string, unknown> = {
      master_sku: canonicalMasterSku,
      content_type,
      platform,
      feedback: feedbackText,
      finish_code: finishCode,
      async_mode: asyncMode,
      // Structured feedback (FIX-01): only include fields that are set
      ...(toneStyle ? { tone_style: toneStyle } : {}),
      ...(emphasis && emphasis.length > 0 ? { emphasis } : {}),
      ...(lengthPreference ? { length_preference: lengthPreference } : {}),
      ...(saveAsCorrection ? { save_as_correction: true } : {}),
    }
    const requestId = request.headers.get('x-request-id') ?? randomUUID()

    const pipelineResponse = await fetch(`${PIPELINE_URL}/regenerate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(pipelinePayload),
    })

    if (!pipelineResponse.ok) {
      const errorData = await pipelineResponse.json().catch(() => ({ detail: 'Unknown pipeline error' }))
      console.error(`Pipeline error (${pipelineResponse.status}):`, errorData)
      const detail = errorData?.detail
      const detailMessage = typeof detail === 'string'
        ? detail
        : typeof detail?.message === 'string'
          ? detail.message
          : `Pipeline returned ${pipelineResponse.status}`
      const detailCode = typeof detail === 'object' && detail && 'code' in detail
        ? String((detail as Record<string, unknown>).code)
        : null
      return errorResponse(pipelineResponse.status === 404 ? 404 : 500, {
        error: detailMessage,
        code: detailCode,
        step: 'pipeline_call',
        actionable_message:
          'Check Cloud Run pipeline health and FEEDOPS_PIPELINE_URL configuration, then retry.',
      })
    }

    const pipelineData = await pipelineResponse.json()

    if (asyncMode) {
      const jobId = typeof pipelineData.job_id === 'string' ? pipelineData.job_id : null
      const jobStatus = typeof pipelineData.status === 'string' ? pipelineData.status : null
      const pipelineRequestId = typeof pipelineData.request_id === 'string'
        ? pipelineData.request_id
        : requestId
      const deduplicated = pipelineData.deduplicated === true

      if (!jobId || !jobStatus) {
        return errorResponse(500, {
          error: 'Pipeline async response missing job_id/status',
          code: 'pipeline_contract_missing_regenerate_job_metadata',
          step: 'pipeline_response_validation_async',
          actionable_message:
            'Cloud Run regenerate async contract drift detected. Ensure Python returns job_id and status.',
        })
      }

      return NextResponse.json({
        success: true,
        queued: true,
        job_id: jobId,
        status: jobStatus,
        request_id: pipelineRequestId,
        deduplicated,
        master_sku: canonicalMasterSku,
        content_type,
        platform,
        mode,
      })
    }

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
      console.warn(`Validation violations for ${canonicalMasterSku}/${platform}/${content_type}: ${violations.join('; ')}`)
      // Log but don't block — Python pipeline has its own quality checks.
      // Surface these violations to operators so they can take action.
    }

    // ==================== FINISH SENTENCES (Python-generated for Google/Bing descriptions) ====================
    const isVariantDescription = content_type === 'description' && (platform === 'google' || platform === 'bing')
    const finishSentences = isVariantDescription
      ? normalizeFinishSentences(pipelineData.finish_sentences)
      : null

    // Python pipeline is the single writer for generated_content/regeneration_history.
    // Treat authoritative persistence metadata as required contract fields.
    const pipelineState = pipelineData.state
    const pipelineIdempotent = pipelineData.idempotent
    const pipelineVersion = pipelineData.version
    const state = (pipelineState === 'no_change' || pipelineState === 'completed')
      ? pipelineState
      : null
    const idempotent = typeof pipelineIdempotent === 'boolean'
      ? pipelineIdempotent
      : null
    const version = (typeof pipelineVersion === 'number' && Number.isFinite(pipelineVersion))
      ? pipelineVersion
      : null

    if (state === null || idempotent === null || version === null) {
      const missing: string[] = []
      if (state === null) missing.push('state')
      if (idempotent === null) missing.push('idempotent')
      if (version === null) missing.push('version')
      return errorResponse(500, {
        error: `Pipeline response missing required regeneration metadata: ${missing.join(', ')}`,
        code: 'pipeline_contract_missing_regenerate_metadata',
        step: 'pipeline_response_validation',
        actionable_message:
          'Cloud Run regenerate contract drift detected. Ensure Python returns state/idempotent/version and retry.',
      })
    }
    const finishSentencesSaved = typeof pipelineData.finish_sentences_saved === 'boolean'
      ? pipelineData.finish_sentences_saved
      : (state === 'completed' && Boolean(finishSentences && Object.keys(finishSentences).length > 0))
    const pipelineRequestId = typeof pipelineData.request_id === 'string'
      ? pipelineData.request_id
      : requestId

    return NextResponse.json({
      success: true,
      content: newContent,
      version,
      mode,
      model: pipelineModel,
      prompt_hash: pipelinePromptHash,
      generated_content_id: pipelineData.generated_content_id ?? null,
      used_evidence: true, // Python pipeline always uses evidence
      used_vision: false, // Vision handled by Python pipeline internally
      finish_sentences_count: finishSentences ? Object.keys(finishSentences).length : 0,
      finish_sentences_saved: finishSentencesSaved,
      pipeline: 'python', // Indicate content came from Python pipeline
      state,
      idempotent,
      request_id: pipelineRequestId,
      validation_errors: violations,
      actionable_message:
        state === 'no_change'
          ? 'Generated content is unchanged; no persistence update was performed.'
          : violations.length > 0
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
