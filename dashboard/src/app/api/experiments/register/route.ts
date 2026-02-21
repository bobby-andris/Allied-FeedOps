import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { insertRowsSafe } from '@/lib/intent/persistence'

interface RegisterRequestBody {
  name?: string
  initiative?: string
  hypothesis?: string
  decision_rule?: string
  success_threshold?: number
  failure_threshold?: number
  start_date?: string
  end_date?: string
  created_by?: string
  metadata?: Record<string, unknown>
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as RegisterRequestBody
    if (!body.name || !body.initiative || !body.hypothesis) {
      return NextResponse.json(
        { error: 'name, initiative, and hypothesis are required' },
        { status: 400 }
      )
    }

    const experimentKey = `${slugify(body.initiative)}-${slugify(body.name)}-${Date.now()}`

    const row = {
      experiment_key: experimentKey,
      name: body.name,
      initiative: body.initiative,
      hypothesis: body.hypothesis,
      decision_rule: body.decision_rule ?? null,
      success_threshold: Number.isFinite(body.success_threshold) ? Number(body.success_threshold) : null,
      failure_threshold: Number.isFinite(body.failure_threshold) ? Number(body.failure_threshold) : null,
      status: 'active',
      start_date: body.start_date ?? new Date().toISOString().slice(0, 10),
      end_date: body.end_date ?? null,
      metadata: body.metadata ?? {},
      created_by: body.created_by ?? null,
    }

    const supabase = createAdminClient()
    const insert = await insertRowsSafe(supabase, 'experiment_registry', [row])

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      experiment_key: experimentKey,
      persisted: {
        experiment_registry: insert.inserted,
      },
      warnings: insert.warning ? [insert.warning] : [],
    })
  } catch (error) {
    console.error('Register experiment failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
