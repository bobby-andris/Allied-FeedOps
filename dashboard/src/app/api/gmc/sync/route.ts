import { NextResponse } from 'next/server'

const PIPELINE_URL =
  process.env.FEEDOPS_PIPELINE_URL ||
  'https://feedops-pipeline-623866089882.us-east1.run.app'

export async function POST() {
  try {
    const upstream = await fetch(`${PIPELINE_URL}/gmc/sync`, {
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
