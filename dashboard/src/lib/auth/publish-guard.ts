import { NextRequest, NextResponse } from 'next/server'

interface PublishGuardOutcome {
  allowed: boolean
  actorRole: string | null
  actorId: string | null
  response?: NextResponse
}

function normalizeBoolEnv(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) return defaultValue
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

function parseAllowedRoles(value: string | undefined): string[] {
  const raw = value || 'admin,publisher'
  return raw
    .split(',')
    .map((role) => role.trim().toLowerCase())
    .filter((role) => role.length > 0)
}

export function enforcePublishGuard(request: NextRequest): PublishGuardOutcome {
  const rbacEnabled = normalizeBoolEnv(process.env.FEEDOPS_PUBLISH_RBAC_ENABLED, false)
  const actorRole = (request.headers.get('x-feedops-role') || request.headers.get('x-user-role') || '').trim()
  const actorId = (request.headers.get('x-user-id') || request.headers.get('x-feedops-user') || '').trim()

  if (!rbacEnabled) {
    return {
      allowed: true,
      actorRole: actorRole || null,
      actorId: actorId || null,
    }
  }

  if (!actorRole) {
    return {
      allowed: false,
      actorRole: null,
      actorId: actorId || null,
      response: NextResponse.json(
        {
          error: 'Publish denied: missing role header',
          code: 'publish_forbidden_missing_role',
          step: 'rbac_guard',
          actionable_message:
            'Set x-feedops-role (or x-user-role) to an allowed publish role and retry.',
        },
        { status: 403 }
      ),
    }
  }

  const allowedRoles = parseAllowedRoles(process.env.FEEDOPS_PUBLISH_ALLOWED_ROLES)
  const normalizedActorRole = actorRole.toLowerCase()

  if (!allowedRoles.includes(normalizedActorRole)) {
    return {
      allowed: false,
      actorRole,
      actorId: actorId || null,
      response: NextResponse.json(
        {
          error: `Publish denied for role "${actorRole}"`,
          code: 'publish_forbidden_role',
          step: 'rbac_guard',
          actionable_message: `Allowed publish roles: ${allowedRoles.join(', ')}.`,
        },
        { status: 403 }
      ),
    }
  }

  return {
    allowed: true,
    actorRole,
    actorId: actorId || null,
  }
}
