import { NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'

export interface LabelProfitability {
  custom_label_0: string
  days_of_data: number
  total_spend: number
  total_revenue: number
  roas: number
  total_impressions: number
  total_conversions: number
}

export async function GET() {
  try {
    const supabase = createAdminClient()

    // Query funnel_snapshots_daily for label-level profitability
    // (Plan references label_tier_daily_snapshot but actual table is funnel_snapshots_daily)
    const { data, error } = await supabase.rpc('exec_sql', {
      query: `
        SELECT
          custom_label_0,
          COUNT(DISTINCT snapshot_date) as days_of_data,
          SUM(cost_micros) / 1000000.0 as total_spend,
          SUM(conversions_value) as total_revenue,
          CASE WHEN SUM(cost_micros) > 0
            THEN SUM(conversions_value) / (SUM(cost_micros) / 1000000.0)
            ELSE 0 END as roas,
          SUM(impressions) as total_impressions,
          SUM(conversions) as total_conversions
        FROM funnel_snapshots_daily
        WHERE snapshot_date >= NOW() - INTERVAL '30 days'
        GROUP BY custom_label_0
        ORDER BY SUM(cost_micros) DESC
      `,
    })

    // If rpc doesn't work, fall back to direct query approach
    if (error) {
      // Try direct table query as fallback
      const { data: snapshots, error: fallbackError } = await supabase
        .from('funnel_snapshots_daily')
        .select('custom_label_0, snapshot_date, cost_micros, conversions_value, impressions, conversions')
        .gte('snapshot_date', new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])

      if (fallbackError) {
        console.error('Label profitability query failed:', fallbackError)
        return NextResponse.json({ error: fallbackError.message, labels: [] }, { status: 200 })
      }

      // Aggregate in-memory
      const labelMap = new Map<string, {
        dates: Set<string>
        totalSpend: number
        totalRevenue: number
        totalImpressions: number
        totalConversions: number
      }>()

      for (const row of snapshots ?? []) {
        const label = row.custom_label_0
        if (!labelMap.has(label)) {
          labelMap.set(label, {
            dates: new Set(),
            totalSpend: 0,
            totalRevenue: 0,
            totalImpressions: 0,
            totalConversions: 0,
          })
        }
        const entry = labelMap.get(label)!
        entry.dates.add(row.snapshot_date)
        entry.totalSpend += Number(row.cost_micros ?? 0) / 1_000_000
        entry.totalRevenue += Number(row.conversions_value ?? 0)
        entry.totalImpressions += Number(row.impressions ?? 0)
        entry.totalConversions += Number(row.conversions ?? 0)
      }

      const labels: LabelProfitability[] = Array.from(labelMap.entries())
        .map(([label, entry]) => ({
          custom_label_0: label,
          days_of_data: entry.dates.size,
          total_spend: entry.totalSpend,
          total_revenue: entry.totalRevenue,
          roas: entry.totalSpend > 0 ? entry.totalRevenue / entry.totalSpend : 0,
          total_impressions: entry.totalImpressions,
          total_conversions: entry.totalConversions,
        }))
        .sort((a, b) => b.total_spend - a.total_spend)

      return NextResponse.json({ labels })
    }

    return NextResponse.json({ labels: data ?? [] })
  } catch (err) {
    console.error('Label profitability failed:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error', labels: [] },
      { status: 200 }
    )
  }
}
