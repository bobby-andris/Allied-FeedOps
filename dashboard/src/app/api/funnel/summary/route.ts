import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

interface ConfirmedSample {
  checked: number
  matched: number
  last_run: string | null
}

interface FunnelSummary {
  funnel: {
    total_catalog: number
    has_generated: number
    approved: number
    published: number
    confirmed_sample: ConfirmedSample | null
  }
  generated_at: string
}

/**
 * GET /api/funnel/summary
 *
 * Returns 5-stage SKU coverage funnel counts:
 *   1. total_catalog  — COUNT(DISTINCT master_sku) FROM variant_index
 *   2. has_generated  — COUNT(DISTINCT master_sku) FROM generated_content
 *   3. approved       — COUNT(*) FROM sku_approvals WHERE approval_status = 'approved'
 *   4. published      — COUNT(DISTINCT master_sku) FROM publish_events WHERE status='success' AND action='publish'
 *   5. confirmed_sample — static result from DIAG-04 spot-check (null until Plan 03 runs)
 *
 * Uses COUNT(DISTINCT master_sku) — NOT row counts — to avoid inflating numbers
 * when multiple content rows exist per SKU (title, description, 3 platforms = 6 rows/SKU).
 */
export async function GET() {
  try {
    const supabase = await createClient()

    // Run all four Supabase queries in parallel using raw SQL via RPC-style execute
    // The JS client doesn't natively support COUNT(DISTINCT), so we use select with
    // head: true and count: 'exact' for approximate, OR fetch distinct rows and count in JS.
    // For accuracy with large tables (variant_index: 72K rows), we use the .rpc() pattern.
    // Fallback: fetch distinct master_sku values and count — acceptable for stage 2-4 (smaller sets).
    // For stage 1 (variant_index 72K), we use a targeted approach.

    const [
      catalogResult,
      generatedResult,
      approvedResult,
      publishedResult,
    ] = await Promise.all([
      // Stage 1: Total catalog — distinct master_skus in variant_index
      supabase
        .from('variant_index')
        .select('master_sku', { count: 'exact', head: false })
        .limit(100000), // fetch for dedup in JS (72K rows, ~2MB — acceptable for diagnostic)

      // Stage 2: Has generated content — distinct master_skus in generated_content
      supabase
        .from('generated_content')
        .select('master_sku', { count: 'exact', head: false })
        .limit(10000),

      // Stage 3: Approved — sku_approvals with approval_status = 'approved'
      supabase
        .from('sku_approvals')
        .select('master_sku', { count: 'exact', head: false })
        .eq('approval_status', 'approved')
        .limit(10000),

      // Stage 4: Published — distinct master_skus with successful publish event
      supabase
        .from('publish_events')
        .select('master_sku', { count: 'exact', head: false })
        .eq('status', 'success')
        .eq('action', 'publish')
        .limit(10000),
    ])

    // Count distinct master_skus (dedup in JS since Supabase JS client lacks COUNT DISTINCT)
    const totalCatalog = new Set((catalogResult.data || []).map((r) => r.master_sku)).size
    const hasGenerated = new Set((generatedResult.data || []).map((r) => r.master_sku)).size
    const approved = new Set((approvedResult.data || []).map((r) => r.master_sku)).size
    const published = new Set((publishedResult.data || []).map((r) => r.master_sku)).size

    // Stage 5: Confirmed sample — read from spot-check results file if it exists
    // This file is produced by Plan 03 (DIAG-04 spot-check script)
    let confirmedSample: ConfirmedSample | null = null
    try {
      const spotCheckPath = path.join(
        process.cwd(),
        '../.planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json'
      )
      if (fs.existsSync(spotCheckPath)) {
        const raw = fs.readFileSync(spotCheckPath, 'utf-8')
        const parsed = JSON.parse(raw)
        confirmedSample = {
          checked: parsed.summary?.total_checked ?? 0,
          matched: parsed.summary?.total_matched ?? 0,
          last_run: parsed.run_timestamp ?? null,
        }
      }
    } catch {
      // File missing or malformed — leave as null
      confirmedSample = null
    }

    const response: FunnelSummary = {
      funnel: {
        total_catalog: totalCatalog,
        has_generated: hasGenerated,
        approved,
        published,
        confirmed_sample: confirmedSample,
      },
      generated_at: new Date().toISOString(),
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Funnel summary API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
