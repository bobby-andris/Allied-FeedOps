import type { AssignmentTier, DecisionActionType, NeedsDecisionTerm } from '@/lib/shopping-funnel/types'

export const INTENT_POLICY_VERSION = 'intent_v1'

export type IntentClass =
  | 'BRAND_CORE'
  | 'PRODUCT_HIGH'
  | 'CATEGORY_MID'
  | 'DISCOVERY_LOW'
  | 'COMPETITOR'
  | 'INFO_ASSIST'
  | 'MISMATCH'
  | 'RISK_POLICY'

export type IntentSubclass =
  | 'brand_only'
  | 'brand_with_category'
  | 'brand_with_sku'
  | 'product_with_size'
  | 'product_with_material'
  | 'product_with_finish'
  | 'category_with_modifier'
  | 'room_fixture'
  | 'broad_problem'
  | 'competitor_product'
  | 'competitor_alternative'
  | 'how_to'
  | 'install_care'
  | 'irrelevant_product'
  | 'policy_sensitive'

export type DecisionChannel = 'shopping' | 'search' | 'cross_channel'

export type RouteAction =
  | DecisionActionType
  | 'search_discovery'
  | 'search_exact_candidate'
  | 'observe_only'

export type PromotionDemotionAction =
  | 'promote_to_medium'
  | 'promote_to_high'
  | 'demote_to_medium'
  | 'demote_to_low'
  | 'negative'
  | 'hold'

export type SearchTier = 'broad' | 'phrase' | 'exact'

export type SearchGovernanceAction =
  | 'graduate_shopping_to_search'
  | 'promote_to_phrase'
  | 'promote_to_exact'
  | 'demote_to_phrase'
  | 'exclude'
  | 'hold'

export type BidPolicyAction = 'increase_target' | 'decrease_target' | 'hold'
export type TargetMode = 'roas' | 'cpa'

export type GuardrailRolloutStatus = 'go' | 'hold' | 'blocked'

export interface IntentClassification {
  normalizedQuery: string
  intentClass: IntentClass
  subclasses: IntentSubclass[]
  reasonCodes: string[]
  matchedTokens: string[]
  isBranded: boolean
  isCompetitor: boolean
  hasMismatchRisk: boolean
}

export interface TermMetrics {
  impressions: number
  clicks: number
  conversions: number
  conversionsValue: number
  costMicros: number
}

export interface IntentDecisionInput {
  searchTerm: string
  metrics: TermMetrics
  attributionQualityScore?: number
  valueSignalScore?: number
  existingTerm?: NeedsDecisionTerm
}

export interface IntentRouteDecision {
  searchTerm: string
  classification: IntentClassification
  routeAction: RouteAction
  recommendedTier?: AssignmentTier
  confidence: number
  requiresReview: boolean
  reasonCodes: string[]
  policyVersion: string
}

export interface PromotionDemotionInput {
  searchTerm: string
  currentTier: AssignmentTier
  metrics: TermMetrics
  marginRoas?: number
  confidence: number
  attributionQualityScore?: number
  valueSignalScore?: number
}

export interface PromotionDemotionDecision {
  searchTerm: string
  action: PromotionDemotionAction
  confidence: number
  reasonCodes: string[]
  policyVersion: string
}

export interface SearchGovernanceInput {
  searchTerm: string
  currentTier: SearchTier
  metrics: TermMetrics
  confidence: number
  classification: IntentClassification
  attributionQualityScore?: number
}

export interface SearchGovernanceDecision {
  searchTerm: string
  action: SearchGovernanceAction
  recommendedTier: SearchTier | null
  confidence: number
  reasonCodes: string[]
  policyVersion: string
}

export interface BidPolicyInput {
  key: string
  channel: DecisionChannel
  intentClass: IntentClass
  targetMode?: TargetMode
  currentTargetRoas?: number
  observedRoas?: number
  currentTargetCpa?: number
  observedCpa?: number
  confidence: number
  attributionQualityScore?: number
  valueSignalScore?: number
}

export interface BidPolicyDecision {
  key: string
  action: BidPolicyAction
  recommendedTargetRoas?: number
  recommendedTargetCpa?: number
  confidence: number
  reasonCodes: string[]
  policyVersion: string
}

export interface ShoppingToSearchGraduationInput {
  searchTerm: string
  classification: IntentClassification
  metrics: TermMetrics
  confidence: number
  alreadyCoveredInSearch?: boolean
  attributionQualityScore?: number
}

export interface ShoppingToSearchGraduationDecision {
  searchTerm: string
  eligible: boolean
  suggestedTier: SearchTier | null
  confidence: number
  requiresReview: boolean
  reasonCodes: string[]
  policyVersion: string
}

export interface GuardrailInput {
  recentSpend: number
  recentRevenue: number
  baselineSpend: number
  baselineRevenue: number
  attributionQualityScore?: number
  staleDataHours?: number
  openCriticalIncidents?: number
  openHighIncidents?: number
}

export interface GuardrailDecision {
  status: GuardrailRolloutStatus
  incidents: Array<{
    ruleId: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    message: string
    suggestedAction: string
  }>
  reasonCodes: string[]
  policyVersion: string
}

// --- Tier Movement Execution Types ---

export type TierMovementStatus = 'pending' | 'approved' | 'executed' | 'failed' | 'rejected' | 'deferred'

export interface TierMovementRequest {
  searchTerm: string
  customLabel0: string
  currentTier: AssignmentTier
  targetTier: AssignmentTier
  action: PromotionDemotionAction
  confidence: number
  reasonCodes: string[]
  policyVersion: string
  requestedBy?: string
}

export interface TierMovementResult {
  searchTerm: string
  customLabel0: string
  currentTier: AssignmentTier
  targetTier: AssignmentTier
  status: 'applied' | 'failed' | 'blocked' | 'review_required'
  executionLogId?: string
  negativeRegistryId?: string
  sheetRowUpdated?: boolean
  reasonCodes: string[]
  error?: string
}

export interface TierMovementBatchRequest {
  movements: TierMovementRequest[]
  dryRun?: boolean
  createdBy?: string
}

export interface TierMovementBatchResult {
  results: TierMovementResult[]
  appliedCount: number
  failedCount: number
  blockedCount: number
  reviewRequiredCount: number
  guardrailStatus: GuardrailRolloutStatus
  executedAt: string
}

export interface TierMovementHistoryEntry {
  id: string
  searchTerm: string
  customLabel0: string
  previousTier: AssignmentTier
  newTier: AssignmentTier
  action: PromotionDemotionAction
  status: string
  confidence: number
  reasonCodes: string[]
  createdBy: string | null
  createdAt: string
}
