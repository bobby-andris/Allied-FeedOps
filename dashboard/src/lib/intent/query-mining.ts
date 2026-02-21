/**
 * Continuous Query Mining + Auto-Generated Campaign Drafts
 *
 * Filters novel search terms and generates campaign draft objects
 * from query clusters grouped by intent class.
 */

import type { IntentClass, SearchTier } from '@/lib/intent/types'

export interface QueryCluster {
  terms: string[]
  intentClass: IntentClass
  recommendedTier: SearchTier
  avgConfidence: number
}

export interface CampaignDraft {
  campaignName: string
  adGroupName: string
  matchType: 'broad' | 'phrase' | 'exact'
  keywords: string[]
  estimatedVolume: number
}

export interface BuildoutBrief {
  intent_class: string
  terms: string[]
  recommended_tier: string
  avg_confidence: number
}

/**
 * Filter candidateTerms to only those NOT already in existingTerms (case-insensitive).
 */
export function mineNewQueries(existingTerms: string[], candidateTerms: string[]): string[] {
  const existingSet = new Set(existingTerms.map((t) => t.toLowerCase().trim()))
  return candidateTerms.filter((term) => {
    const normalized = term.toLowerCase().trim()
    return normalized.length > 0 && !existingSet.has(normalized)
  })
}

function matchTypeFromTier(tier: SearchTier): 'broad' | 'phrase' | 'exact' {
  switch (tier) {
    case 'exact':
      return 'exact'
    case 'phrase':
      return 'phrase'
    case 'broad':
    default:
      return 'broad'
  }
}

function campaignNameFromIntent(intentClass: IntentClass): string {
  const labels: Record<IntentClass, string> = {
    BRAND_CORE: 'Brand Core',
    PRODUCT_HIGH: 'Product High-Intent',
    CATEGORY_MID: 'Category Mid-Funnel',
    DISCOVERY_LOW: 'Discovery Low-Funnel',
    COMPETITOR: 'Competitor',
    INFO_ASSIST: 'Informational',
    MISMATCH: 'Mismatch Review',
    RISK_POLICY: 'Risk Policy',
  }
  return `FeedOps - ${labels[intentClass] ?? intentClass}`
}

/**
 * Build a campaign draft from a query cluster.
 */
export function buildCampaignDraft(queryCluster: QueryCluster): CampaignDraft {
  return {
    campaignName: campaignNameFromIntent(queryCluster.intentClass),
    adGroupName: `${queryCluster.intentClass}_auto_${queryCluster.terms.length}kw`,
    matchType: matchTypeFromTier(queryCluster.recommendedTier),
    keywords: [...queryCluster.terms],
    estimatedVolume: queryCluster.terms.length,
  }
}

/**
 * Generate campaign drafts from buildout briefs, grouping by intent class.
 */
export function generateCampaignDrafts(buildoutBriefs: BuildoutBrief[]): CampaignDraft[] {
  if (buildoutBriefs.length === 0) return []

  const grouped = new Map<
    string,
    { terms: string[]; tiers: string[]; confidences: number[] }
  >()

  for (const brief of buildoutBriefs) {
    const existing = grouped.get(brief.intent_class)
    if (existing) {
      existing.terms.push(...brief.terms)
      existing.tiers.push(brief.recommended_tier)
      existing.confidences.push(brief.avg_confidence)
    } else {
      grouped.set(brief.intent_class, {
        terms: [...brief.terms],
        tiers: [brief.recommended_tier],
        confidences: [brief.avg_confidence],
      })
    }
  }

  const drafts: CampaignDraft[] = []

  for (const [intentClass, data] of grouped) {
    const uniqueTerms = [...new Set(data.terms)]
    const avgConfidence =
      data.confidences.reduce((sum, c) => sum + c, 0) / data.confidences.length

    // Pick the most common tier
    const tierCounts = new Map<string, number>()
    for (const tier of data.tiers) {
      tierCounts.set(tier, (tierCounts.get(tier) ?? 0) + 1)
    }
    let bestTier = data.tiers[0]
    let bestCount = 0
    for (const [tier, count] of tierCounts) {
      if (count > bestCount) {
        bestTier = tier
        bestCount = count
      }
    }

    const cluster: QueryCluster = {
      terms: uniqueTerms,
      intentClass: intentClass as IntentClass,
      recommendedTier: bestTier as SearchTier,
      avgConfidence,
    }

    drafts.push(buildCampaignDraft(cluster))
  }

  return drafts
}
