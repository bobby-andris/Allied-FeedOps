import { randomUUID } from 'crypto'
import { NextRequest, NextResponse } from 'next/server'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

type PipelineErrorPayload = {
  detail?: unknown
}

function errorResponse(
  status: number,
  payload: {
    error: string
    code?: string | null
    step?: string
    actionable_message?: string | null
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
      },
      { status }
    )
  }
  return NextResponse.json(payload, { status })
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params

    if (!jobId?.trim()) {
      return errorResponse(400, {
        error: 'Job ID is required',
        code: 'regenerate_status_missing_job_id',
        step: 'request_validation',
        actionable_message: 'Provide a valid regenerate job ID.',
      })
    }

    if (!PIPELINE_URL) {
      return errorResponse(503, {
        error: 'Content generation pipeline is not configured (FEEDOPS_PIPELINE_URL not set)',
        code: 'regenerate_status_pipeline_not_configured',
        step: 'pipeline_config',
        actionable_message:
          'Set FEEDOPS_PIPELINE_URL for this environment before checking regenerate status.',
      })
    }

    const requestId = request.headers.get('x-request-id') ?? randomUUID()
    const response = await fetch(`${PIPELINE_URL}/regenerate/status/${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      cache: 'no-store',
    })

    const payload: PipelineErrorPayload | Record<string, unknown> = await response
      .json()
      .catch(() => ({ detail: 'Unknown pipeline error' }))

    if (!response.ok) {
      const detail = (payload as PipelineErrorPayload).detail
      const detailMessage = typeof detail === 'string'
        ? detail
        : typeof detail === 'object' && detail && 'message' in detail
          ? String((detail as Record<string, unknown>).message)
          : `Pipeline returned ${response.status}`
      const detailCode = typeof detail === 'object' && detail && 'code' in detail
        ? String((detail as Record<string, unknown>).code)
        : null
      return errorResponse(response.status === 404 ? 404 : 500, {
        error: detailMessage,
        code: detailCode,
        step: 'pipeline_status_call',
        actionable_message:
          'Check Cloud Run regenerate job status endpoint and retry.',
      })
    }

    return NextResponse.json(payload)
  } catch (error) {
    console.error('Regenerate status API error:', error)
    return errorResponse(500, {
      error: error instanceof Error ? error.message : 'Internal server error',
      step: 'unhandled_exception',
      actionable_message:
        'Unexpected regenerate status failure. Retry once; if it persists, inspect API logs.',
    })
  }
}
