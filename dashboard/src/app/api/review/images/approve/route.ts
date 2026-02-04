import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { imageId, status, reason } = body

    if (!imageId || !status) {
      return NextResponse.json(
        { error: 'imageId and status are required' },
        { status: 400 }
      )
    }

    if (!['approved', 'rejected'].includes(status)) {
      return NextResponse.json(
        { error: 'status must be "approved" or "rejected"' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    const updateData: Record<string, unknown> = {
      approval_status: status,
    }

    if (status === 'approved') {
      updateData.approved_at = new Date().toISOString()
      updateData.approved_by = 'dashboard_user' // TODO: Get from auth when available
      updateData.rejection_reason = null
    } else if (status === 'rejected') {
      updateData.rejection_reason = reason || null
      updateData.approved_at = null
      updateData.approved_by = null
    }

    const { data, error } = await supabase
      .from('generated_images')
      .update(updateData)
      .eq('id', imageId)
      .select()
      .single()

    if (error) {
      console.error('Error updating image approval:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true, data })
  } catch (error) {
    console.error('Image approval API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
