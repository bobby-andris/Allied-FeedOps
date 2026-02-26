// === Demand Tab Types ===
export interface ImpressionShareGap {
  queryText: string
  customLabel0: string
  actualImpressions: number
  marketVolume: number | null // avg_monthly_searches from keyword_metrics
  sharePercent: number | null // actual / market * 100
  gap: number | null // market - actual (how many impressions we're missing)
}

export interface CpcOpportunity {
  queryText: string
  customLabel0: string
  actualCpcMicros: number
  marketHighCpcMicros: number | null
  headroomPercent: number | null // (1 - actual/market) * 100; positive = below market
  savings: 'below_market' | 'at_market' | 'above_market'
}

export interface MonthlySearchVolume {
  year: number
  month: number
  searches: number
}

export interface SeasonalTerm {
  queryText: string
  customLabel0: string
  avgMonthlySearches: number
  monthlyVolumes: MonthlySearchVolume[]
  currentMonthSearches: number
  priorMonthSearches: number
  changePercent: number // MoM change
  direction: 'spiking' | 'declining' | 'stable'
}

export interface NewTerm {
  queryText: string
  customLabel0: string
  firstSeen: string // ISO date
  impressions: number
  clicks: number
  conversions: number
}

export interface LongTailBucket {
  wordCountRange: string // '1-2', '3-4', '5+'
  termCount: number
  avgRoas: number
  avgCvr: number
  totalImpressions: number
  totalConversions: number
  totalRevenue: number
  totalSpend: number
}

export interface DemandData {
  impressionShare: ImpressionShareGap[]
  cpcOpportunity: CpcOpportunity[]
  seasonal: SeasonalTerm[]
  newTerms: NewTerm[]
  longTail: LongTailBucket[]
  kpis: {
    avgImpressionShare: number | null
    avgCpcHeadroom: number | null
    seasonalAlertCount: number
    newTermCount: number
  }
}

// === Competitive Tab Types ===
export interface BrandSplit {
  segment: 'brand' | 'non_brand' | 'competitor'
  revenue: number
  spend: number
  roas: number
  impressions: number
  clicks: number
  conversions: number
  termCount: number
}

export interface CompetitorMention {
  token: string
  termCount: number
  impressions: number
  clicks: number
  spend: number // cost in dollars
  conversions: number
  revenue: number
  roas: number
  topTerms: string[] // top 5 terms containing this token
}

export interface CompetitiveData {
  brandSplit: BrandSplit[]
  competitorMentions: CompetitorMention[]
  kpis: {
    brandRevenuePercent: number
    competitorSpend: number
    topCompetitor: string | null
    nonBrandRoas: number
  }
}

// === Products Tab Types ===
export type BcgQuadrant = 'star' | 'cashCow' | 'questionMark' | 'dog'

export interface ProductGroup {
  customLabel0: string
  roas: number
  revenue: number
  spend: number
  impressions: number
  conversions: number
  termCount: number
  trend: number // percent change vs prior period
  trendDirection: 'up' | 'down' | 'flat'
  quadrant: BcgQuadrant
}

export interface ProductGroupDetail {
  customLabel0: string
  quadrant: BcgQuadrant
  roas: number
  revenue: number
  spend: number
  trend: number
  topTerms: Array<{
    searchTerm: string
    currentTier: string
    impressions: number
    clicks: number
    revenue: number
    roas: number
  }>
}

export interface ProductsData {
  groups: ProductGroup[]
  medianRoas: number
  medianRevenue: number
  kpis: {
    starCount: number
    cashCowCount: number
    questionMarkCount: number
    dogCount: number
    totalRevenue: number
    totalSpend: number
  }
}
