/**
 * POST /api/performance/capture-snapshot
 *
 * Manual override endpoint that now triggers the pipeline's durable
 * daily collector + impact computation flow.
 */

import { NextRequest, NextResponse } from 'next/server'

const PIPELINE_URL =
  process.env.FEEDOPS_PIPELINE_URL ||
  'https://feedops-pipeline-623866089882.us-east1.run.app'

async function postPipeline(path: string, body: Record<string, unknown>) {
  const response = await fetch(`${PIPELINE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof payload?.detail === 'string'
        ? payload.detail
        : typeof payload?.error === 'string'
          ? payload.error
          : `Pipeline call failed: ${path}`
    throw new Error(detail)
  }
  return payload
}

export async function POST(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const filterSku = searchParams.get('master_sku')
    const platform = searchParams.get('platform') || 'google'
    const environment = searchParams.get('environment') || 'production'
    const runDate = new Date().toISOString().slice(0, 10)
    const masterSkus = filterSku ? [filterSku] : undefined

    const collectPayload = {
      run_date: runDate,
      platform,
      environment,
      master_skus: masterSkus,
      days_to_refresh: 3,
      max_controls: 500,
    }
    const collectResult = await postPipeline('/performance/collect-daily', collectPayload)

    const computePayload = {
      run_date: runDate,
      platform,
      environment,
      master_skus: masterSkus,
      pre_window_days: 30,
      post_window_days: 30,
    }
    const computeResult = await postPipeline('/performance/compute-impact', computePayload)

    return NextResponse.json({
      success: true,
      message: 'Triggered daily snapshot collection and impact computation',
      snapshots_created: collectResult?.rows_upserted ?? 0,
      impact_rows_upserted: computeResult?.rows_upserted ?? 0,
      treated_skus: collectResult?.treated_skus ?? 0,
      control_skus: collectResult?.control_skus ?? 0,
      run_date: runDate,
      platform,
      environment,
    })
  } catch (error) {
    console.error('Snapshot capture failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
