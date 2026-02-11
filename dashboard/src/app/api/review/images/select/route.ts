import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'
import { buildProductMasterImageFromVariant } from './master-selection'

export async function POST(request: NextRequest) {
  try {
    const { imageId, masterSku, finish, userSelected, useForMaster } = await request.json()

    if (!imageId || !masterSku) {
      return NextResponse.json(
        { error: 'Missing required fields: imageId and masterSku' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Handle user selection for a variant
    if (userSelected) {
      if (!finish) {
        return NextResponse.json(
          { error: 'finish is required when setting userSelected' },
          { status: 400 }
        )
      }

      // First, clear user_selected for all variant images of this SKU+finish
      const { error: clearError } = await supabase
        .from('variant_lifestyle_images')
        .update({ user_selected: false })
        .eq('master_sku', masterSku)
        .eq('finish', finish)

      if (clearError) {
        console.error('Error clearing previous selection:', clearError)
        return NextResponse.json(
          { error: 'Failed to clear previous selection' },
          { status: 500 }
        )
      }

      // Then set the new selection
      const { error: selectError } = await supabase
        .from('variant_lifestyle_images')
        .update({ user_selected: true })
        .eq('id', imageId)

      if (selectError) {
        console.error('Error selecting image:', selectError)
        return NextResponse.json(
          { error: 'Failed to select image' },
          { status: 500 }
        )
      }

      // Record in lifestyle_image_selections for audit
      const { error: auditError } = await supabase
        .from('lifestyle_image_selections')
        .upsert({
          master_sku: masterSku,
          finish: finish,
          selected_image_id: imageId,
          selected_by: 'user', // TODO: Get actual user from session
          selected_at: new Date().toISOString(),
        }, {
          onConflict: 'master_sku,finish',
          ignoreDuplicates: false,
        })

      if (auditError) {
        // Log but don't fail - audit is secondary
        console.error('Error recording selection audit:', auditError)
      }

      return NextResponse.json({ success: true, action: 'user_selected' })
    }

    // Handle Shopify master image selection
    if (useForMaster) {
      // First try to resolve as an existing product-level image
      const { data: existingProductImage, error: productLookupError } = await supabase
        .from('product_lifestyle_images')
        .select('id, master_sku')
        .eq('id', imageId)
        .eq('master_sku', masterSku)
        .maybeSingle()

      if (productLookupError) {
        console.error('Error looking up product image:', productLookupError)
        return NextResponse.json(
          { error: 'Failed to load product image for master selection' },
          { status: 500 }
        )
      }

      let selectedProductImageId = existingProductImage?.id || null

      // If no product image matches, resolve variant image and clone it into product scope
      if (!selectedProductImageId) {
        const { data: variantImage, error: variantLookupError } = await supabase
          .from('variant_lifestyle_images')
          .select('id, master_sku, variation_index, image_url, thumbnail_url, prompt, generation_model, generation_timestamp, score, score_breakdown, approval_status, approved_by, approved_at, user_selected')
          .eq('id', imageId)
          .eq('master_sku', masterSku)
          .maybeSingle()

        if (variantLookupError) {
          console.error('Error looking up variant image for master selection:', variantLookupError)
          return NextResponse.json(
            { error: 'Failed to load variant image for master selection' },
            { status: 500 }
          )
        }

        if (!variantImage) {
          return NextResponse.json(
            { error: 'Image not found for this SKU' },
            { status: 404 }
          )
        }

        if (variantImage.approval_status !== 'approved') {
          return NextResponse.json(
            {
              error: 'Variant image must be approved before using it as Shopify master image',
              actionable_message: 'Approve this variant image first, then set it as Shopify master image.',
            },
            { status: 409 }
          )
        }

        if (!variantImage.user_selected) {
          return NextResponse.json(
            {
              error: 'Variant image must be selected for its finish before using it as Shopify master image',
              actionable_message: 'Select this image for the variant first, then set it as Shopify master image.',
            },
            { status: 409 }
          )
        }

        const { data: variantMapping, error: mappingError } = await supabase
          .from('variant_index')
          .select('shopify_product_id')
          .eq('master_sku', masterSku)
          .not('shopify_product_id', 'is', null)
          .limit(1)
          .maybeSingle()

        if (mappingError) {
          console.error('Error loading Shopify mapping for master image selection:', mappingError)
          return NextResponse.json(
            { error: 'Failed to resolve Shopify product mapping' },
            { status: 500 }
          )
        }

        if (!variantMapping?.shopify_product_id) {
          return NextResponse.json(
            {
              error: 'No Shopify product mapping found for this SKU',
              actionable_message: 'Sync variant_index with Shopify product IDs, then retry master image selection.',
            },
            { status: 409 }
          )
        }

        const productPayload = buildProductMasterImageFromVariant(
          {
            ...variantImage,
            image_url: variantImage.image_url,
          },
          variantMapping.shopify_product_id,
        )

        const { data: upsertedProductImage, error: upsertError } = await supabase
          .from('product_lifestyle_images')
          .upsert(productPayload, {
            onConflict: 'master_sku,variation_index',
            ignoreDuplicates: false,
          })
          .select('id')
          .single()

        if (upsertError || !upsertedProductImage) {
          console.error('Error upserting product image from variant:', upsertError)
          return NextResponse.json(
            { error: 'Failed to create Shopify master image from variant image' },
            { status: 500 }
          )
        }

        selectedProductImageId = upsertedProductImage.id
      }

      // Clear prior master selection for this SKU
      const { error: clearError } = await supabase
        .from('product_lifestyle_images')
        .update({ user_selected: false })
        .eq('master_sku', masterSku)

      if (clearError) {
        console.error('Error clearing previous master:', clearError)
        return NextResponse.json(
          { error: 'Failed to clear previous master image' },
          { status: 500 }
        )
      }

      // Set the selected product image as the Shopify master image
      const { error: masterError } = await supabase
        .from('product_lifestyle_images')
        .update({ user_selected: true })
        .eq('id', selectedProductImageId)

      if (masterError) {
        console.error('Error setting master image:', masterError)
        return NextResponse.json(
          { error: 'Failed to set master image' },
          { status: 500 }
        )
      }

      // Record in lifestyle_image_selections for audit (master level)
      const { error: auditError } = await supabase
        .from('lifestyle_image_selections')
        .upsert({
          master_sku: masterSku,
          finish: null, // null finish = master level
          selected_image_id: selectedProductImageId,
          selection_reason: 'Set as master SKU image',
          selected_by: 'user', // TODO: Get actual user from session
          selected_at: new Date().toISOString(),
        }, {
          onConflict: 'master_sku,finish',
          ignoreDuplicates: false,
        })

      if (auditError) {
        // Log but don't fail - audit is secondary
        console.error('Error recording master selection audit:', auditError)
      }

      return NextResponse.json({ success: true, action: 'use_for_master' })
    }

    return NextResponse.json(
      { error: 'Must specify either userSelected or useForMaster' },
      { status: 400 }
    )

  } catch (error) {
    console.error('Error in image select API:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
