import { NextRequest, NextResponse } from 'next/server'
import {
  getRequiredPipelineUrl,
  PIPELINE_URL_MISSING_MESSAGE,
} from '@/lib/pipeline-url'

export async function GET(request: NextRequest) {
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

    const { searchParams } = new URL(request.url)
    const status = searchParams.get('status')
    const limit = searchParams.get('limit')

    // Build upstream URL with query params
    const upstreamUrl = new URL(`${pipelineUrl}/backfill/jobs`)
    if (status) upstreamUrl.searchParams.set('status', status)
    if (limit) upstreamUrl.searchParams.set('limit', limit)

    // Proxy request to Cloud Run
    const response = await fetch(upstreamUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })

    if (!response.ok) {
      console.error(`Backfill jobs proxy error: ${response.status}`)
      return NextResponse.json(
        { error: `Upstream returned ${response.status}` },
        { status: 502 }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Backfill jobs proxy error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch backfill jobs' },
      { status: 502 }
    )
  }
}
