import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { uploadVariantImage } from '@/lib/publishing/shopify-images'

/**
 * Diagnostic endpoint to test Shopify CDN migration
 *
 * GET /api/test-migration?sku=FT-16
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const sku = searchParams.get('sku') || 'FT-16'

    const supabase = await createClient()

    // Get ONE approved image for this SKU
    const { data: images, error } = await supabase
      .from('variant_lifestyle_images')
      .select('id, image_url, gmc_offer_id, master_sku, finish, shopify_cdn_url')
      .eq('master_sku', sku)
      .eq('approval_status', 'approved')
      .is('shopify_cdn_url', null)
      .limit(1)

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    if (!images || images.length === 0) {
      return NextResponse.json({
        success: false,
        message: 'No images needing migration found',
        sku,
      })
    }

    const img = images[0]

    // Lookup Shopify IDs
    const { data: variant, error: variantError } = await supabase
      .from('variant_index')
      .select('shopify_product_id, shopify_variant_id')
      .eq('gmc_offer_id', img.gmc_offer_id)
      .single()

    if (variantError || !variant?.shopify_product_id) {
      return NextResponse.json({
        error: 'No Shopify mapping found',
        gmc_offer_id: img.gmc_offer_id,
        variantError: variantError?.message,
      }, { status: 500 })
    }

    // Attempt upload
    console.log(`[Test Migration] Uploading image ${img.id} for ${img.gmc_offer_id}`)

    const result = await uploadVariantImage(
      img.image_url,
      variant.shopify_product_id,
      variant.shopify_variant_id || '',
      `${img.master_sku} - ${img.finish}`
    )

    console.log(`[Test Migration] Upload successful:`, result)

    // Update database
    await supabase
      .from('variant_lifestyle_images')
      .update({
        shopify_media_id: result.mediaId,
        shopify_cdn_url: result.cdnUrl,
        migrated_to_shopify_at: new Date().toISOString(),
      })
      .eq('id', img.id)

    return NextResponse.json({
      success: true,
      imageId: img.id,
      gmc_offer_id: img.gmc_offer_id,
      finish: img.finish,
      shopify_media_id: result.mediaId,
      shopify_cdn_url: result.cdnUrl,
    })

  } catch (error) {
    console.error('[Test Migration] Error:', error)
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
    }, { status: 500 })
  }
}
