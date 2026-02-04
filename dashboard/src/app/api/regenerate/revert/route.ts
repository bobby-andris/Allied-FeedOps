import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

interface RevertRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  history_id: string  // The regeneration_history entry to revert to
}

export async function POST(request: NextRequest) {
  try {
    const body: RevertRequest = await request.json()
    const { master_sku, content_type, platform, history_id } = body

    // Validate required fields
    if (!master_sku || !content_type || !platform || !history_id) {
      return NextResponse.json(
        { error: 'Missing required fields: master_sku, content_type, platform, history_id' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Get the history entry to revert to
    const { data: historyEntry, error: historyError } = await supabase
      .from('regeneration_history')
      .select('previous_content, new_content')
      .eq('id', history_id)
      .single()

    if (historyError || !historyEntry) {
      return NextResponse.json(
        { error: 'History entry not found' },
        { status: 404 }
      )
    }

    // Get the previous content from the history entry
    const revertContent = historyEntry.previous_content

    if (!revertContent) {
      return NextResponse.json(
        { error: 'No previous content to revert to' },
        { status: 400 }
      )
    }

    // Get current content record
    const { data: currentContent, error: currentError } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('platform', platform)
      .eq('content_type', content_type)
      .eq('is_current', true)
      .single()

    if (currentError && currentError.code !== 'PGRST116') {
      console.error('Error fetching current content:', currentError)
      return NextResponse.json(
        { error: 'Failed to fetch current content' },
        { status: 500 }
      )
    }

    const currentVersion = currentContent?.version || 0

    // Mark current content as not current
    if (currentContent) {
      await supabase
        .from('generated_content')
        .update({ is_current: false })
        .eq('id', currentContent.id)
    }

    // Insert reverted content as new version
    const { data: newContentRecord, error: insertError } = await supabase
      .from('generated_content')
      .upsert({
        master_sku,
        platform,
        content_type,
        candidate_content: revertContent,
        baseline_content: currentContent?.baseline_content,
        version: currentVersion + 1,
        is_current: true,
      }, {
        onConflict: 'master_sku,platform,content_type',
      })
      .select()
      .single()

    if (insertError) {
      console.error('Failed to save reverted content:', insertError)
      return NextResponse.json(
        { error: 'Failed to save reverted content' },
        { status: 500 }
      )
    }

    // Log the revert action to history
    await supabase
      .from('regeneration_history')
      .insert({
        master_sku,
        content_type,
        platform,
        mode: 'simple', // Revert is treated as a simple regeneration
        feedback_text: `Reverted to version from history entry ${history_id}`,
        previous_content: currentContent?.candidate_content,
        new_content: revertContent,
        model_version: 'revert',
        quality_score_before: currentContent?.quality_score,
        generated_content_id: newContentRecord?.id,
      })

    return NextResponse.json({
      success: true,
      content: revertContent,
      version: currentVersion + 1,
      reverted_from_history_id: history_id,
    })
  } catch (error) {
    console.error('Revert error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
