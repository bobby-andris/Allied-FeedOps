import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { uploadProductImage, uploadVariantImage } from '@/lib/publishing/shopify-images'

/**
 * Upload approved lifestyle image to Shopify CDN.
 *
 * POST /api/images/upload-to-shopify
 * Body: { imageId: string, imageType: 'product' | 'variant' }
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
    const { imageId, imageType } = body

    if (!imageId || !imageType) {
      return NextResponse.json(
        { error: 'imageId and imageType are required' },
        { status: 400 }
      )
    }

    if (!['product', 'variant'].includes(imageType)) {
      return NextResponse.json(
        { error: 'imageType must be "product" or "variant"' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Determine table based on image type
    const tableName = imageType === 'product'
      ? 'product_lifestyle_images'
      : 'variant_lifestyle_images'

    // Get image details from appropriate table
    const selectFields = imageType === 'product'
      ? 'id, master_sku, image_url, shopify_product_id, approval_status'
      : 'id, master_sku, finish, image_url, gmc_offer_id, approval_status'

    const { data: image, error: fetchError } = await supabase
      .from(tableName)
      .select(selectFields)
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

    let result: { mediaId: string; cdnUrl: string }

    if (imageType === 'product') {
      // Product-level image - has shopify_product_id directly
      if (!image.shopify_product_id) {
        return NextResponse.json(
          { error: 'Shopify product ID not found' },
          { status: 404 }
        )
      }

      result = await uploadProductImage(
        image.image_url,
        image.shopify_product_id,
        `${image.master_sku} product image`
      )
    } else {
      // Variant-level image - lookup Shopify IDs via gmc_offer_id
      const { data: variant, error: variantError } = await supabase
        .from('variant_index')
        .select('shopify_product_id, shopify_variant_id')
        .eq('gmc_offer_id', image.gmc_offer_id)
        .single()

      if (variantError || !variant?.shopify_product_id) {
        return NextResponse.json(
          { error: 'No Shopify mapping found for this variant' },
          { status: 404 }
        )
      }

      result = await uploadVariantImage(
        image.image_url,
        variant.shopify_product_id,
        variant.shopify_variant_id || '',
        `${image.master_sku} - ${image.finish}`
      )
    }

    // Update database with Shopify CDN URL and metadata
    const { error: updateError } = await supabase
      .from(tableName)
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
