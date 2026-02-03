import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const status = searchParams.get('status')
  const sku = searchParams.get('sku')
  const limit = parseInt(searchParams.get('limit') || '50')
  const offset = parseInt(searchParams.get('offset') || '0')

  try {
    const supabase = await createClient()
    
    let query = supabase
      .from('sku_approvals')
      .select('*')
      .order('created_at', { ascending: false })

    if (status) {
      query = query.eq('approval_status', status)
    }

    if (sku) {
      query = query.eq('master_sku', sku)
    }

    query = query.range(offset, offset + limit - 1)

    const { data, error } = await query

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ data })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { master_sku, ...approvalData } = body

    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Check if record exists
    const { data: existing } = await supabase
      .from('sku_approvals')
      .select('master_sku')
      .eq('master_sku', master_sku)
      .single()

    let result
    if (existing) {
      // Update
      result = await supabase
        .from('sku_approvals')
        .update({
          ...approvalData,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .select()
        .single()
    } else {
      // Insert
      result = await supabase
        .from('sku_approvals')
        .insert({
          master_sku,
          ...approvalData,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .select()
        .single()
    }

    if (result.error) {
      return NextResponse.json({ error: result.error.message }, { status: 500 })
    }

    return NextResponse.json({ data: result.data })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { master_sku, element, approved } = body

    if (!master_sku || !element) {
      return NextResponse.json(
        { error: 'master_sku and element are required' },
        { status: 400 }
      )
    }

    const validElements = ['title', 'description', 'image']
    if (!validElements.includes(element)) {
      return NextResponse.json(
        { error: 'element must be one of: title, description, image' },
        { status: 400 }
      )
    }

    const supabase = await createClient()
    const field = `${element}_approved`

    // Upsert the approval
    const { data: existing } = await supabase
      .from('sku_approvals')
      .select('*')
      .eq('master_sku', master_sku)
      .single()

    let result
    if (existing) {
      result = await supabase
        .from('sku_approvals')
        .update({
          [field]: approved,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .select()
        .single()
    } else {
      result = await supabase
        .from('sku_approvals')
        .insert({
          master_sku,
          [field]: approved,
          approval_status: 'pending',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .select()
        .single()
    }

    if (result.error) {
      return NextResponse.json({ error: result.error.message }, { status: 500 })
    }

    // Auto-derive approval_status based on element approvals
    const data = result.data
    let newStatus = 'pending'
    
    if (data.title_approved && data.description_approved && data.image_approved) {
      newStatus = 'approved'
    } else if (data.title_approved === false || data.description_approved === false || data.image_approved === false) {
      newStatus = 'rejected'
    }

    if (newStatus !== data.approval_status) {
      await supabase
        .from('sku_approvals')
        .update({ 
          approval_status: newStatus,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
    }

    return NextResponse.json({ data: { ...data, approval_status: newStatus } })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
