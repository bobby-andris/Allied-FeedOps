/**
 * Google Ads API client wrapper for fetching shopping performance metrics.
 * 
 * Uses the google-ads-api npm package to query shopping_performance_view
 * for product-level metrics (impressions, clicks, conversions, etc.)
 */

import { GoogleAdsApi } from 'google-ads-api'

// Types for performance data
export interface DailyPerformance {
  date: string
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  conversionValue: number
  cost: number
  roas: number
}

export interface ProductPerformance {
  productItemId: string
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  conversionValue: number
  cost: number
  roas: number
  dailyData: DailyPerformance[]
}

// Lazy initialization to avoid errors when env vars are missing
let clientInstance: GoogleAdsApi | null = null

function getClient(): GoogleAdsApi {
  if (!clientInstance) {
    const clientId = process.env.GOOGLE_ADS_CLIENT_ID
    const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET
    const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN

    if (!clientId || !clientSecret || !developerToken) {
      throw new Error(
        'Missing Google Ads credentials. Required: GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN'
      )
    }

    clientInstance = new GoogleAdsApi({
      client_id: clientId,
      client_secret: clientSecret,
      developer_token: developerToken,
    })
  }
  return clientInstance
}

function getCustomer() {
  const client = getClient()
  
  const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID
  const loginCustomerId = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID
  const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN

  if (!customerId || !refreshToken) {
    throw new Error(
      'Missing Google Ads customer config. Required: GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_REFRESH_TOKEN'
    )
  }

  return client.Customer({
    customer_id: customerId,
    login_customer_id: loginCustomerId,
    refresh_token: refreshToken,
  })
}

/**
 * Escape single quotes in a string for safe GAQL query interpolation
 */
