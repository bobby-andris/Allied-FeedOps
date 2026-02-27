import { NextRequest, NextResponse } from 'next/server'
import {
  readCostReconciliationReport,
  runCostReconciliationCapture,
} from '@/lib/monitoring/cost-reconciliation'

const DEFAULT_CAPTURE_LOOKBACK_DAYS = 1
const DEFAULT_REPORT_LOOKBACK_DAYS = 14

function parseLookbackDays(value: string | null, fallback: number, max: number): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return Math.min(Math.floor(parsed), max)
}

function isCaptureAuthorized(request: NextRequest): boolean {
  if (request.headers.get('x-vercel-cron')) {
    return true
  }

  const secret = process.env.CRON_SECRET
  if (!secret) {
    return true
  }

  const authHeader = request.headers.get('authorization')
  return authHeader === `Bearer ${secret}`
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl
    const shouldCapture =
      Boolean(request.headers.get('x-vercel-cron')) || searchParams.get('capture') === '1'

    let capture: Awaited<ReturnType<typeof runCostReconciliationCapture>> | null = null
    if (shouldCapture) {
      if (!isCaptureAuthorized(request)) {
        return NextResponse.json(
          {
            error: 'Unauthorized capture request',
          },
          { status: 401 }
        )
      }

      const captureLookbackDays = parseLookbackDays(
        searchParams.get('lookback_days'),
        DEFAULT_CAPTURE_LOOKBACK_DAYS,
        30
      )

      capture = await runCostReconciliationCapture({
        lookbackDays: captureLookbackDays,
      })
    }

    const reportLookbackDays = parseLookbackDays(
      searchParams.get('lookback_days'),
      DEFAULT_REPORT_LOOKBACK_DAYS,
      90
    )

    const report = await readCostReconciliationReport({
      lookbackDays: reportLookbackDays,
    })

    return NextResponse.json({
      success: true,
      report,
      ...(capture ? { capture } : {}),
    })
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : 'Failed to read cost reconciliation report',
      },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  if (!isCaptureAuthorized(request)) {
    return NextResponse.json(
      {
        error: 'Unauthorized capture request',
      },
      { status: 401 }
    )
  }

  try {
    const { searchParams } = request.nextUrl
    const lookbackDays = parseLookbackDays(
      searchParams.get('lookback_days'),
      DEFAULT_CAPTURE_LOOKBACK_DAYS,
      30
    )

    const capture = await runCostReconciliationCapture({
      lookbackDays,
    })

    return NextResponse.json({
      success: true,
      capture,
    })
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : 'Failed to capture cost reconciliation data',
      },
      { status: 500 }
    )
  }
}
