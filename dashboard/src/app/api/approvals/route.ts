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
    const validPlatforms = ['google', 'bing', 'shopify'] as const

    if (platform && !validPlatforms.includes(platform)) {
      return NextResponse.json(
        { error: `platform must be one of: ${validPlatforms.join(', ')}` },
        { status: 400 }
      )
    }

    // Build normalized patch object from request.
    const updateData: Partial<{
      title_approved: boolean | null
      description_approved: boolean | null
      image_approved: boolean | null
    }> = {}

    if (element !== undefined) {
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
      if (title_approved !== undefined) updateData.title_approved = normalizeApprovalValue(title_approved)
      if (description_approved !== undefined) updateData.description_approved = normalizeApprovalValue(description_approved)
      if (image_approved !== undefined) updateData.image_approved = normalizeApprovalValue(image_approved)
    }

    if (Object.keys(updateData).length === 0) {
      return NextResponse.json(
        { error: 'No approval fields provided' },
        { status: 400 }
      )
    }

    const { data: existing, error: existingError } = await supabase
      .from('sku_approvals')
      .select('*')
      .eq('master_sku', master_sku)
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
    const nextStatus = deriveApprovalStatus(nextState)

    const fieldsChanged = (['title_approved', 'description_approved', 'image_approved'] as const).some(
      (field) => updateData[field] !== undefined && updateData[field] !== currentState[field]
    )

    if (existing && !fieldsChanged && currentStatus === nextStatus) {
      return NextResponse.json({
        data: { ...existing, approval_status: currentStatus },
        state: 'no_change',
        idempotent: true,
      })
    }

    // Only transition title/description approved content on first approval transition.
    const transitionContentTypes: Array<'title' | 'description'> = []
    if (currentState.title_approved !== true && nextState.title_approved === true) {
      transitionContentTypes.push('title')
    }
    if (currentState.description_approved !== true && nextState.description_approved === true) {
      transitionContentTypes.push('description')
    }

    const platformsToUpdate = platform ? [platform] : [...validPlatforms]
    const sourceRows = new Map<string, { id: string; candidate_content: string; approved_version: number | null }>()

    if (transitionContentTypes.length > 0) {
      const missingSources: string[] = []

      for (const ct of transitionContentTypes) {
        for (const p of platformsToUpdate) {
          const { data: gcRow, error: gcError } = await supabase
            .from('generated_content')
            .select('id, candidate_content, approved_version')
            .eq('master_sku', master_sku)
            .eq('platform', p)
            .eq('content_type', ct)
            .maybeSingle()

          if (gcError) {
            return NextResponse.json(
              {
                error: `Failed to load source content for approval: ${gcError.message}`,
                code: 'source_content_lookup_failed',
                step: 'approval_source_content_check',
                actionable_message:
                  'Retry approval. If this persists, check generated_content table access for this SKU.',
              },
              { status: 500 }
            )
          }

          if (!gcRow || !gcRow.candidate_content || gcRow.candidate_content.trim().length === 0) {
            missingSources.push(`${p}/${ct}`)
            continue
          }

          sourceRows.set(`${p}:${ct}`, {
            id: gcRow.id,
            candidate_content: gcRow.candidate_content,
            approved_version: gcRow.approved_version,
          })
        }
      }

      if (missingSources.length > 0) {
        return NextResponse.json(
          {
            error: 'Cannot approve content because source candidate content is missing.',
            code: 'missing_source_content',
            step: 'approval_source_content_check',
            actionable_message:
              'Regenerate the missing platform/content items first, then retry approval.',
            missing_requirements: missingSources,
          },
          { status: 409 }
        )
      }
    }

    const now = new Date().toISOString()
    const approvalPayload = {
      ...nextState,
      approval_status: nextStatus,
      approved_at: nextStatus === 'approved' ? now : null,
      updated_at: now,
    }

    let savedRecord
    if (existing) {
      const { data, error } = await supabase
        .from('sku_approvals')
        .update(approvalPayload)
        .eq('master_sku', master_sku)
        .select()
        .single()
      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }
      savedRecord = data
    } else {
      const { data, error } = await supabase
        .from('sku_approvals')
        .insert({
          master_sku,
          ...approvalPayload,
          created_at: now,
        })
        .select()
        .single()
      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }
      savedRecord = data
    }

    // Copy candidate content to approved content only for first-time approval transitions.
    for (const ct of transitionContentTypes) {
      for (const p of platformsToUpdate) {
        const source = sourceRows.get(`${p}:${ct}`)
        if (!source) continue

        await supabase
          .from('generated_content')
          .update({
            approved_content: source.candidate_content,
            approved_at: now,
            approved_version: (source.approved_version || 0) + 1,
            updated_at: now,
          })
          .eq('id', source.id)
      }
    }

    return NextResponse.json({
      data: { ...savedRecord, approval_status: nextStatus },
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

function normalizeApprovalValue(value: unknown): boolean | null {
  if (value === true || value === 1 || value === '1') return true
  if (value === false || value === 0 || value === '0') return false
  return null
}

function deriveApprovalStatus(state: {
  title_approved: boolean | null
  description_approved: boolean | null
  image_approved: boolean | null
}): 'pending' | 'approved' | 'rejected' {
  if (state.title_approved === true && state.description_approved === true && state.image_approved === true) {
    return 'approved'
  }
  if (state.title_approved === false || state.description_approved === false || state.image_approved === false) {
    return 'rejected'
  }
  return 'pending'
}
