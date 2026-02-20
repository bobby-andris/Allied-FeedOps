import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import {
  computeDecompositionArtifact,
  createValueScoringContext,
} from '@/lib/optimization/decomposition/engine'
import { insertArtifactsBatch } from '@/lib/optimization/decomposition/repository'

interface BackfillRequestBody {
  start_date?: string
  end_date?: string
  custom_label_0?: string
  max_pairs?: number
  dry_run?: boolean
  min_impressions?: number
}

function sanitizeMaxPairs(input: unknown, fallback = 5000, max = 10000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function parseDryRun(input: unknown, fallback = true): boolean {
  if (typeof input === 'boolean') {
    return input
  }
  if (typeof input === 'string') {
    if (input.toLowerCase() === 'true') {
      return true
    }
    if (input.toLowerCase() === 'false') {
      return false
    }
  }
  return fallback
}

function assertAuthorized(request: NextRequest): string | null {
  if (process.env.NODE_ENV === 'development') {
    return null
  }

  const configuredToken = process.env.INTERNAL_API_TOKEN
  if (!configuredToken) {
    return 'INTERNAL_API_TOKEN is not configured.'
  }

  const providedToken = request.headers.get('x-internal-token')
  if (!providedToken || providedToken !== configuredToken) {
    return 'Unauthorized.'
  }

  return null
}

export async function POST(request: NextRequest) {
  try {
    const authError = assertAuthorized(request)
    if (authError) {
      return NextResponse.json({ error: authError }, { status: authError === 'Unauthorized.' ? 401 : 500 })
    }

    let body: BackfillRequestBody = {}
    try {
      body = (await request.json()) as BackfillRequestBody
    } catch {
      body = {}
    }

    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)

    const startDate =
      sanitizeDateInput(body.start_date) ?? sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate =
      sanitizeDateInput(body.end_date) ?? sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate
    const customLabel0 =
      sanitizeCustomLabel(body.custom_label_0 ?? undefined) ?? sanitizeCustomLabel(params.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(
      body.min_impressions !== undefined ? String(body.min_impressions) : params.get('min_impressions')
    )

    const maxPairs = sanitizeMaxPairs(body.max_pairs ?? params.get('max_pairs'))
    const dryRun = parseDryRun(body.dry_run ?? params.get('dry_run'), true)

    const sourceTerms = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit: Math.min(Math.max(maxPairs * 2, 500), 10000),
      offset: 0,
      sortBy: 'impressions_desc',
      pipeline: {
        enabled: false,
      },
    })

    const pairMap = new Map<
      string,
      {
        searchTerm: string
        customLabel0: string
        assignment: (typeof sourceTerms.terms)[number]['custom_label_0s'][number]
        labelCount: number
      }
    >()

    for (const term of sourceTerms.terms) {
      for (const assignment of term.custom_label_0s) {
        const key = `${term.search_term}||${assignment.custom_label_0}`
        if (pairMap.has(key)) {
          continue
        }
        pairMap.set(key, {
          searchTerm: term.search_term,
          customLabel0: assignment.custom_label_0,
          assignment,
          labelCount: term.custom_label_0s.length,
        })
      }
    }

    const selectedPairs = [...pairMap.values()].slice(0, maxPairs)
    const valueScoringContext = createValueScoringContext(selectedPairs.map((pair) => pair.assignment))

    const artifacts = selectedPairs.map((pair) =>
      computeDecompositionArtifact({
        searchTerm: pair.searchTerm,
        customLabel0: pair.customLabel0,
        assignment: pair.assignment,
        labelCount: pair.labelCount,
        valueScoringContext,
      })
    )

    const insertResult = dryRun
      ? { insertedPairs: 0, warnings: ['Dry run enabled; no artifacts were persisted.'] }
      : await insertArtifactsBatch(artifacts)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      mode: dryRun ? 'dry_run' : 'persist',
      date_window: sourceTerms.date_window,
      source_terms_scanned: sourceTerms.terms.length,
      pair_candidates: pairMap.size,
      pairs_processed: artifacts.length,
      inserted_pairs: insertResult.insertedPairs,
      warnings: insertResult.warnings,
      limits: {
        max_pairs: maxPairs,
      },
    })
  } catch (error) {
    console.error('Decomposition backfill failed:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    )
  }
}
