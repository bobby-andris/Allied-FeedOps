import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

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

    // Handle use_for_master (product-level images)
    if (useForMaster) {
      // First, clear user_selected for all product images of this SKU
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

      // Then set the new master image
      const { error: masterError } = await supabase
        .from('product_lifestyle_images')
        .update({ user_selected: true })
        .eq('id', imageId)

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
          selected_image_id: imageId,
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
