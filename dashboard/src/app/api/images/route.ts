import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { image_id, master_sku, selected } = body

    if (!image_id || !master_sku) {
      return NextResponse.json(
        { error: 'image_id and master_sku are required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // If selecting an image, first unselect all other images for this SKU
    if (selected) {
      await supabase
        .from('generated_images')
        .update({ selected: false })
        .eq('master_sku', master_sku)
    }

    // Update the specific image
    const { data, error } = await supabase
      .from('generated_images')
      .update({ selected })
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
