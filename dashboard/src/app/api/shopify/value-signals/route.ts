import { NextRequest, NextResponse } from 'next/server'
import {
  fetchShopifyValueSignalsWithLabelMapping,
} from '@/lib/shopify/value-signals'

function sanitizeInteger(input: string | null, fallback: number, max: number): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const lookbackDays = sanitizeInteger(params.get('lookback_days'), 90, 365)
    const maxOrders = sanitizeInteger(params.get('max_orders'), 500, 2000)

    const summary = await fetchShopifyValueSignalsWithLabelMapping({
      lookbackDays,
      maxOrders,
    })
    const { mappedSkuCount, skuCountInOrders, ...publicSummary } = summary

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      lookback_days: lookbackDays,
      max_orders: maxOrders,
      mapped_sku_count: mappedSkuCount,
      sku_count_in_orders: skuCountInOrders,
      ...publicSummary,
    })
  } catch (error) {
    console.error('Shopify value signals fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
