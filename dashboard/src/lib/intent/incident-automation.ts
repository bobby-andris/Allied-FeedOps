import type { GuardrailDecision, GuardrailRolloutStatus } from '@/lib/intent/types'

export interface AutoDetectIncidentsInput {
  guardrailDecision: GuardrailDecision
  existingOpenRuleIds: string[]
}

export interface DetectedIncident {
  rule_id: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'open'
  message: string
  suggested_action: string
}

export interface AutoDetectIncidentsResult {
  newIncidents: DetectedIncident[]
  skippedCount: number
}

export function autoDetectIncidents(input: AutoDetectIncidentsInput): AutoDetectIncidentsResult {
  const existingSet = new Set(input.existingOpenRuleIds)
  const newIncidents: DetectedIncident[] = []
  let skippedCount = 0

  for (const incident of input.guardrailDecision.incidents) {
    if (existingSet.has(incident.ruleId)) {
      skippedCount++
      continue
    }
    newIncidents.push({
      rule_id: incident.ruleId,
      severity: incident.severity,
      status: 'open',
      message: incident.message,
      suggested_action: incident.suggestedAction,
    })
  }

  return { newIncidents, skippedCount }
}

export interface RollbackReadinessInput {
  guardrailStatus: GuardrailRolloutStatus
  snapshotCount: number
  openCriticalIncidents: number
  openHighIncidents: number
  hasActiveNegatives: boolean
}

export type RollbackRecommendation =
  | 'rollback_recommended'
  | 'rollback_optional'
  | 'no_rollback_needed'
  | 'no_snapshots_available'

export interface RollbackChecklistItem {
  label: string
  passed: boolean
}

export interface RollbackReadinessResult {
  ready: boolean
  recommendation: RollbackRecommendation
  checklist: RollbackChecklistItem[]
  blockers: string[]
}

export function evaluateRollbackReadiness(input: RollbackReadinessInput): RollbackReadinessResult {
  const checklist: RollbackChecklistItem[] = []
  const blockers: string[] = []

  const hasSnapshots = input.snapshotCount > 0
  checklist.push({ label: 'Policy snapshots available', passed: hasSnapshots })
  if (!hasSnapshots) {
    blockers.push('No policy snapshots available for rollback')
  }

  const needsRollback = input.guardrailStatus !== 'go'
  checklist.push({ label: 'Guardrail status requires action', passed: needsRollback })

  const hasCritical = input.openCriticalIncidents > 0
  checklist.push({ label: 'Critical incidents present', passed: hasCritical })

  const hasHigh = input.openHighIncidents > 0
  checklist.push({ label: 'High-severity incidents present', passed: hasHigh })

  checklist.push({ label: 'Active cross-channel negatives to clean', passed: input.hasActiveNegatives })

  if (!hasSnapshots) {
    return {
      ready: false,
      recommendation: 'no_snapshots_available',
      checklist,
      blockers,
    }
  }

  if (!needsRollback) {
    return {
      ready: false,
      recommendation: 'no_rollback_needed',
      checklist,
      blockers,
    }
  }

  if (input.guardrailStatus === 'blocked') {
    return {
      ready: true,
      recommendation: 'rollback_recommended',
      checklist,
      blockers,
    }
  }

  // hold status
  return {
    ready: true,
    recommendation: 'rollback_optional',
    checklist,
    blockers,
  }
}
