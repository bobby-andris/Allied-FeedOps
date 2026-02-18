import { createClient } from "@/lib/supabase/server"
import { BatchRegenerateButton } from "@/components/review/BatchRegenerateButton"
import {
  buildPlatformProgress,
  computePlatformReadinessForSku,
  computeContentStateByPlatform,
  latestProductionPublishSnapshots,
  type PlatformProgress,
  type PlatformContentState,
} from "@/lib/review/platform-progress"
import { ReviewListClient } from "@/components/review/ReviewListClient"
import type { Platform } from "@/lib/publishing/types"

export interface LifestyleImageLifecycle {
  total: number      // variants with any lifestyle image
  approved: number   // variants with approval_status = 'approved'
  published: number  // variants uploaded to Shopify (shopify_media_id IS NOT NULL)
}

export interface SkuWithContent {
  master_sku: string
  approval_status: string | null
  title_approved: boolean | null
  description_approved: boolean | null
  image_approved: boolean | null
  content_count: number
  avg_quality_score: number | null
  platform_progress: PlatformProgress[]
  product_title: string | null
  thumbnail_url: string | null
  per_platform_approval: Partial<Record<Platform, PlatformContentState>>
  lifestyle_images: LifestyleImageLifecycle
}

interface GeneratedContentRow {
  master_sku: string
  quality_score: number | null
  platform: string | null
  content_type: string | null
  approved_content: string | null
}

interface VariantRow {
  master_sku: string
  finish: string | null
}

interface VariantApprovalRow {
  master_sku: string
  finish: string | null
  approval_status: string | null
  title_approved: boolean | number | string | null
  description_approved: boolean | number | string | null
}

interface VariantImageRow {
  master_sku: string
  finish: string | null
  approval_status: string | null
  user_selected: boolean | null
  shopify_media_id: string | null
}

interface PublishEventRow {
  master_sku: string
  platform: string | null
  published_at: string | null
  published_title: string | null
  published_description: string | null
  content_version: number | null
}

interface ContentApprovalRow {
  master_sku: string
  platform: string | null
  content_type: string | null
  approved_content: string | null
}

interface CatalogRow {
  master_sku: string
  title: string | null
  main_image_url: string | null
}

