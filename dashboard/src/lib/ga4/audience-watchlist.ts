import type { Ga4AudienceRow, Ga4AttributionQuality } from '@/lib/ga4/client'

export interface AudienceWatchDefinition {
  id: string
  audienceName: string
  purpose: string
}

export interface AudienceWatchItem extends AudienceWatchDefinition {
  sessions: number
  transactions: number
  purchaseRevenue: number
  conversionRate: number
  status: 'observe' | 'healthy' | 'at-risk'
}

export interface AudienceRecommendation {
  audienceName: string
  recommendationType: 'observe' | 'exclude' | 'target' | 'hold'
  priority: 'high' | 'medium' | 'low'
  reason: string
}

export const DEFAULT_AUDIENCE_WATCHLIST: AudienceWatchDefinition[] = [
  {
    id: 'A1_HighIntent_NoPurchase_7d',
    audienceName: 'A1_HighIntent_NoPurchase_7d',
    purpose: 'High intent users without purchase in 7 days',
  },
  {
    id: 'A2_AddToCart_NoPurchase_3d',
    audienceName: 'A2_AddToCart_NoPurchase_3d',
    purpose: 'Cart abandoners in last 72h',
  },
  {
    id: 'A3_BeginCheckout_NoPurchase_1d',
    audienceName: 'A3_BeginCheckout_NoPurchase_1d',
    purpose: 'Checkout abandoners in last 24h',
  },
  {
    id: 'A4_RepeatBuyer_HighValue_180d',
    audienceName: 'A4_RepeatBuyer_HighValue_180d',
    purpose: 'Repeat buyers with high value propensity',
  },
  {
    id: 'A5_PaidSession_LowEngagement_30d',
    audienceName: 'A5_PaidSession_LowEngagement_30d',
    purpose: 'Paid sessions with weak engagement and no progression',
  },
]

export function buildAudienceWatchItems(
  rows: Ga4AudienceRow[],
  definitions: AudienceWatchDefinition[] = DEFAULT_AUDIENCE_WATCHLIST
): AudienceWatchItem[] {
  const byAudience = new Map(rows.map((row) => [row.audienceName.toLowerCase(), row]))

  return definitions.map((definition) => {
    const row = byAudience.get(definition.audienceName.toLowerCase())
    const sessions = row?.sessions ?? 0
    const transactions = row?.transactions ?? 0
    const purchaseRevenue = row?.purchaseRevenue ?? 0
    const conversionRate = sessions > 0 ? transactions / sessions : 0

    let status: AudienceWatchItem['status'] = 'observe'
    if (sessions >= 250 && transactions === 0) {
      status = 'at-risk'
    } else if (transactions > 0) {
      status = 'healthy'
    }

    return {
      ...definition,
      sessions,
      transactions,
      purchaseRevenue: Number(purchaseRevenue.toFixed(2)),
      conversionRate: Number(conversionRate.toFixed(4)),
      status,
    }
  })
}

export function buildAudienceRecommendations(
  watchItems: AudienceWatchItem[],
  attributionQuality: Ga4AttributionQuality
): AudienceRecommendation[] {
  const recommendations: AudienceRecommendation[] = []

  if (attributionQuality.riskLevel === 'high') {
    recommendations.push({
      audienceName: 'All audiences',
      recommendationType: 'hold',
      priority: 'high',
      reason:
        'Attribution quality is high risk. Hold automatic audience actions until data reliability improves.',
    })
  }

  for (const item of watchItems) {
    if (item.sessions >= 300 && item.transactions === 0) {
      recommendations.push({
        audienceName: item.audienceName,
        recommendationType: 'exclude',
        priority: 'high',
        reason: 'High session volume with zero conversions indicates expensive low-quality traffic.',
      })
      continue
    }

    if (item.conversionRate >= 0.035 && item.purchaseRevenue >= 1000) {
      recommendations.push({
        audienceName: item.audienceName,
        recommendationType: 'target',
        priority: 'medium',
        reason: 'Strong conversion efficiency and revenue support positive targeting expansion tests.',
      })
      continue
    }

    recommendations.push({
      audienceName: item.audienceName,
      recommendationType: 'observe',
      priority: 'low',
      reason: 'Insufficient evidence for change. Continue watchlist monitoring.',
    })
  }

  return recommendations
}

