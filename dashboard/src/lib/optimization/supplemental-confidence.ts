type Ga4RiskLevel = 'low' | 'medium' | 'high'

export interface SupplementalGa4Signal {
  available: boolean
  qualityScore?: number
  riskLevel?: Ga4RiskLevel
  unassignedRevenueShare?: number
  notSetCampaignRevenueShare?: number
}

export interface SupplementalShopifySignal {
  available: boolean
  mappedSkuCount?: number
  skuCountInOrders?: number
  totalRevenue?: number
  unmappedSkuRevenue?: number
}

export interface SupplementalConfidenceSignalInput {
  ga4?: SupplementalGa4Signal
  shopify?: SupplementalShopifySignal
}

export interface SupplementalConfidenceGate {
  multiplier: number
  reasons: string[]
  warnings: string[]
  diagnostics: {
    ga4RiskLevel: Ga4RiskLevel | 'unavailable'
    ga4QualityScore: number | null
    ga4UnassignedRevenueShare: number | null
    ga4NotSetCampaignRevenueShare: number | null
    shopifyMappedSkuCoverage: number | null
    shopifyUnmappedRevenueShare: number | null
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function round4(value: number): number {
  return Number(value.toFixed(4))
}

function computeCoverageRatio(mappedSkuCount?: number, skuCountInOrders?: number): number | null {
  if (!Number.isFinite(mappedSkuCount) || !Number.isFinite(skuCountInOrders) || !skuCountInOrders) {
    return null
  }
  return clamp((mappedSkuCount ?? 0) / skuCountInOrders, 0, 1)
}

function computeUnmappedRevenueShare(totalRevenue?: number, unmappedSkuRevenue?: number): number | null {
  const total = typeof totalRevenue === 'number' ? totalRevenue : Number.NaN
  const unmapped = typeof unmappedSkuRevenue === 'number' ? unmappedSkuRevenue : Number.NaN
  if (!Number.isFinite(total) || total === 0 || !Number.isFinite(unmapped)) {
    return null
  }
  return clamp(unmapped / total, 0, 1)
}

export function computeSupplementalConfidenceGate(
  input: SupplementalConfidenceSignalInput
): SupplementalConfidenceGate {
  const reasons: string[] = []
  const warnings: string[] = []
  let multiplier = 1

  const ga4RiskLevel: Ga4RiskLevel | 'unavailable' =
    input.ga4?.available && input.ga4.riskLevel ? input.ga4.riskLevel : 'unavailable'
  const ga4QualityScore = input.ga4?.available ? (input.ga4.qualityScore ?? null) : null
  const ga4UnassignedRevenueShare = input.ga4?.available ? (input.ga4.unassignedRevenueShare ?? null) : null
  const ga4NotSetCampaignRevenueShare = input.ga4?.available
    ? (input.ga4.notSetCampaignRevenueShare ?? null)
    : null

  if (input.ga4?.available) {
    const highRiskGa4 =
      ga4RiskLevel === 'high' ||
      (typeof ga4QualityScore === 'number' && ga4QualityScore < 0.65) ||
      (typeof ga4UnassignedRevenueShare === 'number' && ga4UnassignedRevenueShare >= 0.25) ||
      (typeof ga4NotSetCampaignRevenueShare === 'number' && ga4NotSetCampaignRevenueShare >= 0.15)
    const mediumRiskGa4 =
      ga4RiskLevel === 'medium' ||
      (typeof ga4QualityScore === 'number' && ga4QualityScore < 0.82) ||
      (typeof ga4UnassignedRevenueShare === 'number' && ga4UnassignedRevenueShare >= 0.12) ||
      (typeof ga4NotSetCampaignRevenueShare === 'number' && ga4NotSetCampaignRevenueShare >= 0.08)

    if (highRiskGa4) {
      multiplier *= 0.82
      reasons.push('ga4_attribution_high_risk')
    } else if (mediumRiskGa4) {
      multiplier *= 0.92
      reasons.push('ga4_attribution_medium_risk')
    }
  } else {
    warnings.push('GA4 attribution signal unavailable; confidence gating not adjusted by GA4 quality.')
  }

  const shopifyMappedSkuCoverage = input.shopify?.available
    ? computeCoverageRatio(input.shopify.mappedSkuCount, input.shopify.skuCountInOrders)
    : null
  const shopifyUnmappedRevenueShare = input.shopify?.available
    ? computeUnmappedRevenueShare(input.shopify.totalRevenue, input.shopify.unmappedSkuRevenue)
    : null

  if (input.shopify?.available) {
    if (typeof shopifyMappedSkuCoverage === 'number') {
      if (shopifyMappedSkuCoverage < 0.5) {
        multiplier *= 0.88
        reasons.push('shopify_low_sku_label_coverage')
      } else if (shopifyMappedSkuCoverage < 0.75) {
        multiplier *= 0.95
        reasons.push('shopify_medium_sku_label_coverage')
      }
    }

    if (typeof shopifyUnmappedRevenueShare === 'number') {
      if (shopifyUnmappedRevenueShare >= 0.35) {
        multiplier *= 0.9
        reasons.push('shopify_high_unmapped_revenue_share')
      } else if (shopifyUnmappedRevenueShare >= 0.2) {
        multiplier *= 0.96
        reasons.push('shopify_medium_unmapped_revenue_share')
      }
    }
  } else {
    warnings.push('Shopify value signals unavailable; confidence gating not adjusted by SKU mapping quality.')
  }

  return {
    multiplier: round4(clamp(multiplier, 0.6, 1)),
    reasons,
    warnings,
    diagnostics: {
      ga4RiskLevel,
      ga4QualityScore,
      ga4UnassignedRevenueShare,
      ga4NotSetCampaignRevenueShare,
      shopifyMappedSkuCoverage: typeof shopifyMappedSkuCoverage === 'number' ? round4(shopifyMappedSkuCoverage) : null,
      shopifyUnmappedRevenueShare:
        typeof shopifyUnmappedRevenueShare === 'number' ? round4(shopifyUnmappedRevenueShare) : null,
    },
  }
}
