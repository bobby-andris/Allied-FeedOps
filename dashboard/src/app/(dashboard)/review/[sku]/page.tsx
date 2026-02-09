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
  generation_model: string | null
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

// Per-platform "current" content for comparison display
// - Shopify: from product_catalog (what's actually live on Shopify)
// - Google/Bing: from baseline_content in generated_content (previous generation)
interface CurrentContentByPlatform {
  [platform: string]: { title: string | null; description: string | null }
}

interface ApprovalRecord {
  master_sku: string
  approval_status: string
  title_approved: number | null  // 1 = approved, 0 = rejected, null = not reviewed
  description_approved: number | null
  image_approved: number | null
  notes: string | null
}

/**
 * Generate all possible SKU formats to try when looking up in the database.
 *
 * Problem: SKUs in the database may use slashes (WP-2/16-GAL) or hyphens (920D-6),
 * while URLs must use hyphens (slashes are path separators).
 *
 * Solution: Generate multiple candidate formats and try each one.
 *
 * @param urlSku The SKU as it appears in the URL (hyphens only)
 * @returns Array of possible database formats to try
 */
function getSkuCandidates(urlSku: string): string[] {
  const candidates: string[] = []

  // 1. URL-decode in case of %2F encoding
  const decoded = decodeURIComponent(urlSku)

  // 2. Add the decoded URL SKU as-is (might match directly)
  candidates.push(decoded)

  // 3. Try replacing last hyphen-before-dimension with slash
  // Pattern: -16, -2X, -16-GAL → /16, /2X, /16-GAL
  const normalizedLast = decoded.replace(/-(\d+[A-Z]*(?:-[A-Z]+)?)$/i, '/$1')
  if (normalizedLast !== decoded) {
    candidates.push(normalizedLast)
  }

  // 4. Try replacing the second-to-last hyphen-digit segment (for patterns like WP-2-16-GAL where the 2 is a model number)
  // This handles cases like WP-2-16-GAL where we need WP-2/16-GAL
  const twoPartMatch = decoded.match(/^(.+?)-(\d+)-(\d+[A-Z]*(?:-[A-Z]+)?)$/i)
  if (twoPartMatch) {
    candidates.push(`${twoPartMatch[1]}-${twoPartMatch[2]}/${twoPartMatch[3]}`)
  }

  // 5. If the SKU has a slash already (from decoding), also try the hyphen version
  if (decoded.includes('/')) {
    candidates.push(decoded.replace(/\//g, '-'))
  }

  // Remove duplicates while preserving order
  return [...new Set(candidates)]
}

async function getSkuData(urlSku: string) {
  const supabase = await createClient()

  // Generate all possible SKU formats to try
  const skusToTry = getSkuCandidates(urlSku)

  // Get content for all platforms - try each SKU format until we find a match
  let content = null
  let contentError = null
  for (const sku of skusToTry) {
    const result = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', sku)
      .order('platform')
      .order('content_type')
    if (result.data && result.data.length > 0) {
      content = result.data
      break
    }
    contentError = result.error
  }
  const effectiveSku = content && content.length > 0 ? content[0].master_sku : urlSku
  
  if (contentError) {
    console.error('Error fetching content:', contentError)
  }

  // Use effectiveSku for remaining queries (the SKU format that worked)
  const sku = effectiveSku

  // Get product-level lifestyle images (for Shopify product page display)
  const { data: productLifestyleImages, error: productImagesError } = await supabase
    .from('product_lifestyle_images')
    .select('*')
    .eq('master_sku', sku)
    .order('variation_index')

  if (productImagesError) {
    console.error('Error fetching product lifestyle images:', productImagesError)
  }

  // Get variant-level lifestyle images (for GMC feed / variant-specific display)
  const { data: variantLifestyleImages, error: variantImagesError } = await supabase
    .from('variant_lifestyle_images')
    .select('*')
    .eq('master_sku', sku)
    .order('finish', { ascending: true })
    .order('variation_index')

  if (variantImagesError) {
    console.error('Error fetching variant lifestyle images:', variantImagesError)
  }

  // Build lookup from image_url to finish info (variant images have finish data)
  const finishByUrl = new Map<string, { finish: string; finish_code: string }>()
  for (const img of variantLifestyleImages || []) {
    if (img.finish && img.image_url) {
      finishByUrl.set(img.image_url, { finish: img.finish, finish_code: img.finish_code })
    }
  }

  // Transform for UI — deduplicate by image_url since the same image
  // exists in both product_lifestyle_images and variant_lifestyle_images
  const variantImageUrls = new Set(
    (variantLifestyleImages || []).map(img => img.image_url).filter(Boolean)
  )

  const images: ImageRecord[] = [
    // Product images that DON'T also exist as variant images
    ...(productLifestyleImages || [])
      .filter(img => !img.image_url || !variantImageUrls.has(img.image_url))
      .map(img => {
        const finishInfo = finishByUrl.get(img.image_url)
        return {
          ...img,
          use_for_master: true,
          approval_status: img.approval_status as 'pending' | 'approved' | 'rejected',
          finish: finishInfo?.finish ?? null,
          finish_code: finishInfo?.finish_code ?? null,
        }
      }),
    // All variant images (preferred — they have native finish data)
    ...(variantLifestyleImages || []).map(img => ({
      ...img,
      use_for_master: false,
      approval_status: img.approval_status as 'pending' | 'approved' | 'rejected',
    })),
  ]

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
    .select('option_sku, finish_code, finish_name, main_image_url, alt_image_1, alt_image_2, alt_image_3, alt_image_4, title, narrative_copy')
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
  const currentContentByPlatform: CurrentContentByPlatform = {}
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

    // Shopify: use product_catalog data (what's actually live on Shopify)
    currentContentByPlatform['shopify'] = {
      title: firstProduct.title,
      description: firstProduct.narrative_copy,
    }
  }

  // Build variant current content map (option_sku -> { title, description })
  const variantCurrentContent: Record<string, { title: string | null; description: string | null }> = {}
  if (productCatalog) {
    for (const product of productCatalog) {
      if (product.option_sku) {
        variantCurrentContent[product.option_sku] = {
          title: product.title,
          description: product.narrative_copy,
        }
      }
    }
  }

  // Google/Bing: use baseline_content from generated_content (previous generation)
  if (content && content.length > 0) {
    for (const platform of ['google', 'bing']) {
      const platformRecords = (content as ContentRecord[]).filter(c => c.platform === platform)
      const titleBaseline = platformRecords.find(c => c.content_type === 'title')?.baseline_content || null
      const descBaseline = platformRecords.find(c => c.content_type === 'description')?.baseline_content || null
      if (titleBaseline || descBaseline) {
        currentContentByPlatform[platform] = {
          title: titleBaseline,
          description: descBaseline,
        }
      }
    }
  }

  // Get finish sentences for Google and Bing (product+finish tailored content)
  const { data: googleFinishSentences } = await supabase
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', sku)
    .eq('platform', 'google')
    .single()

  const { data: bingFinishSentences } = await supabase
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', sku)
    .eq('platform', 'bing')
    .single()

  // Get performance baselines (30-day pre-publish metrics)
  const { data: performanceBaselines, error: baselinesError } = await supabase
    .from('performance_baselines')
    .select('*')
    .eq('master_sku', sku)

  if (baselinesError) {
    console.error('Error fetching performance baselines:', baselinesError)
  }

  // Get latest performance snapshot (post-publish metrics)
  const { data: performanceSnapshots, error: snapshotsError } = await supabase
    .from('performance_snapshots')
    .select('*')
    .eq('master_sku', sku)
    .order('snapshot_date', { ascending: false })
    .limit(10)  // Get last 10 snapshots for trend

  if (snapshotsError) {
    console.error('Error fetching performance snapshots:', snapshotsError)
  }

  return {
    content: (content || []) as ContentRecord[],
    images,
    approval: approval as ApprovalRecord | null,
    variants: (variants || []) as VariantIndex[],
    variantApprovals: (variantApprovals || []) as VariantApproval[],
    productImages,
    currentContentByPlatform,
    variantCurrentContent,
    finishSentences: {
      google: googleFinishSentences?.finish_sentences as Record<string, string> | null || null,
      bing: bingFinishSentences?.finish_sentences as Record<string, string> | null || null,
    },
    performanceBaselines: performanceBaselines || [],
    performanceSnapshots: performanceSnapshots || [],
  }
}

export default async function SkuReviewPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = await params
  const {
    content,
    images,
    approval,
    variants,
    variantApprovals,
    productImages,
    currentContentByPlatform,
    variantCurrentContent,
    finishSentences,
    performanceBaselines,
    performanceSnapshots
  } = await getSkuData(sku)

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
      currentContentByPlatform={currentContentByPlatform}
      variantCurrentContent={variantCurrentContent}
      finishSentences={finishSentences}
      performanceBaselines={performanceBaselines}
      performanceSnapshots={performanceSnapshots}
    />
  )
}
