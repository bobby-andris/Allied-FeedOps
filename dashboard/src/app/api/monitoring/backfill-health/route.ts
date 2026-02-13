import { NextRequest, NextResponse } from 'next/server'

// Python Cloud Run pipeline URL
const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL || 'https://feedops-pipeline-623866089882.us-east1.run.app'

export async function GET(request: NextRequest) {
  try {
    // Fetch all 3 monitoring endpoints in parallel
    const [freshnessRes, coverageRes, apiHealthRes] = await Promise.allSettled([
      fetch(`${PIPELINE_URL}/monitoring/freshness`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
      }),
      fetch(`${PIPELINE_URL}/monitoring/coverage`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
      }),
      fetch(`${PIPELINE_URL}/monitoring/api-health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
      }),
    ])

    // Extract data from settled promises (null if failed)
    const freshness = freshnessRes.status === 'fulfilled' && freshnessRes.value.ok
      ? await freshnessRes.value.json()
      : null

    const coverage = coverageRes.status === 'fulfilled' && coverageRes.value.ok
      ? await coverageRes.value.json()
      : null

    const apiHealth = apiHealthRes.status === 'fulfilled' && apiHealthRes.value.ok
      ? await apiHealthRes.value.json()
      : null

    // Log any failures
    if (!freshness) console.warn('Freshness endpoint failed')
    if (!coverage) console.warn('Coverage endpoint failed')
    if (!apiHealth) console.warn('API health endpoint failed')

    // Return combined response (null sections if failed)
    return NextResponse.json({
      freshness,
      coverage,
      apiHealth,
    })
  } catch (error) {
    console.error('Monitoring backfill health proxy error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch monitoring data' },
      { status: 502 }
    )
  }
}
