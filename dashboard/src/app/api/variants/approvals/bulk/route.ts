import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

/**
 * POST /api/variants/approvals/bulk
 *
 * Bulk approve or reject multiple variants at once.
 *
 * Body:
 * {
 *   master_sku: string
 *   finishes: string[]          // List of finish names to update
 *   finish_codes?: string[]     // Optional: corresponding finish codes
 *   action: 'approve' | 'reject'
 *   title_approved?: boolean
 *   description_approved?: boolean
 *   image_approved?: boolean
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      master_sku,
      finishes,
      action,
      platform,
      title_approved,
      description_approved,
      image_approved,
    } = body

    // Validate required fields
    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    if (!finishes || !Array.isArray(finishes) || finishes.length === 0) {
      return NextResponse.json(
        { error: 'finishes array is required and must not be empty' },
        { status: 400 }
      )
    }

    if (!action || !['approve', 'reject'].includes(action)) {
      return NextResponse.json(
        { error: 'action must be "approve" or "reject"' },
        { status: 400 }
      )
    }

    if (platform && !['google', 'bing'].includes(platform)) {
      return NextResponse.json(
        { error: 'platform must be "google" or "bing" when provided' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Build the update data based on action
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString(),
    }

    if (action === 'approve') {
      // For approve, set all provided fields to true (or use explicit values)
      updateData.title_approved = title_approved !== undefined ? title_approved : true
      updateData.description_approved = description_approved !== undefined ? description_approved : true
      updateData.image_approved = image_approved !== undefined ? image_approved : true
      updateData.approval_status = 'approved'
    } else if (action === 'reject') {
      // For reject, set all provided fields to false (or use explicit values)
      updateData.title_approved = title_approved !== undefined ? title_approved : false
      updateData.description_approved = description_approved !== undefined ? description_approved : false
      updateData.image_approved = image_approved !== undefined ? image_approved : false
      updateData.approval_status = 'rejected'
    }

    // Process each finish
    const results: { finish: string; success: boolean; error?: string }[] = []
    const errors: string[] = []

    for (const finish of finishes) {
      try {
        // Check if record exists
        const { data: existing } = await supabase
          .from('variant_approvals')
          .select('id')
          .eq('master_sku', master_sku)
          .eq('finish', finish)
          .single()

        let result
        if (existing) {
          // Update existing record
          result = await supabase
            .from('variant_approvals')
            .update(updateData)
            .eq('master_sku', master_sku)
            .eq('finish', finish)
            .select()
            .single()
        } else {
          // Insert new record
          result = await supabase
            .from('variant_approvals')
            .insert({
              master_sku,
              finish,
              ...updateData,
              created_at: new Date().toISOString(),
            })
            .select()
            .single()
        }

        if (result.error) {
          results.push({ finish, success: false, error: result.error.message })
          errors.push(`${finish}: ${result.error.message}`)
        } else {
          results.push({ finish, success: true })
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        results.push({ finish, success: false, error: message })
        errors.push(`${finish}: ${message}`)
      }
    }

    // Return summary
    const successCount = results.filter(r => r.success).length
    const failCount = results.filter(r => !r.success).length

    if (failCount > 0 && successCount === 0) {
      return NextResponse.json(
        {
          error: 'All operations failed',
          details: errors,
          results,
        },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      message: `${action === 'approve' ? 'Approved' : 'Rejected'} ${successCount} ${platform ? `${platform.toUpperCase()} ` : ''}variant(s)${failCount > 0 ? `, ${failCount} failed` : ''}`,
      results,
      successCount,
      failCount,
    })
  } catch (error) {
    console.error('Error in bulk approval:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
