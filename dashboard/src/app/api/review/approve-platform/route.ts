import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const { master_sku, platform } = await request.json()
    if (!master_sku || !platform) {
      return NextResponse.json({ error: 'master_sku and platform required' }, { status: 400 })
    }

    const validPlatforms = ['google', 'bing', 'shopify']
    if (!validPlatforms.includes(platform)) {
      return NextResponse.json({ error: 'Invalid platform. Must be google, bing, or shopify.' }, { status: 400 })
    }

    const supabase = await createClient()

    // Fetch rows where candidate_content exists and approved_content is not yet set
    const { data: contentRows, error: fetchError } = await supabase
      .from('generated_content')
      .select('id, candidate_content')
      .eq('master_sku', master_sku)
      .eq('platform', platform)
      .is('approved_content', null)
      .not('candidate_content', 'is', null)

    if (fetchError) {
      console.error('approve-platform: fetch error', fetchError)
      return NextResponse.json({ error: fetchError.message }, { status: 500 })
    }

    // Copy candidate_content to approved_content for each unapproved row
    if (contentRows && contentRows.length > 0) {
      const now = new Date().toISOString()
      for (const row of contentRows) {
        const { error: updateError } = await supabase
          .from('generated_content')
          .update({ approved_content: row.candidate_content, approved_at: now })
          .eq('id', row.id)

        if (updateError) {
          console.error('approve-platform: update error', updateError)
          // Continue to try to approve remaining rows
        }
      }
    }

    // Update sku_approvals to reflect approval
    const approvalUpdate: Record<string, boolean | string> = {
      title_approved: true,
      description_approved: true,
      approval_status: 'approved',
    }
    if (platform === 'shopify') {
      approvalUpdate.image_approved = true
    }

    const { error: upsertError } = await supabase
      .from('sku_approvals')
      .upsert(
        { master_sku, ...approvalUpdate, updated_at: new Date().toISOString() },
        { onConflict: 'master_sku' },
      )

    if (upsertError) {
      console.error('approve-platform: upsert error', upsertError)
      return NextResponse.json({ error: upsertError.message }, { status: 500 })
    }

    return NextResponse.json({ success: true, master_sku, platform })
  } catch (error) {
    console.error('approve-platform: unhandled error', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}
