import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

interface GmcProductStatus {
  id: number
  gmc_offer_id: string
  master_sku: string | null
  offer_title: string | null
  status: string
  item_issues: GmcItemIssue[] | null
  issue_count: number
  disapproval_count: number
  synced_at: string
  sync_job_id: string | null
}

interface GmcItemIssue {
  code: string
  canonical_attribute: string
  severity: string
  resolution: string
  applicable_contexts: string[]
}

interface GmcStatusResponse {
  products: GmcProductStatus[]
  summary: {
    total: number
    disapproved: number
    limited: number
    eligible: number
  }
  last_synced: string | null
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl
    const masterSku = searchParams.get('master_sku')
    const statusFilter = searchParams.get('status')
    const limit = Math.min(parseInt(searchParams.get('limit') || '200', 10), 500)

    const supabase = await createClient()

    // Build query — always read from cache, never call Merchant API directly
    let query = supabase
      .from('gmc_product_status')
      .select('*')
      .order('disapproval_count', { ascending: false })
      .order('synced_at', { ascending: false })
      .limit(limit)

    if (masterSku) {
      query = query.eq('master_sku', masterSku)
    }

    if (statusFilter) {
      query = query.eq('status', statusFilter)
    }

    const { data: products, error } = await query

    if (error) {
      console.error('GMC status query error:', error)
      return NextResponse.json(
        { error: 'Failed to fetch GMC status', detail: error.message },
        { status: 500 }
      )
    }

    const rows = (products || []) as GmcProductStatus[]

    // Compute summary counts
    const disapproved = rows.filter((r) => r.status === 'disapproved').length
    const limited = rows.filter((r) => r.status === 'limited').length
    const eligible = rows.filter((r) => r.status === 'approved').length

    // Find most recent sync timestamp
    const lastSynced =
      rows.length > 0
        ? rows.reduce((latest, r) => {
            return r.synced_at > latest ? r.synced_at : latest
          }, rows[0].synced_at)
        : null

    const response: GmcStatusResponse = {
      products: rows,
      summary: {
        total: rows.length,
        disapproved,
        limited,
        eligible,
      },
      last_synced: lastSynced,
    }

    return NextResponse.json(response)
  } catch (err) {
    console.error('GMC status route error:', err)
    return NextResponse.json(
      { error: 'Internal server error', detail: String(err) },
      { status: 500 }
    )
  }
}
