/**
 * Types for the evidence table builder module
 */

/**
 * A single evidence row for the LLM prompt
 */
export interface Evidence {
  field: string
  value: string
  source: string
}

/**
 * Platform context for evidence generation
 */
export interface EvidenceContext {
  platform: 'google' | 'bing' | 'shopify'
  finish_code?: string // For variant-specific content (Google/Bing)
}

/**
 * Row from product_catalog table (subset of ProductCatalog from types.ts)
 */
export interface ProductCatalogRow {
  master_sku: string
  option_sku: string
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
  main_image_url: string | null
  alt_image_1: string | null
  material: string | null
  style: string | null
  shape: string | null
  orientation: string | null
  tilting: string | null
  mounting_type: string | null
  center_to_center: number | null
  diameter: number | null
  mirror_height: number | null
  mirror_width: number | null
  thickness: number | null
  weight_capacity: number | null
  included_items: string | null
  assembly_required: boolean
}

/**
 * Design style classification for tone guidance
 */
export interface DesignStyleContext {
  style: string
  tone_guidance: string
  style_keywords: string[]
}

/**
 * A detected functional feature
 */
export interface FunctionalFeature {
  feature_id: string
  title_keyword: string | null
  benefit: string
  keywords: string[]
}

/**
 * Result from getProductEvidence query
 */
export interface ProductEvidenceResult {
  evidence: Evidence[]
  markdown: string
  imageUrl: string | null
}