async function getSkusWithContent(): Promise<SkuWithContent[]> {
  const supabase = await createClient()

  // Get generated content including per-platform approval snapshots.
  const { data: contentSkus, error: contentError } = await supabase
    .from('generated_content')
    .select('master_sku, quality_score, platform, content_type, approved_content')

  if (contentError) {
    console.error('Error fetching content:', contentError)
    return []
  }

  const skuList = [...new Set((contentSkus || []).map((row) => row.master_sku).filter(Boolean))]
  if (skuList.length === 0) {
    return []
  }

  // Get master-level approval rows.
  const { data: approvals, error: approvalsError } = await supabase
    .from('sku_approvals')
    .select('*')
    .in('master_sku', skuList)

  if (approvalsError) {
    console.error('Error fetching approvals:', approvalsError)
  }

  // Get variant readiness dependencies.
  const { data: variants, error: variantsError } = await supabase
    .from('variant_index')
    .select('master_sku, finish')
    .in('master_sku', skuList)

  if (variantsError) {
    console.error('Error fetching variants:', variantsError)
  }

  const { data: variantApprovals, error: variantApprovalsError } = await supabase
    .from('variant_approvals')
    .select('master_sku, finish, approval_status, title_approved, description_approved')
    .in('master_sku', skuList)

  if (variantApprovalsError) {
    console.error('Error fetching variant approvals:', variantApprovalsError)
  }

  const { data: variantImages, error: variantImagesError } = await supabase
    .from('variant_lifestyle_images')
    .select('master_sku, finish, approval_status, user_selected, shopify_media_id')
    .in('master_sku', skuList)

  if (variantImagesError) {
    console.error('Error fetching variant images:', variantImagesError)
  }

  // Get latest successful production publish snapshots.
  const { data: publishEvents, error: publishEventsError } = await supabase
    .from('publish_events')
    .select('master_sku, platform, published_at, published_title, published_description, content_version')
    .in('master_sku', skuList)
    .eq('action', 'publish')
    .eq('status', 'success')
    .eq('environment', 'production')
    .order('published_at', { ascending: false })

  if (publishEventsError) {
    console.error('Error fetching publish events:', publishEventsError)
  }

  // Get product catalog data (title + thumbnail) via RPC.
  // Uses DISTINCT ON (master_sku) server-side so we get exactly one row per SKU regardless of
  // how many finish variants exist — no PostgREST 1000-row limit issues.
  // ABR (Antique Brass) is selected as the thumbnail: alphabetically first image URL per SKU.
  const { data: catalogRows } = await supabase
    .rpc('get_catalog_thumbnails', { sku_list: skuList })

  // Get per-platform approval state (only approved content) for all SKUs.
  const { data: contentApprovalRows } = await supabase
    .from('generated_content')
    .select('master_sku, platform, content_type, approved_content')
    .in('master_sku', skuList)
    .not('approved_content', 'is', null)

  const contentBySku = new Map<string, GeneratedContentRow[]>()
  const variantsBySku = new Map<string, VariantRow[]>()
  const variantApprovalsBySku = new Map<string, VariantApprovalRow[]>()
  const variantImagesBySku = new Map<string, VariantImageRow[]>()
  const publishEventsBySku = new Map<string, PublishEventRow[]>()
  const contentApprovalBySku = new Map<string, ContentApprovalRow[]>()

  for (const row of contentSkus || []) {
    const bucket = contentBySku.get(row.master_sku) || []
    bucket.push(row)
    contentBySku.set(row.master_sku, bucket)
  }

  for (const row of variants || []) {
    const bucket = variantsBySku.get(row.master_sku) || []
    bucket.push(row)
    variantsBySku.set(row.master_sku, bucket)
  }

  for (const row of variantApprovals || []) {
    const bucket = variantApprovalsBySku.get(row.master_sku) || []
    bucket.push(row)
    variantApprovalsBySku.set(row.master_sku, bucket)
  }

  for (const row of variantImages || []) {
    const bucket = variantImagesBySku.get(row.master_sku) || []
    bucket.push(row)
    variantImagesBySku.set(row.master_sku, bucket)
  }

  for (const row of publishEvents || []) {
    const bucket = publishEventsBySku.get(row.master_sku) || []
    bucket.push(row)
    publishEventsBySku.set(row.master_sku, bucket)
  }

  for (const row of contentApprovalRows || []) {
    const bucket = contentApprovalBySku.get(row.master_sku) || []
    bucket.push(row)
    contentApprovalBySku.set(row.master_sku, bucket)
  }

  // Build catalog lookup by SKU (RPC returns one row per SKU — no dedup needed).
  const catalogBySku = new Map<string, CatalogRow>()
  for (const row of catalogRows || []) {
    catalogBySku.set(row.master_sku, row)
  }

  // Build result
  const approvalMap = new Map((approvals || []).map(a => [a.master_sku, a]))

  const result: SkuWithContent[] = []
  for (const [sku, skuContent] of contentBySku) {
    const approval = approvalMap.get(sku)
    const scores = skuContent
      .map((row) => row.quality_score)
      .filter((score): score is number => typeof score === 'number')
    const avgScore = scores.length > 0
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : null

    const perPlatformApproval = computeContentStateByPlatform(contentApprovalBySku.get(sku) ?? [])

    const readiness = computePlatformReadinessForSku({
      contentRecords: skuContent,
      variants: variantsBySku.get(sku) || [],
      variantApprovals: variantApprovalsBySku.get(sku) || [],
      variantImages: variantImagesBySku.get(sku) || [],
    })
    const publishSnapshots = latestProductionPublishSnapshots(publishEventsBySku.get(sku) || [])

    const skuVariantImages = variantImagesBySku.get(sku) || []
    const lifestyleImages: LifestyleImageLifecycle = {
      total: skuVariantImages.length,
      approved: skuVariantImages.filter(img => img.approval_status === 'approved').length,
      published: skuVariantImages.filter(img => img.shopify_media_id != null).length,
    }

    result.push({
      master_sku: sku,
      approval_status: approval?.approval_status || 'pending',
      title_approved: approval?.title_approved || null,
      description_approved: approval?.description_approved || null,
      image_approved: approval?.image_approved || null,
      content_count: skuContent.length,
      avg_quality_score: avgScore,
      platform_progress: buildPlatformProgress(readiness, publishSnapshots, perPlatformApproval),
      product_title: catalogBySku.get(sku)?.title ?? null,
      thumbnail_url: catalogBySku.get(sku)?.main_image_url ?? null,
      per_platform_approval: perPlatformApproval,
      lifestyle_images: lifestyleImages,
    })
  }

  // Sort by SKU
  result.sort((a, b) => a.master_sku.localeCompare(b.master_sku))

  return result
}

export default async function ReviewPage() {
  const skus = await getSkusWithContent()

  return (
    <div className="p-8">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Review Queue</h1>
          <p className="text-muted-foreground">
            Review and approve generated content for {skus.length} product SKUs
          </p>
        </div>
        <BatchRegenerateButton totalSkus={skus.length} />
      </div>
      <ReviewListClient skus={skus} />
    </div>
  )
}
