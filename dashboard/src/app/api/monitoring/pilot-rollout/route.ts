import { NextResponse } from 'next/server'
import { getPilotCanarySnapshot } from '@/lib/rollout/pilot-canary'

export async function GET() {
  try {
    return NextResponse.json({
      success: true,
      snapshot: getPilotCanarySnapshot(),
    })
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to read pilot rollout snapshot',
      },
      { status: 500 }
    )
  }
}
