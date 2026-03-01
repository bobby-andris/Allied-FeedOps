import { NextResponse } from 'next/server'
import {
  getRequiredPipelineUrl,
  PIPELINE_URL_MISSING_MESSAGE,
} from '@/lib/pipeline-url'

export async function POST() {
  let pipelineUrl: string

  try {
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

    const upstream = await fetch(`${pipelineUrl}/gmc/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!upstream.ok) {
      const text = await upstream.text().catch(() => 'Unknown error')
      return NextResponse.json(
        { error: `Pipeline returned ${upstream.status}`, detail: text },
        { status: upstream.status }
      )
    }

    const data = await upstream.json()
    return NextResponse.json(data, { status: 202 })
  } catch (err) {
    console.error('GMC sync proxy error:', err)
    return NextResponse.json(
      { error: 'Failed to trigger GMC sync', detail: String(err) },
      { status: 500 }
    )
  }
}
