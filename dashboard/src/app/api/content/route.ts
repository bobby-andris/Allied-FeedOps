import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const sku = searchParams.get('sku')
  const platform = searchParams.get('platform')

  if (!sku) {
    return NextResponse.json(
      { error: 'sku parameter is required' },
      { status: 400 }
    )
  }

  try {
    const supabase = await createClient()
    
    let query = supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', sku)

    if (platform) {
      query = query.eq('platform', platform)
    }

    const { data: content, error: contentError } = await query

    if (contentError) {
      return NextResponse.json({ error: contentError.message }, { status: 500 })
    }

    // Also get images
    const { data: images, error: imagesError } = await supabase
      .from('generated_images')
      .select('*')
      .eq('master_sku', sku)
      .order('variation_index', { ascending: true })

    if (imagesError) {
      console.error('Failed to fetch images:', imagesError)
    }

    // Get approval status
    const { data: approval } = await supabase
      .from('sku_approvals')
      .select('*')
      .eq('master_sku', sku)
      .single()

    return NextResponse.json({
      content: content || [],
      images: images || [],
      approval: approval || null,
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
