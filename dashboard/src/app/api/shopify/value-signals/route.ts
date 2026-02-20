import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  fetchShopifyOrderSnapshots,
  summarizeShopifyOrders,
} from '@/lib/shopify/value-signals'

function sanitizeInteger(input: string | null, fallback: number, max: number): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function resolveCustomLabel0(value: unknown, fallbackCategory: string | null): string | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const objectValue = value as Record<string, unknown>
    const direct =
      objectValue.customLabel0 ??
      objectValue.custom_label_0 ??
      objectValue.customlabel0 ??
      null
    if (typeof direct === 'string' && direct.trim()) {
      return direct.trim()
    }
  }

  if (typeof fallbackCategory === 'string' && fallbackCategory.trim()) {
    return fallbackCategory.trim()
  }

  return null
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const lookbackDays = sanitizeInteger(params.get('lookback_days'), 90, 365)
    const maxOrders = sanitizeInteger(params.get('max_orders'), 500, 2000)

    const orders = await fetchShopifyOrderSnapshots({
      lookbackDays,
      maxOrders,
    })

    const skus = Array.from(
      new Set(
        orders.flatMap((order) => order.lineItems.map((lineItem) => lineItem.sku)).filter(Boolean)
      )
    )

    const customLabelBySku: Record<string, string> = {}
    const supabase = createAdminClient()

    for (let index = 0; index < skus.length; index += 400) {
      const batch = skus.slice(index, index + 400)
      if (batch.length === 0) {
        continue
      }

      const { data, error } = await supabase
        .from('variant_index')
        .select('option_sku, custom_labels, product_category')
        .in('option_sku', batch)

      if (error) {
        throw error
      }

      for (const row of data ?? []) {
        const optionSku = row.option_sku
        if (!optionSku) {
          continue
        }
        const customLabel0 = resolveCustomLabel0(row.custom_labels, row.product_category ?? null)
        if (customLabel0) {
          customLabelBySku[optionSku] = customLabel0
        }
      }
    }

    const summary = summarizeShopifyOrders(orders, customLabelBySku)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      lookback_days: lookbackDays,
      max_orders: maxOrders,
      mapped_sku_count: Object.keys(customLabelBySku).length,
      sku_count_in_orders: skus.length,
      ...summary,
    })
  } catch (error) {
    console.error('Shopify value signals fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

