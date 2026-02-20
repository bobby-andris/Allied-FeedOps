import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4CampaignPerformance } from '@/lib/ga4/client'
import {
  getNormalizedForensicsPropertyId,
  resolveGa4DateWindow,
  type Ga4ShopifyReconciliationSummary,
} from '@/lib/ga4/forensics'
import { fetchShopifyOrderSnapshots } from '@/lib/shopify/value-signals'

function sanitizeInteger(input: string | null, fallback: number, max: number): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function buildEmptySummary(input: {
  propertyId: string
  startDate: string
  endDate: string
}): Ga4ShopifyReconciliationSummary {
  return {
    propertyId: input.propertyId,
    startDate: input.startDate,
    endDate: input.endDate,
    ga4Revenue: 0,
    shopifyRevenue: 0,
    revenueDelta: 0,
    revenueRatio: null,
    orderCount: 0,
    generatedAt: new Date().toISOString(),
  }
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const propertyId = getNormalizedForensicsPropertyId(params.get('property_id') ?? undefined)
  const startDate = params.get('start_date') ?? '30daysAgo'
  const endDate = params.get('end_date') ?? 'yesterday'
  const maxOrders = sanitizeInteger(params.get('max_orders'), 3000, 10000)

  const warnings: string[] = []
  const resolvedWindow = resolveGa4DateWindow(startDate, endDate)
  const summary = buildEmptySummary({
    propertyId,
    startDate: resolvedWindow.startDate,
    endDate: resolvedWindow.endDate,
  })

  try {
    const ga4 = await fetchGa4CampaignPerformance({
      propertyId,
      startDate,
      endDate,
      limit: 5000,
    })
    summary.ga4Revenue = Number(
      ga4.rows.reduce((sum, row) => sum + row.purchaseRevenue, 0).toFixed(4)
    )
  } catch (error) {
    warnings.push(`GA4 revenue unavailable: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }

  try {
    const orders = await fetchShopifyOrderSnapshots({
      lookbackDays: resolvedWindow.lookbackDays + 2,
      maxOrders,
    })

    const startMs = resolvedWindow.start.getTime()
    const endMs = resolvedWindow.end.getTime() + 24 * 60 * 60 * 1000 - 1
    const windowOrders = orders.filter((order) => {
      const createdAtMs = new Date(order.createdAt).getTime()
      return createdAtMs >= startMs && createdAtMs <= endMs
    })

    summary.orderCount = windowOrders.length
    summary.shopifyRevenue = Number(
      windowOrders.reduce((sum, order) => sum + order.totalRevenue, 0).toFixed(4)
    )
  } catch (error) {
    warnings.push(
      `Shopify revenue unavailable: ${error instanceof Error ? error.message : 'Unknown error'}`
    )
  }

  summary.revenueDelta = Number((summary.ga4Revenue - summary.shopifyRevenue).toFixed(4))
  summary.revenueRatio =
    summary.shopifyRevenue > 0 ? Number((summary.ga4Revenue / summary.shopifyRevenue).toFixed(6)) : null

  return NextResponse.json({
    ...summary,
    available: warnings.length === 0,
    warnings,
  })
}
