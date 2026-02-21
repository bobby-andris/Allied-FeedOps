import { describe, expect, it } from 'vitest'
import {
  autoDetectIncidents,
  evaluateRollbackReadiness,
  type AutoDetectIncidentsInput,
  type RollbackReadinessInput,
} from '@/lib/intent/incident-automation'
import { evaluateGuardrails } from '@/lib/intent/policy'

describe('autoDetectIncidents', () => {
  it('creates incident records from guardrail evaluation incidents', () => {
    const guardrailResult = evaluateGuardrails({
      recentSpend: 14000,
      recentRevenue: 8000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      attributionQualityScore: 0.3,
      staleDataHours: 30,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
    })

    const input: AutoDetectIncidentsInput = {
      guardrailDecision: guardrailResult,
      existingOpenRuleIds: [],
    }

    const result = autoDetectIncidents(input)
    expect(result.newIncidents.length).toBeGreaterThan(0)
    expect(result.newIncidents[0].rule_id).toBeDefined()
    expect(result.newIncidents[0].severity).toBeDefined()
    expect(result.newIncidents[0].message).toBeDefined()
    expect(result.newIncidents[0].status).toBe('open')
  })

  it('dedupes against existing open incidents by rule_id', () => {
    const guardrailResult = evaluateGuardrails({
      recentSpend: 14000,
      recentRevenue: 8000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      attributionQualityScore: 0.3,
      staleDataHours: 30,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
    })

    const existingRuleIds = guardrailResult.incidents.map((i) => i.ruleId)
    const result = autoDetectIncidents({
      guardrailDecision: guardrailResult,
      existingOpenRuleIds: existingRuleIds,
    })

    expect(result.newIncidents).toHaveLength(0)
    expect(result.skippedCount).toBe(guardrailResult.incidents.length)
  })

  it('returns empty when guardrails are clear', () => {
    const guardrailResult = evaluateGuardrails({
      recentSpend: 8000,
      recentRevenue: 10000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      attributionQualityScore: 0.9,
      staleDataHours: 2,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
    })

    const result = autoDetectIncidents({
      guardrailDecision: guardrailResult,
      existingOpenRuleIds: [],
    })

    expect(result.newIncidents).toHaveLength(0)
    expect(result.skippedCount).toBe(0)
  })

  it('only creates incidents for rules not already open', () => {
    const guardrailResult = evaluateGuardrails({
      recentSpend: 14000,
      recentRevenue: 8000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      attributionQualityScore: 0.3,
      staleDataHours: 30,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
    })

    // Only mark first rule as existing
    const firstRuleId = guardrailResult.incidents[0]?.ruleId
    const result = autoDetectIncidents({
      guardrailDecision: guardrailResult,
      existingOpenRuleIds: firstRuleId ? [firstRuleId] : [],
    })

    expect(result.newIncidents.length).toBe(guardrailResult.incidents.length - 1)
    expect(result.skippedCount).toBe(1)
  })

  it('includes suggested_action from guardrail incidents', () => {
    const guardrailResult = evaluateGuardrails({
      recentSpend: 14000,
      recentRevenue: 8000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
    })

    const result = autoDetectIncidents({
      guardrailDecision: guardrailResult,
      existingOpenRuleIds: [],
    })

    for (const incident of result.newIncidents) {
      expect(incident.suggested_action).toBeDefined()
      expect(typeof incident.suggested_action).toBe('string')
    }
  })
})

describe('evaluateRollbackReadiness', () => {
  it('returns ready when guardrails are blocked and snapshots exist', () => {
    const input: RollbackReadinessInput = {
      guardrailStatus: 'blocked',
      snapshotCount: 3,
      openCriticalIncidents: 1,
      openHighIncidents: 2,
      hasActiveNegatives: true,
    }
    const result = evaluateRollbackReadiness(input)
    expect(result.ready).toBe(true)
    expect(result.recommendation).toBe('rollback_recommended')
  })

  it('returns ready with caution when guardrails are on hold', () => {
    const input: RollbackReadinessInput = {
      guardrailStatus: 'hold',
      snapshotCount: 1,
      openCriticalIncidents: 0,
      openHighIncidents: 2,
      hasActiveNegatives: false,
    }
    const result = evaluateRollbackReadiness(input)
    expect(result.ready).toBe(true)
    expect(result.recommendation).toBe('rollback_optional')
  })

  it('returns not ready when guardrails are clear', () => {
    const input: RollbackReadinessInput = {
      guardrailStatus: 'go',
      snapshotCount: 5,
      openCriticalIncidents: 0,
      openHighIncidents: 0,
      hasActiveNegatives: false,
    }
    const result = evaluateRollbackReadiness(input)
    expect(result.ready).toBe(false)
    expect(result.recommendation).toBe('no_rollback_needed')
  })

  it('returns not ready when no snapshots available', () => {
    const input: RollbackReadinessInput = {
      guardrailStatus: 'blocked',
      snapshotCount: 0,
      openCriticalIncidents: 1,
      openHighIncidents: 0,
      hasActiveNegatives: true,
    }
    const result = evaluateRollbackReadiness(input)
    expect(result.ready).toBe(false)
    expect(result.recommendation).toBe('no_snapshots_available')
    expect(result.blockers.length).toBeGreaterThan(0)
  })

  it('includes checklist items in result', () => {
    const input: RollbackReadinessInput = {
      guardrailStatus: 'blocked',
      snapshotCount: 2,
      openCriticalIncidents: 1,
      openHighIncidents: 1,
      hasActiveNegatives: true,
    }
    const result = evaluateRollbackReadiness(input)
    expect(result.checklist.length).toBeGreaterThan(0)
    for (const item of result.checklist) {
      expect(item.label).toBeDefined()
      expect(typeof item.passed).toBe('boolean')
    }
  })
})
