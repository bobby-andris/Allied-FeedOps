import { randomUUID } from 'crypto'
import { NextRequest, NextResponse } from 'next/server'
import {
  getRequiredPipelineUrl,
  PIPELINE_URL_MISSING_MESSAGE,
} from '@/lib/pipeline-url'

type GenerateImagesRequest = {
  master_sku?: string
  num_variations?: number
  dry_run?: boolean
  selected_finish_code?: string
}

export async function POST(request: NextRequest) {
  let pipelineUrl: string

  try {
    pipelineUrl = getRequiredPipelineUrl()
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : PIPELINE_URL_MISSING_MESSAGE,
      },
      { status: 503 }
    )
  }

  try {
    const body: GenerateImagesRequest = await request.json()

    if (!body.master_sku?.trim()) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    const requestId = request.headers.get('x-request-id') ?? randomUUID()
    const upstream = await fetch(`${pipelineUrl}/generate-images`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(body),
    })

    const payload = await upstream.json().catch(() => ({}))
    if (!upstream.ok) {
      const detail =
        typeof payload?.detail === 'string'
          ? payload.detail
          : typeof payload?.error === 'string'
            ? payload.error
            : `Pipeline returned ${upstream.status}`

      return NextResponse.json(
        { error: detail },
        { status: upstream.status }
      )
    }

    return NextResponse.json(payload, { status: upstream.status })
  } catch (error) {
    console.error('Image generation proxy error:', error)
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : 'Failed to generate images',
      },
      { status: 500 }
    )
  }
}
