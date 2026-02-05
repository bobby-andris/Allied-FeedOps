// Database types for FeedOps
// These will be extended as we add more tables

export interface SkuApproval {
  id: string
  master_sku: string
  title_approved: number | null  // 1 = approved, 0 = rejected, null = not reviewed
  description_approved: number | null
  image_approved: number | null
  approval_status: 'pending' | 'approved' | 'revision' | 'rejected'
  selected_finish: string | null
  selected_image_index: number | null
  notes: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface VariantApproval {
  id: string
  master_sku: string
  finish: string
  title_approved: number | null
  description_approved: number | null
  image_approved: number | null
  approval_status: 'pending' | 'approved' | 'revision' | 'rejected'
  notes: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface PublishBatch {
  batch_id: string
  name: string
  target_date: string | null
  status: 'draft' | 'ready' | 'executing' | 'completed' | 'failed'
  notes: string | null
  executed_at: string | null
  sku_count: number
  success_count: number
  failed_count: number
  created_at: string
  updated_at: string
}

export interface PublishEvent {
  id: string
  master_sku: string
  platform: 'google' | 'bing' | 'shopify'
  environment: 'staging' | 'production'
  action: 'publish' | 'rollback'
  status: 'success' | 'failed'
  published_at: string
  batch_id: string | null
  error_message: string | null
  // Content snapshot for rollback (added in migration 021)
  published_title: string | null
  published_description: string | null
  variant_count: number | null
  content_version: number | null
}

export interface GeneratedContent {
  id: string
  master_sku: string
  platform: 'google' | 'bing' | 'shopify'
  content_type: 'title' | 'description'
  baseline_content: string | null
  candidate_content: string | null
  quality_score: number | null
  version: number
  is_current: boolean
  created_at: string
  updated_at: string
  // Approval tracking (added in migration 021)
  approved_content: string | null
  approved_at: string | null
  approved_version: number | null
}

export type FeedbackPreset = 
  | 'shorter' 
  | 'longer' 
  | 'more_specific' 
  | 'different_angle' 
  | 'more_keywords' 
  | 'less_promotional' 
  | 'better_hook'

export interface RegenerationHistory {
  id: string
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  feedback_text: string | null
  feedback_preset: FeedbackPreset | null
  previous_content: string | null
  new_content: string | null
  model_version: string | null
  system_prompt: string | null
  user_prompt: string | null
  prompt_hash: string | null
  quality_score_before: number | null
  quality_score_after: number | null
  created_at: string
  created_by: string | null
  generated_content_id: string | null
}

export interface GeneratedImage {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  prompt: string | null
  generation_model: string | null
  generation_timestamp: string | null
  score: number | null
  score_breakdown: Record<string, number> | null
  // Selection tracking
  ai_selected: boolean        // AI's recommendation based on scoring
  user_selected: boolean      // User's actual choice for this variant
  use_for_master: boolean     // If this variant image should also be used for master SKU
  // Approval tracking
  approval_status: 'pending' | 'approved' | 'rejected'
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  // Variant association
  finish: string | null
  finish_code: string | null
  // GMC tracking
  gmc_pushed_at: string | null
  gmc_offer_id: string | null
  created_at: string
}

// Alias for enhanced usage in review components
export type EnhancedImageRecord = GeneratedImage

export interface LifestyleImageSelection {
  id: string
  master_sku: string
  finish: string | null
  selected_image_id: string | null
  selection_reason: string | null
  selected_by: string | null
  selected_at: string
}

export interface PerformanceSnapshot {
  id: string
  master_sku: string
  platform: 'google' | 'bing' | 'shopify'
  environment: 'staging' | 'production'
  snapshot_date: string
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  cvr: number
  cost: number
  cpc: number
  roas: number | null
  created_at: string
}

export interface PerformanceBaseline {
  id: string
  master_sku: string
  platform: 'google' | 'bing' | 'shopify'
  period_start: string
  period_end: string
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  cvr: number
  cost: number
  cpc: number
  roas: number | null
  created_at: string
}

export interface VariantIndex {
  id: string
  option_sku: string        // Unique variant SKU (e.g., "1051-ABR")
  gmc_offer_id: string      // GMC offer ID for Google Merchant Center
  master_sku: string
  shopify_product_id: string | null
  shopify_variant_id: string | null
  finish: string | null     // Finish name (e.g., "Antique Brass")
  finish_code: string | null // Finish code (e.g., "ABR")
  dimensions: string | null
  product_title: string | null
  product_category: string | null
  created_at: string
  updated_at: string
}

// Batch Generation Jobs (for multi-SKU generation from /generate page)
export interface BatchGenerationJob {
  id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  total_skus: number
  completed_skus: number
  failed_skus: number
  options: {
    titles: boolean
    descriptions: boolean
    images: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
    num_candidates?: number
  }
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  created_by: string | null
}

export interface BatchGenerationJobSku {
  id: string
  job_id: string
  master_sku: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  generated_content_ids: string[] | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

// ============================================================================
// Product Catalog Types (from Acatalog.csv)
// ============================================================================

export interface ProductCatalog {
  id: number
  master_sku: string
  option_sku: string
  core_sku: string | null
  upc: string | null
  gtin: string | null
  gmc_id: string | null
  amazon_asin: string | null
  finish_name: string
  finish_code: string
  position: number | null
  category: string
  collection: string | null
  title: string
  narrative_copy: string | null
  bullet_1: string | null
  bullet_2: string | null
  bullet_3: string | null
  bullet_4: string | null
  bullet_5: string | null
  bullet_6: string | null
  product_length: number | null
  product_height: number | null
  product_width: number | null
  projection: number | null
  product_weight: number | null
  box_length: number | null
  box_height: number | null
  box_width: number | null
  box_weight: number | null
  installation_url: string | null
  specification_url: string | null
  main_image_filename: string | null
  main_image_url: string | null
  alt_image_1: string | null
  alt_image_2: string | null
  alt_image_3: string | null
  alt_image_4: string | null
  center_to_center: number | null
  diameter: number | null
  screw_size: string | null
  mirror_height: number | null
  mirror_width: number | null
  thickness: number | null
  weight_capacity: number | null
  material: string | null
  style: string | null
  shape: string | null
  orientation: string | null
  tilting: string | null
  mounting_type: string | null
  assembly_required: boolean
  item_number: string | null
  included_items: string | null
  created_at: string
  updated_at: string
}

// ============================================================================
// Competitor Intelligence Types
// ============================================================================

export interface CompetitorScrapeJob {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  job_type: 'serp' | 'marketplace'
  category: string
  source: 'google' | 'amazon' | 'wayfair' | 'homedepot'
  search_query: string | null
  apify_run_id: string | null
  apify_dataset_id: string | null
  listings_count: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface CompetitorListing {
  id: string
  source: string
  source_type: 'serp' | 'marketplace'
  source_url: string | null
  domain: string | null
  product_category: string
  title: string
  description: string | null
  price: number | null
  rating: number | null
  review_count: number | null
  brand: string | null
  position: number | null
  image_url: string | null
  scraped_at: string
  scrape_job_id: string | null
  keywords_extracted: string[] | null
}

export type CompetitorPatternType =
  | 'title_structure'
  | 'keyword'
  | 'benefit'
  | 'trust_signal'
  | 'competitor_brand'

export interface CompetitorPattern {
  id: string
  category: string
  pattern_type: CompetitorPatternType
  pattern_value: string
  frequency: number
  avg_position: number | null
  sources: string[] | null
  example_titles: string[] | null
  updated_at: string
}

// ============================================================================
// Search Query Insights Types
// ============================================================================

export interface SearchQuerySyncJob {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  job_type: 'search_terms' | 'keyword_planner' | 'full_sync'
  days_lookback: number
  limit_results: number
  enrich_with_keyword_planner: boolean
  queries_fetched: number
  queries_enriched: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export type CompetitionLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNSPECIFIED'

export interface SearchQuery {
  id: string
  query_text: string
  campaign_id: string | null
  // Variant-level identification
  gmc_offer_id: string | null
  master_sku: string | null
  finish: string | null
  finish_code: string | null
  shopify_variant_id: string | null
  // Google Ads metrics
  impressions: number
  clicks: number
  conversions: number
  conversion_value: number
  cost_micros: number
  ctr: number       // computed
  cvr: number       // computed
  // Keyword Planner metrics
  avg_monthly_searches: number | null
  competition: CompetitionLevel | null
  competition_index: number | null
  low_cpc_micros: number | null
  high_cpc_micros: number | null
  keyword_metrics_updated_at: string | null
  // Time tracking
  period_start: string
  period_end: string
  fetched_at: string
  sync_job_id: string | null
}

export interface SearchQueryByMasterSku {
  id: string
  master_sku: string
  query_text: string
  // Aggregated metrics
  total_impressions: number
  total_clicks: number
  total_conversions: number
  total_conversion_value: number
  variant_count: number
  top_variant_finish: string | null
  top_variant_finish_code: string | null
  // Keyword Planner metrics
  avg_monthly_searches: number | null
  competition: CompetitionLevel | null
  competition_index: number | null
  // Time tracking
  period_start: string
  period_end: string
  updated_at: string
}

export interface KeywordMetrics {
  keyword: string
  avg_monthly_searches: number | null
  competition: CompetitionLevel | null
  competition_index: number | null
  low_cpc_micros: number | null
  high_cpc_micros: number | null
  monthly_searches: Array<{
    year: number
    month: number
    searches: number
  }> | null
  updated_at: string
}

export interface KeywordCoverageVariant {
  id: string
  master_sku: string
  finish: string
  finish_code: string | null
  gmc_offer_id: string | null
  keyword: string
  in_title: boolean
  in_description: boolean
  query_volume: number
  avg_monthly_searches: number | null
  updated_at: string
}

export interface KeywordCoverageMaster {
  id: string
  master_sku: string
  keyword: string
  in_title: boolean
  in_description: boolean
  query_volume: number
  avg_monthly_searches: number | null
  updated_at: string
}

export interface FinishSearchPattern {
  id: string
  finish: string
  finish_code: string
  pattern_keyword: string
  total_impressions: number
  total_clicks: number
  query_count: number
  category: string | null
  updated_at: string
}

// Database schema type
export interface Database {
  public: {
    Tables: {
      sku_approvals: {
        Row: SkuApproval
        Insert: Omit<SkuApproval, 'id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<SkuApproval, 'id' | 'created_at'>>
      }
      variant_approvals: {
        Row: VariantApproval
        Insert: Omit<VariantApproval, 'id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<VariantApproval, 'id' | 'created_at'>>
      }
      publish_batches: {
        Row: PublishBatch
        Insert: Omit<PublishBatch, 'batch_id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<PublishBatch, 'batch_id' | 'created_at'>>
      }
      publish_events: {
        Row: PublishEvent
        Insert: Omit<PublishEvent, 'id'>
        Update: Partial<Omit<PublishEvent, 'id'>>
      }
      generated_content: {
        Row: GeneratedContent
        Insert: Omit<GeneratedContent, 'id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<GeneratedContent, 'id' | 'created_at'>>
      }
      generated_images: {
        Row: GeneratedImage
        Insert: Omit<GeneratedImage, 'id' | 'created_at'>
        Update: Partial<Omit<GeneratedImage, 'id' | 'created_at'>>
      }
      performance_snapshots: {
        Row: PerformanceSnapshot
        Insert: Omit<PerformanceSnapshot, 'id' | 'created_at'>
        Update: Partial<Omit<PerformanceSnapshot, 'id' | 'created_at'>>
      }
      performance_baselines: {
        Row: PerformanceBaseline
        Insert: Omit<PerformanceBaseline, 'id' | 'created_at'>
        Update: Partial<Omit<PerformanceBaseline, 'id' | 'created_at'>>
      }
      variant_index: {
        Row: VariantIndex
        Insert: Omit<VariantIndex, 'id'>
        Update: Partial<Omit<VariantIndex, 'id'>>
      }
      regeneration_history: {
        Row: RegenerationHistory
        Insert: Omit<RegenerationHistory, 'id' | 'created_at'>
        Update: Partial<Omit<RegenerationHistory, 'id' | 'created_at'>>
      }
      batch_generation_jobs: {
        Row: BatchGenerationJob
        Insert: Omit<BatchGenerationJob, 'id' | 'created_at' | 'completed_skus' | 'failed_skus'>
        Update: Partial<Omit<BatchGenerationJob, 'id' | 'created_at'>>
      }
      batch_generation_job_skus: {
        Row: BatchGenerationJobSku
        Insert: Omit<BatchGenerationJobSku, 'id' | 'created_at'>
        Update: Partial<Omit<BatchGenerationJobSku, 'id' | 'created_at'>>
      }
    }
  }
}
