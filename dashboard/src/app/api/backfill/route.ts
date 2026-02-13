import { NextRequest, NextResponse } from 'next/server'

// Python Cloud Run pipeline URL
const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL || 'https://feedops-pipeline-623866089882.us-east1.run.app'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const status = searchParams.get('status')
    const limit = searchParams.get('limit')

    // Build upstream URL with query params
    const upstreamUrl = new URL(`${PIPELINE_URL}/backfill/jobs`)
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
