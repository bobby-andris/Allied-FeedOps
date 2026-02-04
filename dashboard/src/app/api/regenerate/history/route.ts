import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const sku = searchParams.get('sku')
  const contentType = searchParams.get('content_type')
  const platform = searchParams.get('platform')
  const limit = parseInt(searchParams.get('limit') || '10')

  if (!sku) {
    return NextResponse.json(
      { error: 'sku parameter is required' },
      { status: 400 }
    )
  }

  try {
    const supabase = await createClient()

    let query = supabase
      .from('regeneration_history')
      .select('*')
      .eq('master_sku', sku)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (contentType) {
      query = query.eq('content_type', contentType)
    }

    if (platform) {
      query = query.eq('platform', platform)
    }

    const { data: history, error } = await query

    if (error) {
      console.error('Failed to fetch regeneration history:', error)
      return NextResponse.json(
        { error: 'Failed to fetch regeneration history' },
        { status: 500 }
      )
    }

    return NextResponse.json({
      history: history || [],
      count: history?.length || 0,
    })
  } catch (error) {
    console.error('History fetch error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
