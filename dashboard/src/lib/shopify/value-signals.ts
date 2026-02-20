import { createAdminClient } from '@/lib/supabase/admin'

const SHOPIFY_API_VERSION = '2026-01'

export interface ShopifyLineItemSnapshot {
  sku: string
  quantity: number
  revenue: number
}

export interface ShopifyOrderSnapshot {
  id: string
  createdAt: string
  customerId: string | null
  totalRevenue: number
  lineItems: ShopifyLineItemSnapshot[]
}

export interface ShopifyCustomLabelRevenue {
  customLabel0: string
  revenue: number
  orderCount: number
  skuCount: number
}

export interface ShopifyValueSignalsSummary {
  orderCount: number
  uniqueCustomers: number
  repeatCustomerRate: number
  totalRevenue: number
  averageOrderValue: number
  topCustomLabels: ShopifyCustomLabelRevenue[]
  topSkus: Array<{ sku: string; revenue: number; quantity: number }>
  unmappedSkuRevenue: number
}

export interface ShopifyValueSignalsWithMapping extends ShopifyValueSignalsSummary {
  mappedSkuCount: number
  skuCountInOrders: number
}

interface ShopifyGraphQLResponse<T = unknown> {
  data?: T
  errors?: Array<{ message: string }>
}

interface OrdersQueryResponse {
  orders: {
    pageInfo: {
      hasNextPage: boolean
      endCursor: string | null
    }
    nodes: Array<{
      id: string
      createdAt: string
      customer: { id: string } | null
      totalPriceSet?: { shopMoney?: { amount?: string } } | null
      lineItems: {
        nodes: Array<{
          quantity?: number | null
          sku?: string | null
          discountedTotalSet?: { shopMoney?: { amount?: string } } | null
          originalTotalSet?: { shopMoney?: { amount?: string } } | null
        }>
      }
    }>
  }
}

function getShopifyCredentials(): { storeUrl: string; accessToken: string } {
  const storeUrl = process.env.SHOPIFY_STORE_URL
  const accessToken = process.env.SHOPIFY_ACCESS_TOKEN

  if (!storeUrl || !accessToken) {
    throw new Error('Missing Shopify credentials. Required: SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN')
  }

  return { storeUrl, accessToken }
}

function normalizeStoreHost(storeUrl: string): string {
  const withoutProtocol = storeUrl.replace('https://', '').replace('http://', '').trim()
  return withoutProtocol.split('/')[0].replace(/\/$/, '')
}

function parseAmount(value: string | undefined | null): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
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

async function shopifyGraphQL<T>(
  query: string,
  variables: Record<string, unknown>
): Promise<ShopifyGraphQLResponse<T>> {
  const { storeUrl, accessToken } = getShopifyCredentials()
  const host = normalizeStoreHost(storeUrl)
  const endpoint = `https://${host}/admin/api/${SHOPIFY_API_VERSION}/graphql.json`

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': accessToken,
    },
    body: JSON.stringify({ query, variables }),
  })

  if (!response.ok) {
    throw new Error(`Shopify API request failed: ${response.status} ${response.statusText}`)
  }

  return response.json() as Promise<ShopifyGraphQLResponse<T>>
}

const ORDERS_QUERY = `
query OrdersForSignals($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, sortKey: CREATED_AT, reverse: true, query: $query) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      id
      createdAt
      customer {
        id
      }
      totalPriceSet {
        shopMoney {
          amount
        }
      }
      lineItems(first: 50) {
        nodes {
          quantity
          sku
          discountedTotalSet {
            shopMoney {
              amount
            }
          }
          originalTotalSet {
            shopMoney {
              amount
            }
          }
        }
      }
    }
  }
}
`

export async function fetchShopifyOrderSnapshots(options?: {
  lookbackDays?: number
  maxOrders?: number
}): Promise<ShopifyOrderSnapshot[]> {
  const lookbackDays = Math.max(1, options?.lookbackDays ?? 90)
  const maxOrders = Math.max(1, options?.maxOrders ?? 500)
  const now = new Date()
  const lookbackDate = new Date(now)
  lookbackDate.setDate(now.getDate() - lookbackDays)
  const queryFilter = `created_at:>=${lookbackDate.toISOString().slice(0, 10)}`

  let after: string | null = null
  const snapshots: ShopifyOrderSnapshot[] = []

  while (snapshots.length < maxOrders) {
    const batchSize = Math.min(100, maxOrders - snapshots.length)
    const response: ShopifyGraphQLResponse<OrdersQueryResponse> = await shopifyGraphQL<OrdersQueryResponse>(
      ORDERS_QUERY,
      {
      first: batchSize,
      after,
      query: queryFilter,
      }
    )

    if (response.errors?.length) {
      throw new Error(`Shopify Orders query failed: ${response.errors.map((e) => e.message).join('; ')}`)
    }

    const orderNodes = response.data?.orders?.nodes ?? []
    for (const order of orderNodes) {
      const lineItems = (order.lineItems?.nodes ?? [])
        .map((item) => {
          const sku = (item.sku ?? '').trim()
          if (!sku) {
            return null
          }

          const quantity = Number(item.quantity ?? 0) || 0
          const revenue =
            parseAmount(item.discountedTotalSet?.shopMoney?.amount) ||
            parseAmount(item.originalTotalSet?.shopMoney?.amount)

          return {
            sku,
            quantity,
            revenue,
          } satisfies ShopifyLineItemSnapshot
        })
        .filter((item): item is ShopifyLineItemSnapshot => Boolean(item))

      snapshots.push({
        id: order.id,
        createdAt: order.createdAt,
        customerId: order.customer?.id ?? null,
        totalRevenue: parseAmount(order.totalPriceSet?.shopMoney?.amount),
        lineItems,
      })
    }

    const pageInfo = response.data?.orders?.pageInfo
    if (!pageInfo?.hasNextPage || !pageInfo.endCursor || orderNodes.length === 0) {
      break
    }
    after = pageInfo.endCursor
  }

  return snapshots.slice(0, maxOrders)
}

