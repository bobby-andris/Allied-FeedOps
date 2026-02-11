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
  } catch {
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
    const { data: existing, error: existingError } = await supabase
      .from('variant_approvals')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('finish', finish)
      .maybeSingle()

    if (existingError) {
      return NextResponse.json({ error: existingError.message }, { status: 500 })
    }

    const updateData: Partial<{
      title_approved: boolean | null
      description_approved: boolean | null
      image_approved: boolean | null
      notes: string | null
    }> = {}

    if (approvalData.title_approved !== undefined) {
      updateData.title_approved = normalizeApprovalValue(approvalData.title_approved)
    }
    if (approvalData.description_approved !== undefined) {
      updateData.description_approved = normalizeApprovalValue(approvalData.description_approved)
    }
    if (approvalData.image_approved !== undefined) {
      updateData.image_approved = normalizeApprovalValue(approvalData.image_approved)
    }
    if (approvalData.notes !== undefined) {
      updateData.notes = approvalData.notes
    }

    const currentState = {
      title_approved: normalizeApprovalValue(existing?.title_approved),
      description_approved: normalizeApprovalValue(existing?.description_approved),
      image_approved: normalizeApprovalValue(existing?.image_approved),
    }
    const nextState = {
      title_approved:
        updateData.title_approved !== undefined ? updateData.title_approved : currentState.title_approved,
      description_approved:
        updateData.description_approved !== undefined
          ? updateData.description_approved
          : currentState.description_approved,
      image_approved:
        updateData.image_approved !== undefined ? updateData.image_approved : currentState.image_approved,
    }
    const currentStatus = existing?.approval_status || deriveApprovalStatus(currentState)
    const newStatus = deriveApprovalStatus(nextState)

    const fieldsChanged = (['title_approved', 'description_approved', 'image_approved'] as const).some(
      (field) => updateData[field] !== undefined && updateData[field] !== currentState[field]
    ) || (updateData.notes !== undefined && updateData.notes !== existing?.notes)

    if (existing && !fieldsChanged && currentStatus === newStatus) {
      return NextResponse.json({
        data: { ...existing, approval_status: currentStatus },
        state: 'no_change',
        idempotent: true,
      })
    }

    let result
    if (existing) {
      // Update
      result = await supabase
        .from('variant_approvals')
        .update({
          ...updateData,
          approval_status: newStatus,
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
          ...updateData,
          approval_status: newStatus,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .select()
        .single()
    }

    if (result.error) {
      return NextResponse.json({ error: result.error.message }, { status: 500 })
    }

    return NextResponse.json({
      data: { ...result.data, approval_status: newStatus },
      state: 'updated',
      idempotent: false,
    })
  } catch {
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
    const updateData: Partial<{
      title_approved: boolean | null
      description_approved: boolean | null
      image_approved: boolean | null
    }> = {}

    if (element !== undefined) {
      // Legacy format: { element, approved }
      const validElements = ['title', 'description', 'image']
      if (!validElements.includes(element)) {
        return NextResponse.json(
          { error: 'element must be one of: title, description, image' },
          { status: 400 }
        )
      }
      if (approved === undefined) {
        return NextResponse.json(
          { error: 'approved is required when element is provided' },
          { status: 400 }
        )
      }
      updateData[`${element}_approved` as keyof typeof updateData] = normalizeApprovalValue(approved)
    } else {
      // Direct format: { title_approved?, description_approved?, image_approved? }
      if (title_approved !== undefined) updateData.title_approved = normalizeApprovalValue(title_approved)
      if (description_approved !== undefined) {
        updateData.description_approved = normalizeApprovalValue(description_approved)
      }
      if (image_approved !== undefined) updateData.image_approved = normalizeApprovalValue(image_approved)
    }

    if (Object.keys(updateData).length === 0) {
      return NextResponse.json(
        { error: 'No approval fields provided' },
        { status: 400 }
      )
    }

    // Upsert the approval
    const { data: existing, error: existingError } = await supabase
      .from('variant_approvals')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('finish', finish)
      .maybeSingle()

    if (existingError) {
      return NextResponse.json({ error: existingError.message }, { status: 500 })
    }

    const currentState = {
      title_approved: normalizeApprovalValue(existing?.title_approved),
      description_approved: normalizeApprovalValue(existing?.description_approved),
      image_approved: normalizeApprovalValue(existing?.image_approved),
    }
    const nextState = {
      title_approved:
        updateData.title_approved !== undefined ? updateData.title_approved : currentState.title_approved,
      description_approved:
        updateData.description_approved !== undefined
          ? updateData.description_approved
          : currentState.description_approved,
      image_approved:
        updateData.image_approved !== undefined ? updateData.image_approved : currentState.image_approved,
    }
    const currentStatus = existing?.approval_status || deriveApprovalStatus(currentState)
    const newStatus = deriveApprovalStatus(nextState)

    const fieldsChanged = (['title_approved', 'description_approved', 'image_approved'] as const).some(
      (field) => updateData[field] !== undefined && updateData[field] !== currentState[field]
    )

    if (existing && !fieldsChanged && currentStatus === newStatus) {
      return NextResponse.json({
        data: { ...existing, approval_status: currentStatus },
        state: 'no_change',
        idempotent: true,
      })
    }

    let result
    if (existing) {
      result = await supabase
        .from('variant_approvals')
        .update({
          ...updateData,
          approval_status: newStatus,
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
          approval_status: newStatus,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .select()
        .single()
    }

    if (result.error) {
      return NextResponse.json({ error: result.error.message }, { status: 500 })
    }

    return NextResponse.json({
      data: { ...result.data, approval_status: newStatus },
      state: 'updated',
      idempotent: false,
    })
  } catch {
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
  const normalizedTitle = normalizeApprovalValue(data.title_approved)
  const normalizedDescription = normalizeApprovalValue(data.description_approved)
  const normalizedImage = normalizeApprovalValue(data.image_approved)

  if (normalizedTitle === true && normalizedDescription === true && normalizedImage === true) {
    return 'approved'
  } else if (normalizedTitle === false || normalizedDescription === false || normalizedImage === false) {
    return 'rejected'
  }
  return 'pending'
}

function normalizeApprovalValue(value: unknown): boolean | null {
  if (value === true || value === 1 || value === '1') return true
  if (value === false || value === 0 || value === '0') return false
  return null
}
