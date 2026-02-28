import { NextResponse } from 'next/server'
import {
  getRequiredPipelineUrl,
  PIPELINE_URL_MISSING_MESSAGE,
} from '@/lib/pipeline-url'

// Per-endpoint timeouts — freshness can be slow (2784-SKU query), coverage/apiHealth are fast
// Freshness timeout is kept short so coverage cards don't block behind the slow freshness query
const FRESHNESS_TIMEOUT_MS = 10_000  // 10s: fail fast if freshness is slow
const FAST_ENDPOINT_TIMEOUT_MS = 10_000  // 10s for coverage + api-health

function fetchWithTimeout(url: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  return fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    signal: controller.signal,
  }).finally(() => clearTimeout(timer))
}

export async function GET() {
  try {
    const pipelineUrl = getRequiredPipelineUrl()

    // Fetch all 3 monitoring endpoints in parallel, each with its own timeout.
    // Freshness has a short timeout so slow queries don't block coverage cards from rendering.
    const [freshnessRes, coverageRes, apiHealthRes] = await Promise.allSettled([
      fetchWithTimeout(`${pipelineUrl}/monitoring/freshness`, FRESHNESS_TIMEOUT_MS),
      fetchWithTimeout(`${pipelineUrl}/monitoring/coverage`, FAST_ENDPOINT_TIMEOUT_MS),
      fetchWithTimeout(`${pipelineUrl}/monitoring/api-health`, FAST_ENDPOINT_TIMEOUT_MS),
    ])

    // Extract data from settled promises (null if failed or timed out)
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
    if (!freshness) console.warn('Freshness endpoint failed or timed out')
    if (!coverage) console.warn('Coverage endpoint failed or timed out')
    if (!apiHealth) console.warn('API health endpoint failed or timed out')

    // Return combined response (null sections if failed)
    return NextResponse.json({
      freshness,
      coverage,
      apiHealth,
    })
  } catch (error) {
    if (error instanceof Error && error.message === PIPELINE_URL_MISSING_MESSAGE) {
      return NextResponse.json(
        { error: error.message },
        { status: 503 }
      )
    }
    console.error('Monitoring backfill health proxy error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch monitoring data' },
      { status: 502 }
    )
  }
}