function escapeGaqlString(value: string): string {
  return value.replace(/'/g, "\\'")
}

/**
 * Format date as YYYY-MM-DD for GAQL queries
 */
function formatDate(date: Date): string {
  return date.toISOString().split('T')[0]
}

/**
 * Calculate date range based on range string (7d, 30d, 90d)
 */
export function getDateRange(range: string): { startDate: string; endDate: string } {
  const endDate = new Date()
  const startDate = new Date()
  
  switch (range) {
    case '7d':
      startDate.setDate(startDate.getDate() - 7)
      break
    case '30d':
      startDate.setDate(startDate.getDate() - 30)
      break
    case '90d':
      startDate.setDate(startDate.getDate() - 90)
      break
    default:
      startDate.setDate(startDate.getDate() - 30)
  }
  
  return {
    startDate: formatDate(startDate),
    endDate: formatDate(endDate),
  }
}

/**
 * Fetch shopping performance metrics for products matching the given Shopify product IDs.
 *
 * Queries all shopping performance data for the date range, then filters in memory
 * to match products. This approach handles large numbers of products efficiently
 * without building massive WHERE clauses.
 *
 * @param shopifyProductIds - Array of Shopify product IDs (e.g., ['4545063682180'])
 * @param startDate - Start date in YYYY-MM-DD format
 * @param endDate - End date in YYYY-MM-DD format
 * @returns Map of Shopify product ID to aggregated performance metrics
 */
export async function fetchShoppingPerformance(
  shopifyProductIds: string[],
  startDate: string,
  endDate: string
): Promise<Map<string, ProductPerformance>> {
  if (shopifyProductIds.length === 0) {
    return new Map()
  }

  const customer = getCustomer()
  const results = new Map<string, ProductPerformance>()

  // Create a Set for O(1) lookup of requested product IDs
  const requestedProductIds = new Set(shopifyProductIds)

  // Initialize results for all requested product IDs
  for (const productId of shopifyProductIds) {
    results.set(productId, createEmptyPerformance(productId))
  }

  // Query all shopping performance data for the date range
  // Filter by shopify_ prefix to only get Shopify products, then filter in memory
  const query = `
    SELECT
      segments.product_item_id,
      segments.date,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.conversions,
      metrics.conversions_value,
      metrics.cost_micros
    FROM shopping_performance_view
    WHERE
      segments.product_item_id LIKE 'shopify_%'
      AND segments.date BETWEEN '${startDate}' AND '${endDate}'
    ORDER BY segments.product_item_id, segments.date
  `

  try {
    const rows = await customer.query(query)

    // Group rows by Shopify product ID and aggregate
    const productData = new Map<string, { rows: Array<{ date: string; metrics: Record<string, number> }> }>()

    for (const row of rows) {
      const productItemId = (row.segments as { product_item_id?: string })?.product_item_id || ''
      const date = (row.segments as { date?: string })?.date || ''
      const metrics = row.metrics as Record<string, number | undefined> || {}

      // Extract Shopify product ID from offer ID (shopify_US_{productId}_{variantId})
      const shopifyProductId = extractShopifyProductId(productItemId)

      // Skip if not in our requested set (O(1) lookup)
      if (!shopifyProductId || !requestedProductIds.has(shopifyProductId)) {
        continue
      }

      if (!productData.has(shopifyProductId)) {
        productData.set(shopifyProductId, { rows: [] })
      }

      productData.get(shopifyProductId)!.rows.push({
        date,
        metrics: {
          impressions: Number(metrics.impressions || 0),
          clicks: Number(metrics.clicks || 0),
          ctr: Number(metrics.ctr || 0),
          conversions: Number(metrics.conversions || 0),
          conversions_value: Number(metrics.conversions_value || 0),
          cost_micros: Number(metrics.cost_micros || 0),
        },
      })
    }

    // Aggregate metrics for each product
    for (const [productId, data] of productData) {
      const performance = aggregatePerformance(productId, data.rows)
      results.set(productId, performance)
    }
  } catch (error) {
    console.error('Failed to fetch shopping performance from Google Ads:', error)
    throw error
  }

  return results
}

/**
 * Extract Shopify product ID from a GMC offer ID.
 * Format: shopify_US_{shopify_product_id}_{variant_id}
 */
function extractShopifyProductId(offerItemId: string): string | null {
  // Match pattern: shopify_US_{productId}_{variantId}
  // Case-insensitive for the prefix
  const match = offerItemId.match(/^shopify_[Uu][Ss]_(\d+)_\d+$/i)
  return match ? match[1] : null
}

/**
 * Create an empty performance result
 */
function createEmptyPerformance(productItemId: string): ProductPerformance {
  return {
    productItemId,
    impressions: 0,
    clicks: 0,
    ctr: 0,
    conversions: 0,
    conversionValue: 0,
    cost: 0,
    roas: 0,
    dailyData: [],
  }
}

/**
 * Aggregate daily metrics into a ProductPerformance object
 */
function aggregatePerformance(
  productItemId: string,
  rows: Array<{ date: string; metrics: Record<string, number> }>
): ProductPerformance {
  let totalImpressions = 0
  let totalClicks = 0
  let totalConversions = 0
  let totalConversionValue = 0
  let totalCostMicros = 0

  const dailyData: DailyPerformance[] = []

  // Aggregate by date (multiple variants may have same date)
  const dateMap = new Map<string, Record<string, number>>()

  for (const row of rows) {
    const { date, metrics } = row
    
    if (!dateMap.has(date)) {
      dateMap.set(date, {
        impressions: 0,
        clicks: 0,
        conversions: 0,
        conversions_value: 0,
        cost_micros: 0,
      })
    }

    const dayData = dateMap.get(date)!
    dayData.impressions += metrics.impressions
    dayData.clicks += metrics.clicks
    dayData.conversions += metrics.conversions
    dayData.conversions_value += metrics.conversions_value
    dayData.cost_micros += metrics.cost_micros

    totalImpressions += metrics.impressions
    totalClicks += metrics.clicks
    totalConversions += metrics.conversions
    totalConversionValue += metrics.conversions_value
    totalCostMicros += metrics.cost_micros
  }

  // Convert date map to daily data array
  for (const [date, metrics] of dateMap) {
    const cost = metrics.cost_micros / 1_000_000
    const ctr = metrics.impressions > 0 ? metrics.clicks / metrics.impressions : 0
    const roas = cost > 0 ? metrics.conversions_value / cost : 0

    dailyData.push({
      date,
      impressions: metrics.impressions,
      clicks: metrics.clicks,
      ctr,
      conversions: metrics.conversions,
      conversionValue: metrics.conversions_value,
      cost,
      roas,
    })
  }

  // Sort daily data by date
  dailyData.sort((a, b) => a.date.localeCompare(b.date))

  // Calculate aggregate metrics
  const totalCost = totalCostMicros / 1_000_000
  const ctr = totalImpressions > 0 ? totalClicks / totalImpressions : 0
  const roas = totalCost > 0 ? totalConversionValue / totalCost : 0

  return {
    productItemId,
    impressions: totalImpressions,
    clicks: totalClicks,
    ctr,
    conversions: totalConversions,
    conversionValue: totalConversionValue,
    cost: totalCost,
    roas,
    dailyData,
  }
}

/**
 * Check if Google Ads API is configured
 */
export function isGoogleAdsConfigured(): boolean {
  return !!(
    process.env.GOOGLE_ADS_CLIENT_ID &&
    process.env.GOOGLE_ADS_CLIENT_SECRET &&
    process.env.GOOGLE_ADS_DEVELOPER_TOKEN &&
    process.env.GOOGLE_ADS_CUSTOMER_ID &&
    process.env.GOOGLE_ADS_REFRESH_TOKEN
  )
}