export function summarizeShopifyOrders(
  orders: ShopifyOrderSnapshot[],
  customLabelBySku: Record<string, string> = {}
): ShopifyValueSignalsSummary {
  const customers = new Map<string, number>()
  const revenueByLabel = new Map<string, { revenue: number; orders: Set<string>; skus: Set<string> }>()
  const revenueBySku = new Map<string, { revenue: number; quantity: number }>()
  let totalRevenue = 0
  let unmappedSkuRevenue = 0

  for (const order of orders) {
    totalRevenue += order.totalRevenue

    if (order.customerId) {
      customers.set(order.customerId, (customers.get(order.customerId) ?? 0) + 1)
    }

    for (const lineItem of order.lineItems) {
      const existingSku = revenueBySku.get(lineItem.sku) ?? { revenue: 0, quantity: 0 }
      existingSku.revenue += lineItem.revenue
      existingSku.quantity += lineItem.quantity
      revenueBySku.set(lineItem.sku, existingSku)

      const customLabel0 = customLabelBySku[lineItem.sku]
      if (!customLabel0) {
        unmappedSkuRevenue += lineItem.revenue
        continue
      }

      const existingLabel = revenueByLabel.get(customLabel0) ?? {
        revenue: 0,
        orders: new Set<string>(),
        skus: new Set<string>(),
      }
      existingLabel.revenue += lineItem.revenue
      existingLabel.orders.add(order.id)
      existingLabel.skus.add(lineItem.sku)
      revenueByLabel.set(customLabel0, existingLabel)
    }
  }

  const uniqueCustomers = customers.size
  const repeatCustomerCount = [...customers.values()].filter((count) => count >= 2).length
  const repeatCustomerRate = uniqueCustomers > 0 ? repeatCustomerCount / uniqueCustomers : 0

  const topCustomLabels = [...revenueByLabel.entries()]
    .map(([customLabel0, value]) => ({
      customLabel0,
      revenue: Number(value.revenue.toFixed(2)),
      orderCount: value.orders.size,
      skuCount: value.skus.size,
    }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 20)

  const topSkus = [...revenueBySku.entries()]
    .map(([sku, value]) => ({
      sku,
      revenue: Number(value.revenue.toFixed(2)),
      quantity: value.quantity,
    }))
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 20)

  return {
    orderCount: orders.length,
    uniqueCustomers,
    repeatCustomerRate: Number(repeatCustomerRate.toFixed(4)),
    totalRevenue: Number(totalRevenue.toFixed(2)),
    averageOrderValue: Number((orders.length > 0 ? totalRevenue / orders.length : 0).toFixed(2)),
    topCustomLabels,
    topSkus,
    unmappedSkuRevenue: Number(unmappedSkuRevenue.toFixed(2)),
  }
}

export async function fetchCustomLabelBySku(
  skus: string[],
  options?: { batchSize?: number }
): Promise<Record<string, string>> {
  const customLabelBySku: Record<string, string> = {}
  const batchSize = Math.max(1, Math.min(options?.batchSize ?? 400, 1000))
  if (skus.length === 0) {
    return customLabelBySku
  }

  const supabase = createAdminClient()
  const uniqueSkus = Array.from(new Set(skus.filter((sku) => typeof sku === 'string' && sku.trim())))

  for (let index = 0; index < uniqueSkus.length; index += batchSize) {
    const batch = uniqueSkus.slice(index, index + batchSize)
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

  return customLabelBySku
}

export async function fetchShopifyValueSignals(options?: {
  lookbackDays?: number
  maxOrders?: number
  customLabelBySku?: Record<string, string>
}) {
  const orders = await fetchShopifyOrderSnapshots(options)
  const summary = summarizeShopifyOrders(orders, options?.customLabelBySku ?? {})

  return {
    generatedAt: new Date().toISOString(),
    lookbackDays: options?.lookbackDays ?? 90,
    maxOrders: options?.maxOrders ?? 500,
    ...summary,
  }
}

export async function fetchShopifyValueSignalsWithLabelMapping(options?: {
  lookbackDays?: number
  maxOrders?: number
}): Promise<ShopifyValueSignalsWithMapping> {
  const orders = await fetchShopifyOrderSnapshots(options)
  const skus = Array.from(
    new Set(orders.flatMap((order) => order.lineItems.map((lineItem) => lineItem.sku)).filter(Boolean))
  )
  const customLabelBySku = await fetchCustomLabelBySku(skus)
  const summary = summarizeShopifyOrders(orders, customLabelBySku)

  return {
    ...summary,
    mappedSkuCount: Object.keys(customLabelBySku).length,
    skuCountInOrders: skus.length,
  }
}
