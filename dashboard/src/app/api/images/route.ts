import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { image_id, master_sku, selected, finish, imageType } = body

    if (!image_id || !master_sku || !imageType) {
      return NextResponse.json(
        { error: 'image_id, master_sku, and imageType are required' },
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

    // If selecting an image, first unselect all other images at the same level
    if (selected) {
      const clearQuery = supabase
        .from(tableName)
        .update({ user_selected: false })
        .eq('master_sku', master_sku)

      if (imageType === 'variant' && finish) {
        // Clear only images for this specific finish (variant level)
        clearQuery.eq('finish', finish)
      }

      await clearQuery

      // Record selection in audit table
      await supabase
        .from('lifestyle_image_selections')
        .upsert({
          master_sku,
          finish: finish || null,
          selected_image_id: image_id,
          selected_at: new Date().toISOString(),
          selected_by: 'dashboard_user', // TODO: Get from auth when available
        }, {
          onConflict: 'master_sku,finish',
          ignoreDuplicates: false,
        })
    }

    // Update the specific image
    const { data, error } = await supabase
      .from(tableName)
      .update({ user_selected: selected })
      .eq('id', image_id)
      .select()
      .single()

    if (error) {
      console.error('Error updating image:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true, data })
  } catch (error) {
    console.error('Images API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
