// Publishing types for FeedOps dashboard

export type Platform = 'google' | 'shopify' | 'bing'
export type Environment = 'staging' | 'production'

/**
 * Request to publish content for a single SKU to a platform
 */
export interface PublishRequest {
  master_sku: string
  title: string
  description: string
  image_url?: string
  environment: Environment
}

/**
 * Request to publish to Shopify (requires product ID)
 */
export interface ShopifyPublishRequest extends PublishRequest {
  shopify_product_id: string
}

/**
 * Result of a single publish operation
 */
export interface PublishResult {
  success: boolean
  master_sku: string
  platform: Platform
  error?: string
  details?: {
    updated_count?: number
    appended_count?: number
    offer_ids?: string[]
    shopify_product_id?: string
    [key: string]: unknown
  }
}

/**
 * Request to publish a batch of SKUs across multiple platforms
 */
export interface BatchPublishRequest {
  batch_id: string
  platforms: Platform[]
  environment: Environment
}

/**
 * Result of a batch publish operation
 */
export interface BatchPublishResult {
  success: boolean
  batch_id: string
  environment: Environment
  total_skus: number
  successful_skus: number
  failed_skus: number
  results: PublishResult[]
}

/**
 * Row data for Google Sheets supplemental feed
 *
 * GMC Policy for AI-Generated Content:
 * - If content is AI-generated, use structured_title/structured_description
 *   with digital_source_type=trained_algorithmic_media
 * - If both structured and standard fields are present, GMC ignores structured
 * - Set FEEDOPS_GMC_STRUCTURED_ONLY=1 to omit title/description and use only structured fields
 */
export interface GoogleSheetsRow {
  id: string // offer_id (GMC ID)
  title?: string // Standard title (omit if structured-only mode)
  description?: string // Standard description (omit if structured-only mode)
  structured_title?: string // For AI-generated content
  structured_description?: string // For AI-generated content
  digital_source_type?: string // 'trained_algorithmic_media' for AI content
  short_title?: string
  lifestyle_image_link?: string
  custom_label_4: string // tracking label: feedops-staging or feedops-production
}

/**
 * Column mapping for Google Sheets
 */
export interface SheetColumnMap {
  id: number
  title?: number
  description?: number
  structured_title?: number
  structured_description?: number
  digital_source_type?: number
  short_title?: number
  lifestyle_image_link?: number
  custom_label_4?: number
  [key: string]: number | undefined
}

/**
 * Variant index row from Supabase
 */
export interface VariantIndexRow {
  gmc_offer_id: string
  master_sku: string
  shopify_product_id: string | null
  shopify_variant_id: string | null
  finish: string | null
  finish_code: string | null
  dimensions: string | null
  product_title: string | null
  product_category: string | null
}

/**
 * Generated content row from Supabase
 */
export interface GeneratedContentRow {
  master_sku: string
  platform: Platform
  content_type: 'title' | 'description'
  baseline_content: string | null
  candidate_content: string | null
  quality_score: number | null
}

/**
 * Publish event for logging
 */
export interface PublishEventInsert {
  master_sku: string
  platform: Platform
  environment: Environment
  action: 'publish' | 'rollback'
  status: 'success' | 'failed' | 'pending'
  patch_file?: string
  quality_score?: number
  approval_status?: string
  error_message?: string
  published_by?: string
  batch_id?: string
  product_category?: string
  product_collection?: string
}
