import { createClient } from "@/lib/supabase/server"
import { notFound } from "next/navigation"
import { SkuReviewClient } from "@/components/review/SkuReviewClient"
import { VariantIndex, VariantApproval } from "@/lib/supabase/types"

interface ContentRecord {
  id: string
  master_sku: string
  platform: string
  content_type: string
  baseline_content: string | null
  candidate_content: string | null
  quality_score: number | null
  created_at: string
}

interface ImageRecord {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  prompt: string | null
  score: number | null
  // Selection tracking
  ai_selected: boolean
  user_selected: boolean
  use_for_master: boolean
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

interface ProductImageData {
  mainImageUrl: string | null
  additionalImages: (string | null)[]
  shopifyProductUrl: string | null
  variantImages: Record<string, { mainImageUrl: string | null; additionalImages: (string | null)[] }>
}

// Current production content from product_catalog (what's live on Shopify)
interface CurrentProductionContent {
  title: string | null
  description: string | null  // narrative_copy from product_catalog
}

interface ApprovalRecord {
  master_sku: string
  approval_status: string
  title_approved: number | null  // 1 = approved, 0 = rejected, null = not reviewed
  description_approved: number | null
  image_approved: number | null
  notes: string | null
}

async function getSkuData(sku: string) {
  const supabase = await createClient()
  
  // Get content for all platforms
  const { data: content, error: contentError } = await supabase
    .from('generated_content')
    .select('*')
    .eq('master_sku', sku)
    .order('platform')
    .order('content_type')
  
  if (contentError) {
    console.error('Error fetching content:', contentError)
  }
  
  // Get images
  const { data: images, error: imagesError } = await supabase
    .from('generated_images')
    .select('*')
    .eq('master_sku', sku)
    .order('variation_index')
  
  if (imagesError) {
    console.error('Error fetching images:', imagesError)
  }
  
  // Get approval status
  const { data: approval, error: approvalError } = await supabase
    .from('sku_approvals')
    .select('*')
    .eq('master_sku', sku)
    .single()
  
  if (approvalError && approvalError.code !== 'PGRST116') {
    console.error('Error fetching approval:', approvalError)
  }
  
  // Get variants from variant_index
  const { data: variants, error: variantsError } = await supabase
    .from('variant_index')
    .select('*')
    .eq('master_sku', sku)
    .order('finish', { ascending: true })
  
  if (variantsError) {
    console.error('Error fetching variants:', variantsError)
  }
  
  // Get variant approvals
  const { data: variantApprovals, error: variantApprovalsError } = await supabase
    .from('variant_approvals')
    .select('*')
    .eq('master_sku', sku)
    .order('finish', { ascending: true })

  if (variantApprovalsError) {
    console.error('Error fetching variant approvals:', variantApprovalsError)
  }

  // Get product images, current production content, and variants from product_catalog
  const { data: productCatalog, error: productCatalogError } = await supabase
    .from('product_catalog')
    .select('finish_code, finish_name, main_image_url, alt_image_1, alt_image_2, alt_image_3, alt_image_4, title, narrative_copy')
    .eq('master_sku', sku)
    .order('position', { ascending: true })

  if (productCatalogError) {
    console.error('Error fetching product catalog:', productCatalogError)
  }

  // Get Shopify product ID from variant_index (if available)
  const { data: variantForShopify } = await supabase
    .from('variant_index')
    .select('shopify_product_id')
    .eq('master_sku', sku)
    .not('shopify_product_id', 'is', null)
    .limit(1)
    .single()

  // Build product images data structure and current production content
  let productImages: ProductImageData | null = null
  let currentProduction: CurrentProductionContent | null = null
  if (productCatalog && productCatalog.length > 0) {
    const firstProduct = productCatalog[0]
    const shopifyProductUrl = variantForShopify?.shopify_product_id
      ? `https://admin.shopify.com/store/allied-brass/products/${variantForShopify.shopify_product_id}`
      : null

    // Build variant images map
    const variantImagesMap: Record<string, { mainImageUrl: string | null; additionalImages: (string | null)[] }> = {}
    for (const product of productCatalog) {
      if (product.finish_code) {
        variantImagesMap[product.finish_code] = {
          mainImageUrl: product.main_image_url,
          additionalImages: [
            product.alt_image_1,
            product.alt_image_2,
            product.alt_image_3,
            product.alt_image_4,
          ],
        }
      }
    }

    productImages = {
      mainImageUrl: firstProduct.main_image_url,
      additionalImages: [
        firstProduct.alt_image_1,
        firstProduct.alt_image_2,
        firstProduct.alt_image_3,
        firstProduct.alt_image_4,
      ],
      shopifyProductUrl,
      variantImages: variantImagesMap,
    }

    // Current production content (what's live on Shopify)
    currentProduction = {
      title: firstProduct.title,
      description: firstProduct.narrative_copy,
    }
  }

  // Transform images to ensure approval_status has a valid value
  const transformedImages: ImageRecord[] = (images || []).map(img => ({
    ...img,
    approval_status: (img.approval_status as 'pending' | 'approved' | 'rejected') || 'pending',
  }))

  // Build variants list: prefer variant_index, fallback to product_catalog
  let finalVariants: VariantIndex[] = (variants || []) as VariantIndex[]

  if (finalVariants.length === 0 && productCatalog && productCatalog.length > 0) {
    // Build variants from product_catalog
    const uniqueFinishes = new Map<string, { finish_name: string; finish_code: string }>()
    for (const product of productCatalog) {
      if (product.finish_name && product.finish_code && !uniqueFinishes.has(product.finish_code)) {
        uniqueFinishes.set(product.finish_code, {
          finish_name: product.finish_name,
          finish_code: product.finish_code,
        })
      }
    }

    finalVariants = Array.from(uniqueFinishes.values()).map((f) => ({
      id: `pc-${sku}-${f.finish_code}`, // Synthetic ID from product_catalog
      master_sku: sku,
      finish: f.finish_name,
      finish_code: f.finish_code,
      gmc_offer_id: '', // Required by type
      shopify_product_id: null,
      shopify_variant_id: null,
      dimensions: null,
    })) as VariantIndex[]
  }

  return {
    content: (content || []) as ContentRecord[],
    images: transformedImages,
    approval: approval as ApprovalRecord | null,
    variants: finalVariants,
    variantApprovals: (variantApprovals || []) as VariantApproval[],
    productImages,
    currentProduction,
  }
}

export default async function SkuReviewPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = await params
  const { content, images, approval, variants, variantApprovals, productImages, currentProduction } = await getSkuData(sku)

  if (content.length === 0) {
    notFound()
  }

  return (
    <SkuReviewClient
      sku={sku}
      content={content}
      images={images}
      approval={approval}
      variants={variants}
      variantApprovals={variantApprovals}
      productImages={productImages}
      currentProduction={currentProduction}
    />
  )
}
