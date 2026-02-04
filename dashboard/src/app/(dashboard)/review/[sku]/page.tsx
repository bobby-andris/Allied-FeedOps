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
  score: number | null
  selected: boolean
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
  
  return {
    content: (content || []) as ContentRecord[],
    images: (images || []) as ImageRecord[],
    approval: approval as ApprovalRecord | null,
    variants: (variants || []) as VariantIndex[],
    variantApprovals: (variantApprovals || []) as VariantApproval[],
  }
}

export default async function SkuReviewPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = await params
  const { content, images, approval, variants, variantApprovals } = await getSkuData(sku)
  
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
    />
  )
}
