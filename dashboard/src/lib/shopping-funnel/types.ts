export type FunnelTier = 'HIGH' | 'MEDIUM' | 'LOW'

export type AssignmentTier = 'campaign_negative' | 'high' | 'medium' | 'low'

export type DecisionActionType = 'global_block' | 'competitor' | 'branded' | 'funnel'

export interface QueryIntentFeatures {
  product_object: string | null
  modifier_tokens: string[]
  use_case_tokens: string[]
  is_branded: boolean
  is_competitor: boolean
  has_mismatch_risk: boolean
}

export interface QueryRecommendation {
  action_type: DecisionActionType
  default_tier?: AssignmentTier
  confidence: number
  reason_codes: string[]
}

export interface QueryValueScore {
  impact_score: number
  expected_clicks: number
  expected_cvr: number
  expected_conversion_value: number
  expected_profit_proxy: number
  uncertainty: number
}

export interface DateWindow {
  startDate: string
  endDate: string
}

export interface SearchTermSourceAssignment {
  custom_label_0: string
  source_campaign: string
  source_tier: FunnelTier
  impressions: number
  clicks: number
  cost_micros: number
  conversions: number
  conversions_value: number
}

export interface NeedsDecisionTerm {
  search_term: string
  custom_label_0s: SearchTermSourceAssignment[]
  intent_features?: QueryIntentFeatures
  recommendation?: QueryRecommendation
  value_score?: QueryValueScore
}

export interface ExistingFunnelAssignment {
  custom_label_0: string
  tier: 'High' | 'Medium' | 'Low' | 'Campaign Negative' | 'Unknown'
  error: boolean
  error_message: string | null
}

export interface ExistingFunnelTerm {
  search_term: string
  total_impressions: number
  total_clicks: number
  total_cost_micros: number
  total_conversions: number
  total_conversions_value: number
  funnels: ExistingFunnelAssignment[]
}

export interface GetNeedsDecisionOptions {
  startDate: string
  endDate: string
  customLabel0?: string
  minImpressions?: number
  limit?: number
  offset?: number
  sortBy?: 'impressions_desc' | 'impact_desc'
}

export interface GetExistingFunnelOptions {
  startDate: string
  endDate: string
  customLabel0?: string
  tier?: AssignmentTier | 'all'
  showErrorsOnly?: boolean
  minImpressions?: number
  limit?: number
  offset?: number
}

export interface NeedsDecisionResponse {
  terms: NeedsDecisionTerm[]
  total_count: number
  returned_count: number
  limit: number
  offset: number
  has_next: boolean
  custom_labels: string[]
  date_window: DateWindow
  data_source: 'google_ads_api_live'
  generated_at: string
  cache_ttl_ms: number
}

export interface ExistingFunnelResponse {
  terms: ExistingFunnelTerm[]
  total_count: number
  returned_count: number
  limit: number
  offset: number
  has_next: boolean
  error_count: number
  custom_labels: string[]
  date_window: DateWindow
  data_source: 'google_ads_api_live'
  generated_at: string
  cache_ttl_ms: number
}

export interface FunnelDecisionAssignment {
  custom_label_0: string
  tier: AssignmentTier
}

export interface PostDecisionItem {
  search_term: string
  action_type: DecisionActionType
  assignments?: FunnelDecisionAssignment[]
}

export interface PostDecisionResult {
  search_term: string
  status: 'success' | 'error'
  actions_completed: string[]
  error?: string
  error_code?: string
  retry_count?: number
}

export interface PostDecisionsResponse {
  results: PostDecisionResult[]
  success_count: number
  error_count: number
}

export interface ExistingFunnelUpdate {
  search_term: string
  custom_label_0: string
  old_tier?: AssignmentTier | 'global_block' | 'competitor' | 'branded'
  new_tier?: AssignmentTier
  new_action?: 'global_block' | 'competitor' | 'branded'
}

export interface ExistingFunnelUpdateResult {
  search_term: string
  custom_label_0: string
  status: 'success' | 'error'
  actions_completed: string[]
  error?: string
  error_code?: string
  retry_count?: number
}

export interface UpdateExistingResponse {
  results: ExistingFunnelUpdateResult[]
  success_count: number
  error_count: number
}

export interface LabelTierIntegrityIssue {
  custom_label_0: string
  present_tiers: FunnelTier[]
  missing_tiers: FunnelTier[]
}

export interface CampaignSetIntegritySummary {
  enabled_shopping_campaigns: number
  parsed_funnel_campaigns: number
  non_pattern_campaign_count: number
  non_pattern_campaigns: string[]
  ad_group_name_mismatch_count: number
  custom_label_0_count: number
  labels_with_missing_tiers: LabelTierIntegrityIssue[]
}

export interface ShoppingFunnelLineageResponse {
  data_source: 'google_ads_api_live'
  generated_at: string
  cache_ttl_ms: number
  date_window: DateWindow
  integrity: CampaignSetIntegritySummary
}

export interface LabelTierPerformance {
  custom_label_0: string
  tier: FunnelTier
  impressions: number
  clicks: number
  cost_micros: number
  conversions: number
  conversions_value: number
  roas: number
}

export interface LabelTierPerformanceResponse {
  rows: LabelTierPerformance[]
  total_rows: number
  date_window: DateWindow
  data_source: 'google_ads_api_live'
  generated_at: string
  cache_ttl_ms: number
}

export interface SaveDecisionItem {
  search_term: string
  action_type: DecisionActionType
  assignments?: FunnelDecisionAssignment[]
  source_campaign?: string
  source_tier?: FunnelTier
  impressions?: number
  clicks?: number
  cost_micros?: number
  conversions?: number
  conversions_value?: number
}

export interface StagedDecisionSnapshot {
  search_term: string
  action_type: DecisionActionType
  assignments?: FunnelDecisionAssignment[]
  staged_at: string
}

export interface StagedDecisionsResponse {
  decisions: StagedDecisionSnapshot[]
  staged_term_count: number
  total_unposted_terms: number
}
