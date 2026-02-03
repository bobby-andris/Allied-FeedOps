import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

// GET /api/variants/approvals?master_sku=1051
// Returns all variant approvals for a SKU
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const masterSku = searchParams.get('master_sku')

  if (!masterSku) {
    return NextResponse.json(
      { error: 'master_sku is required' },
      { status: 400 }
    )
  }

  try {
    const supabase = await createClient()
    
    const { data, error } = await supabase
      .from('variant_approvals')
      .select('*')
      .eq('master_sku', masterSku)
      .order('finish', { ascending: true })

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

// POST /api/variants/approvals
// Create or update a variant approval with all fields
// Body: { master_sku, finish, title_approved?, description_approved?, image_approved?, notes? }
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { master_sku, finish, ...approvalData } = body

    if (!master_sku || !finish) {
      return NextResponse.json(
        { error: 'master_sku and finish are required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Check if record exists
    const { data: existing } = await supabase
      .from('variant_approvals')
      .select('id')
      .eq('master_sku', master_sku)
      .eq('finish', finish)
      .single()

    let result
    if (existing) {
      // Update
      result = await supabase
        .from('variant_approvals')
        .update({
          ...approvalData,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .eq('finish', finish)
        .select()
        .single()
    } else {
      // Insert
      result = await supabase
        .from('variant_approvals')
        .insert({
          master_sku,
          finish,
          ...approvalData,
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

    // Auto-derive approval_status
    const data = result.data
    const newStatus = deriveApprovalStatus(data)
    
    if (newStatus !== data.approval_status) {
      await supabase
        .from('variant_approvals')
        .update({ 
          approval_status: newStatus,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .eq('finish', finish)
    }

    return NextResponse.json({ data: { ...data, approval_status: newStatus } })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

// PATCH /api/variants/approvals
// Update specific approval fields for a variant
// Body: { master_sku, finish, element?, approved?, title_approved?, description_approved?, image_approved? }
export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { master_sku, finish, element, approved, title_approved, description_approved, image_approved } = body

    if (!master_sku || !finish) {
      return NextResponse.json(
        { error: 'master_sku and finish are required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()
    
    // Build the update object based on request format
    const updateData: Record<string, unknown> = {}
    
    if (element !== undefined) {
      // Legacy format: { element, approved }
      const validElements = ['title', 'description', 'image']
      if (!validElements.includes(element)) {
        return NextResponse.json(
          { error: 'element must be one of: title, description, image' },
          { status: 400 }
        )
      }
      updateData[`${element}_approved`] = approved
    } else {
      // Direct format: { title_approved?, description_approved?, image_approved? }
      if (title_approved !== undefined) updateData.title_approved = title_approved
      if (description_approved !== undefined) updateData.description_approved = description_approved
      if (image_approved !== undefined) updateData.image_approved = image_approved
    }

    if (Object.keys(updateData).length === 0) {
      return NextResponse.json(
        { error: 'No approval fields provided' },
        { status: 400 }
      )
    }

    // Upsert the approval
    const { data: existing } = await supabase
      .from('variant_approvals')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('finish', finish)
      .single()

    let result
    if (existing) {
      result = await supabase
        .from('variant_approvals')
        .update({
          ...updateData,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .eq('finish', finish)
        .select()
        .single()
    } else {
      result = await supabase
        .from('variant_approvals')
        .insert({
          master_sku,
          finish,
          ...updateData,
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

    // Auto-derive approval_status
    const data = result.data
    const newStatus = deriveApprovalStatus(data)

    if (newStatus !== data.approval_status) {
      await supabase
        .from('variant_approvals')
        .update({ 
          approval_status: newStatus,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
        .eq('finish', finish)
    }

    return NextResponse.json({ data: { ...data, approval_status: newStatus } })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

// Helper function to derive approval status from element approvals
function deriveApprovalStatus(data: {
  title_approved?: boolean | number | null
  description_approved?: boolean | number | null
  image_approved?: boolean | number | null
}): string {
  const titleApproved = data.title_approved === true || data.title_approved === 1
  const descApproved = data.description_approved === true || data.description_approved === 1
  const imageApproved = data.image_approved === true || data.image_approved === 1
  
  const titleRejected = data.title_approved === false || data.title_approved === 0
  const descRejected = data.description_approved === false || data.description_approved === 0
  const imageRejected = data.image_approved === false || data.image_approved === 0

  if (titleApproved && descApproved && imageApproved) {
    return 'approved'
  } else if (titleRejected || descRejected || imageRejected) {
    return 'rejected'
  }
  return 'pending'
}
