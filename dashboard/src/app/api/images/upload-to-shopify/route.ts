import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { uploadAndAssociateImage } from '@/lib/publishing/shopify-images'

/**
 * Upload approved lifestyle image to Shopify CDN.
 *
 * POST /api/images/upload-to-shopify
 * Body: { imageId: string }
 *
 * Workflow:
 * 1. Verify image is approved
 * 2. Get Shopify product/variant mapping from variant_index
 * 3. Upload to Shopify via productCreateMedia
 * 4. Poll for processing completion
 * 5. Associate with variant if finish-specific
 * 6. Update database with Shopify CDN URL and metadata
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { imageId } = body

    if (!imageId) {
      return NextResponse.json(
        { error: 'imageId is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Get image details
    const { data: image, error: fetchError } = await supabase
      .from('generated_images')
      .select('id, master_sku, finish_code, image_url, use_for_master, approval_status')
      .eq('id', imageId)
      .single()

    if (fetchError || !image) {
      return NextResponse.json(
        { error: 'Image not found' },
        { status: 404 }
      )
    }

    if (image.approval_status !== 'approved') {
      return NextResponse.json(
        { error: 'Image must be approved before uploading to Shopify' },
        { status: 400 }
      )
    }

    if (!image.image_url) {
      return NextResponse.json(
        { error: 'Image URL is missing' },
        { status: 400 }
      )
    }

    // Get Shopify product/variant IDs from variant_index
    const query = supabase
      .from('variant_index')
      .select('shopify_product_id, shopify_variant_id, finish_code')
      .eq('master_sku', image.master_sku)

    // If finish-specific image, filter by finish_code
    if (image.finish_code && !image.use_for_master) {
      query.eq('finish_code', image.finish_code)
    }

    const { data: variants, error: variantError } = await query.limit(1)

    if (variantError || !variants || variants.length === 0) {
      return NextResponse.json(
        { error: 'No Shopify product/variant mapping found in variant_index' },
        { status: 404 }
      )
    }

    const variant = variants[0]

    if (!variant.shopify_product_id) {
      return NextResponse.json(
        { error: 'Shopify product ID not found in variant_index' },
        { status: 404 }
      )
    }

    // Upload to Shopify
    const result = await uploadAndAssociateImage(
      image.image_url,
      variant.shopify_product_id,
      variant.shopify_variant_id || undefined,
      `${image.master_sku} - ${image.finish_code || 'Master'}`
    )

    // Update database with Shopify CDN URL and metadata
    const { error: updateError } = await supabase
      .from('generated_images')
      .update({
        shopify_media_id: result.mediaId,
        shopify_cdn_url: result.cdnUrl,
        migrated_to_shopify_at: new Date().toISOString(),
      })
      .eq('id', imageId)

    if (updateError) {
      console.error('Error updating image with Shopify CDN URL:', updateError)
      return NextResponse.json(
        { error: 'Failed to update database after Shopify upload' },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      data: {
        imageId,
        shopify_media_id: result.mediaId,
        shopify_cdn_url: result.cdnUrl,
      },
    })
  } catch (error) {
    console.error('Shopify image upload API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
