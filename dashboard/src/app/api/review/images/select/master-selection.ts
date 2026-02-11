interface VariantImageForMasterClone {
  id: string
  master_sku: string
  variation_index: number
  image_url: string
  thumbnail_url: string | null
  prompt: string | null
  generation_model: string | null
  generation_timestamp: string | null
  score: number | null
  score_breakdown: Record<string, unknown> | null
  approval_status: string | null
  approved_by: string | null
  approved_at: string | null
}

export interface ProductMasterImagePayload {
  master_sku: string
  shopify_product_id: string
  variation_index: number
  image_url: string
  thumbnail_url: string | null
  prompt: string | null
  generation_model: string | null
  generation_timestamp: string | null
  score: number | null
  score_breakdown: Record<string, unknown> | null
  approval_status: string
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  ai_selected: boolean
  user_selected: boolean
}

export function buildProductMasterImageFromVariant(
  variantImage: VariantImageForMasterClone,
  shopifyProductId: string,
): ProductMasterImagePayload {
  return {
    master_sku: variantImage.master_sku,
    shopify_product_id: shopifyProductId,
    variation_index: variantImage.variation_index,
    image_url: variantImage.image_url,
    thumbnail_url: variantImage.thumbnail_url,
    prompt: variantImage.prompt,
    generation_model: variantImage.generation_model,
    generation_timestamp: variantImage.generation_timestamp,
    score: variantImage.score,
    score_breakdown: variantImage.score_breakdown,
    approval_status: variantImage.approval_status || 'approved',
    approved_by: variantImage.approved_by,
    approved_at: variantImage.approved_at,
    rejection_reason: null,
    ai_selected: false,
    user_selected: true,
  }
}
