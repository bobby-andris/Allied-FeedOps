import { NextResponse } from 'next/server'

export interface PilotCanaryGuardOutcome {
  allowed: boolean
  blockedSkus: string[]
  response?: NextResponse
}

function normalizeBoolEnv(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) return defaultValue
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

function parseAllowedSkus(raw: string | undefined): Set<string> {
  if (!raw) return new Set()
  return new Set(
    raw
      .split(',')
      .map((sku) => sku.trim())
      .filter((sku) => sku.length > 0)
      .map((sku) => sku.toUpperCase())
  )
}

function isCanaryEnabled(): boolean {
  return normalizeBoolEnv(process.env.FEEDOPS_PILOT_CANARY_ENABLED, false)
}

function isFailClosed(): boolean {
  return normalizeBoolEnv(process.env.FEEDOPS_PILOT_FAIL_CLOSED, true)
}

export function enforcePilotCanaryForSkus(
  skus: string[],
  operation: 'regenerate' | 'publish-sku' | 'publish-batch'
): PilotCanaryGuardOutcome {
  if (!isCanaryEnabled()) {
    return { allowed: true, blockedSkus: [] }
  }

  const normalizedSkus = skus.map((sku) => sku.trim()).filter((sku) => sku.length > 0)
  const allowedSkus = parseAllowedSkus(process.env.FEEDOPS_PILOT_ALLOWED_SKUS)
  const failClosed = isFailClosed()

  if (allowedSkus.size === 0 && failClosed) {
    return {
      allowed: false,
      blockedSkus: normalizedSkus,
      response: NextResponse.json(
        {
          error: 'Pilot canary is enabled but FEEDOPS_PILOT_ALLOWED_SKUS is empty',
          code: 'pilot_canary_missing_allowlist',
          step: 'pilot_canary_guard',
          actionable_message:
            'Set FEEDOPS_PILOT_ALLOWED_SKUS to a comma-separated SKU allowlist or disable FEEDOPS_PILOT_CANARY_ENABLED.',
          operation,
        },
        { status: 503 }
      ),
    }
  }

  if (allowedSkus.size === 0 && !failClosed) {
    return { allowed: true, blockedSkus: [] }
  }

  const blockedSkus = normalizedSkus.filter((sku) => !allowedSkus.has(sku.toUpperCase()))

  if (blockedSkus.length > 0) {
    return {
      allowed: false,
      blockedSkus,
      response: NextResponse.json(
        {
          error: 'Pilot canary blocks one or more requested SKUs',
          code: 'pilot_canary_sku_blocked',
          step: 'pilot_canary_guard',
          actionable_message:
            'Limit requests to pilot-allowlisted SKUs, or update FEEDOPS_PILOT_ALLOWED_SKUS for the current rollout cohort.',
          operation,
          blocked_skus: blockedSkus,
        },
        { status: 409 }
      ),
    }
  }

  return { allowed: true, blockedSkus: [] }
}

export function getPilotCanarySnapshot(): {
  enabled: boolean
  fail_closed: boolean
  allowlist_count: number
  allowlist_preview: string[]
} {
  const allowlist = Array.from(parseAllowedSkus(process.env.FEEDOPS_PILOT_ALLOWED_SKUS))
  return {
    enabled: isCanaryEnabled(),
    fail_closed: isFailClosed(),
    allowlist_count: allowlist.length,
    allowlist_preview: allowlist.slice(0, 10),
  }
}
