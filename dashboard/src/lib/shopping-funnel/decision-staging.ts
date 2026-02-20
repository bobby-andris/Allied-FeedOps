import type {
  AssignmentTier,
  NeedsDecisionTerm,
  PostDecisionItem,
  SaveDecisionItem,
  DecisionActionType,
} from '@/lib/shopping-funnel/types'

export interface NeedsDecisionStateLike {
  actionType: DecisionActionType
  assignments: Partial<Record<string, AssignmentTier>>
}

export interface DecisionCompletionResult {
  complete: boolean
  requiredCount: number
  selectedCount: number
  missingLabels: string[]
}

function isTier(value: unknown): value is AssignmentTier {
  return value === 'campaign_negative' || value === 'high' || value === 'medium' || value === 'low'
}

export function getDecisionCompletion(
  term: NeedsDecisionTerm,
  state: NeedsDecisionStateLike
): DecisionCompletionResult {
  if (state.actionType !== 'funnel') {
    return {
      complete: true,
      requiredCount: 0,
      selectedCount: 0,
      missingLabels: [],
    }
  }

  const requiredLabels = term.custom_label_0s.map((item) => item.custom_label_0)
  const missingLabels = requiredLabels.filter((label) => !isTier(state.assignments[label]))
  const selectedCount = requiredLabels.length - missingLabels.length

  return {
    complete: requiredLabels.length > 0 && missingLabels.length === 0,
    requiredCount: requiredLabels.length,
    selectedCount,
    missingLabels,
  }
}

export function buildDecisionItem(
  term: NeedsDecisionTerm,
  state: NeedsDecisionStateLike
): SaveDecisionItem {
  if (state.actionType !== 'funnel') {
    return {
      search_term: term.search_term,
      action_type: state.actionType,
    }
  }

  const assignments = term.custom_label_0s
    .map((item) => ({
      custom_label_0: item.custom_label_0,
      tier: state.assignments[item.custom_label_0],
    }))
    .filter((item): item is { custom_label_0: string; tier: AssignmentTier } => isTier(item.tier))

  return {
    search_term: term.search_term,
    action_type: state.actionType,
    assignments,
  }
}

export function toPostDecisionItem(item: SaveDecisionItem): PostDecisionItem {
  return {
    search_term: item.search_term,
    action_type: item.action_type,
    assignments: item.assignments,
  }
}

export function createDecisionSignature(item: SaveDecisionItem): string {
  if (item.action_type !== 'funnel') {
    return `${item.search_term}|${item.action_type}|shared`
  }

  const normalizedAssignments = [...(item.assignments ?? [])]
    .map((assignment) => `${assignment.custom_label_0}:${assignment.tier}`)
    .sort((a, b) => a.localeCompare(b))
    .join('|')

  return `${item.search_term}|${item.action_type}|${normalizedAssignments}`
}
