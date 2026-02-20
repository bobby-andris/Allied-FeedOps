import type { AssignmentTier, DecisionActionType, SaveDecisionItem } from '@/lib/shopping-funnel/types'

export interface SearchTermDecisionRow {
  search_term: string
  action_type: string
  custom_label_0: string | null
  tier: string | null
  created_at: string
}

export interface StagedDecisionSnapshot extends SaveDecisionItem {
  staged_at: string
}

function isActionType(value: unknown): value is DecisionActionType {
  return (
    value === 'funnel' || value === 'global_block' || value === 'competitor' || value === 'branded'
  )
}

function isAssignmentTier(value: unknown): value is AssignmentTier {
  return value === 'campaign_negative' || value === 'high' || value === 'medium' || value === 'low'
}

function toTimestamp(value: string): number {
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

export function buildStagedDecisionSnapshots(
  rows: SearchTermDecisionRow[]
): StagedDecisionSnapshot[] {
  const rowsByTerm = new Map<string, SearchTermDecisionRow[]>()

  for (const row of rows) {
    if (!isActionType(row.action_type)) {
      continue
    }

    const current = rowsByTerm.get(row.search_term) ?? []
    current.push(row)
    rowsByTerm.set(row.search_term, current)
  }

  const snapshots: StagedDecisionSnapshot[] = []

  for (const [searchTerm, termRows] of rowsByTerm.entries()) {
    const sortedByCreatedAt = [...termRows].sort(
      (a, b) => toTimestamp(b.created_at) - toTimestamp(a.created_at)
    )
    const newest = sortedByCreatedAt[0]
    if (!newest || !isActionType(newest.action_type)) {
      continue
    }

    if (newest.action_type !== 'funnel') {
      snapshots.push({
        search_term: searchTerm,
        action_type: newest.action_type,
        assignments: undefined,
        staged_at: newest.created_at,
      })
      continue
    }

    const assignmentMap = new Map<string, AssignmentTier>()
    const cutoff = toTimestamp(newest.created_at)
    for (const row of sortedByCreatedAt) {
      if (toTimestamp(row.created_at) < cutoff) {
        continue
      }
      if (row.action_type !== 'funnel' || !row.custom_label_0 || !isAssignmentTier(row.tier)) {
        continue
      }
      if (!assignmentMap.has(row.custom_label_0)) {
        assignmentMap.set(row.custom_label_0, row.tier)
      }
    }

    if (assignmentMap.size === 0) {
      continue
    }

    const assignments = [...assignmentMap.entries()]
      .map(([custom_label_0, tier]) => ({ custom_label_0, tier }))
      .sort((a, b) => a.custom_label_0.localeCompare(b.custom_label_0))

    snapshots.push({
      search_term: searchTerm,
      action_type: 'funnel',
      assignments,
      staged_at: newest.created_at,
    })
  }

  return snapshots.sort((a, b) => b.staged_at.localeCompare(a.staged_at))
}
