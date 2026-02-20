import { describe, expect, it } from 'vitest'
import {
  summarizeShopifyOrders,
  type ShopifyOrderSnapshot,
} from '@/lib/shopify/value-signals'

describe('summarizeShopifyOrders', () => {
  it('aggregates revenue, repeat customers, and custom_label_0 totals', () => {
    const orders: ShopifyOrderSnapshot[] = [
      {
        id: '1',
        createdAt: '2026-02-01T00:00:00.000Z',
        customerId: 'cust-a',
        totalRevenue: 220,
        lineItems: [
          { sku: 'SKU-1', quantity: 1, revenue: 120 },
          { sku: 'SKU-2', quantity: 1, revenue: 100 },
        ],
      },
      {
        id: '2',
        createdAt: '2026-02-03T00:00:00.000Z',
        customerId: 'cust-a',
        totalRevenue: 180,
        lineItems: [{ sku: 'SKU-1', quantity: 2, revenue: 180 }],
      },
      {
        id: '3',
        createdAt: '2026-02-05T00:00:00.000Z',
        customerId: 'cust-b',
        totalRevenue: 80,
        lineItems: [{ sku: 'SKU-3', quantity: 1, revenue: 80 }],
      },
    ]

    const summary = summarizeShopifyOrders(orders, {
      'SKU-1': 'Wall Mounted Towel Bars',
      'SKU-2': 'Soap Dishes & Holders',
    })

    expect(summary.orderCount).toBe(3)
    expect(summary.totalRevenue).toBe(480)
    expect(summary.uniqueCustomers).toBe(2)
    expect(summary.repeatCustomerRate).toBe(0.5)
    expect(summary.topCustomLabels[0]).toEqual(
      expect.objectContaining({
        customLabel0: 'Wall Mounted Towel Bars',
        revenue: 300,
      })
    )
    expect(summary.unmappedSkuRevenue).toBe(80)
  })
})

