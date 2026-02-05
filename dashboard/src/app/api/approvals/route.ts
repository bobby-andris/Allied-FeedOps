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
  } catch {
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
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { master_sku, element, approved, title_approved, description_approved, image_approved, platform } = body

    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Build the update object based on request format
    // Supports two formats:
    // 1. Legacy: { master_sku, element, approved }
    // 2. Direct: { master_sku, title_approved?, description_approved?, image_approved? }
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
      .from('sku_approvals')
      .select('*')
      .eq('master_sku', master_sku)
      .single()

    let result
    if (existing) {
      result = await supabase
        .from('sku_approvals')
        .update({
          ...updateData,
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
          approved_at: newStatus === 'approved' ? new Date().toISOString() : null,
          updated_at: new Date().toISOString(),
        })
        .eq('master_sku', master_sku)
    }

    // ==========================================================================
    // Copy approved content to generated_content table
    // This locks the content so regeneration doesn't change what was approved
    // ==========================================================================
    const contentTypesToApprove: string[] = []

    // Determine which content types to lock based on what was approved
    const titleIsApproved = title_approved === true || (element === 'title' && approved === true)
    const descIsApproved = description_approved === true || (element === 'description' && approved === true)

    if (titleIsApproved) contentTypesToApprove.push('title')
    if (descIsApproved) contentTypesToApprove.push('description')

    if (contentTypesToApprove.length > 0) {
      // Determine which platforms to update
      // If platform specified, update only that platform; otherwise update all
      const platforms = platform ? [platform] : ['google', 'bing', 'shopify']

      for (const ct of contentTypesToApprove) {
        for (const p of platforms) {
          // Get current generated_content row
          const { data: gcRow } = await supabase
            .from('generated_content')
            .select('id, candidate_content, approved_version')
            .eq('master_sku', master_sku)
            .eq('platform', p)
            .eq('content_type', ct)
            .single()

          if (gcRow && gcRow.candidate_content) {
            // Copy candidate_content to approved_content
            await supabase
              .from('generated_content')
              .update({
                approved_content: gcRow.candidate_content,
                approved_at: new Date().toISOString(),
                approved_version: (gcRow.approved_version || 0) + 1,
                updated_at: new Date().toISOString(),
              })
              .eq('id', gcRow.id)
          }
        }
      }
    }

    return NextResponse.json({ data: { ...data, approval_status: newStatus } })
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
