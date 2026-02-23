import { GoogleAdsApi, ResourceNames, enums } from 'google-ads-api'
import type {
  AssignmentTier,
  CampaignSetIntegritySummary,
  DateWindow,
  ExistingFunnelResponse,
  ExistingFunnelTerm,
  ExistingFunnelUpdate,
  ExistingFunnelUpdateResult,
  FunnelDecisionAssignment,
  FunnelTier,
  GetExistingFunnelOptions,
  GetNeedsDecisionOptions,
  LabelTierPerformanceResponse,
  NeedsDecisionResponse,
  NeedsDecisionTerm,
  PostDecisionItem,
  PostDecisionResult,
  PostDecisionsResponse,
  ShoppingFunnelLineageResponse,
  UpdateExistingResponse,
} from '@/lib/shopping-funnel/types'
import {
  classifyGoogleAdsError,
  GoogleAdsRetryError,
  runWithGoogleAdsRetry,
} from '@/lib/shopping-funnel/retry'
import { enrichNeedsDecisionTerm } from '@/lib/optimization/query-intelligence'

const SHARED_LIST_NAME_BY_ACTION = {
  global_block: 'AVD - Global Block',
  competitor: 'AVD - Competitor Terms',
  branded: 'AVD - BRANDED_SEARCH_TERMS - US',
} as const

const CAMPAIGN_NAME_PATTERN = /^AVD - Shopping - US - (.+?) - (HIGH|MEDIUM|LOW)$/i
const TEST_CAMPAIGN_PATTERN = /tst/i
const EXCLUDED_CAMPAIGN_NAMES = new Set(['avd - shopping - branded - us'])
const EXCLUDED_CUSTOM_LABELS = new Set(['catchall', 'branded - us'])
const CACHE_TTL_MS = 2 * 60 * 1000
export const SHOPPING_FUNNEL_DATA_SOURCE = 'google_ads_api_live'
export const SHOPPING_FUNNEL_CACHE_TTL_MS = CACHE_TTL_MS

type SharedAction = keyof typeof SHARED_LIST_NAME_BY_ACTION

interface ParsedCampaign {
  customLabel0: string
  tier: FunnelTier
}

interface SearchTermRow {
  searchTerm: string
  campaignName: string
  adGroupName: string
  customLabel0: string
  sourceTier: FunnelTier
  impressions: number
  clicks: number
  costMicros: number
  conversions: number
  conversionsValue: number
}

interface LabelCampaignSet {
  HIGH?: string
  MEDIUM?: string
  LOW?: string
}

interface AdsContext {
  customer: ReturnType<GoogleAdsApi['Customer']>
  customerId: string
  dateWindow: DateWindow
  labelCampaigns: Map<string, LabelCampaignSet>
  labelNameByNormalized: Map<string, string>
  campaignIdByName: Map<string, string>
  adGroupIdByKey: Map<string, string>
  sharedSetIdByAction: Map<SharedAction, string>
  sharedKeywordsByAction: Map<SharedAction, Set<string>>
  sharedCriterionIdsByActionAndTerm: Map<string, Set<string>>
  campaignNegativeTermsByCampaign: Map<string, Set<string>>
  campaignNegativeCriterionIdsByCampaignAndTerm: Map<string, Set<string>>
  adGroupNegativeTermsByCampaignAdGroup: Map<string, Set<string>>
  adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm: Map<string, Set<string>>
  searchRows: SearchTermRow[]
}

interface AssignmentAggregate {
  customLabel0: string
  sourceCampaign: string
  sourceTier: FunnelTier
  sourceImpressionsMax: number
  impressions: number
  clicks: number
  costMicros: number
  conversions: number
  conversionsValue: number
}

interface ExistingTierResult {
  tier: 'High' | 'Medium' | 'Low' | 'Campaign Negative' | 'Unknown'
  error: boolean
  errorMessage: string | null
}

let clientInstance: GoogleAdsApi | null = null
const contextCache = new Map<string, { expiresAt: number; value: AdsContext }>()

async function runGoogleAdsOperation<T>(operationName: string, operation: () => Promise<T>): Promise<T> {
  const result = await runWithGoogleAdsRetry(operation, {
    operationName,
    onRetry: ({ retryCount, delayMs, errorCode }) => {
      console.warn(
        `[GoogleAdsRetry] ${operationName} retry=${retryCount} delayMs=${delayMs} errorCode=${errorCode}`
      )
    },
  })
  return result.value
}

function getErrorCodeFromUnknown(error: unknown): string | undefined {
  if (error instanceof GoogleAdsRetryError) {
    return error.code
  }
  const classified = classifyGoogleAdsError(error)
  return classified.code === 'UNKNOWN' ? undefined : classified.code
}

function getRetryCountFromUnknown(error: unknown): number {
  if (error instanceof GoogleAdsRetryError) {
    return error.retryCount
  }
  return 0
}

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
  const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID
  const loginCustomerId = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID
  const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN

  if (!customerId || !refreshToken) {
    throw new Error(
      'Missing Google Ads customer config. Required: GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_REFRESH_TOKEN'
    )
  }

  return getClient().Customer({
    customer_id: customerId,
    login_customer_id: loginCustomerId,
    refresh_token: refreshToken,
  })
}

function escapeGaqlLiteral(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
}

function normalizeSearchTerm(value: string): string {
  return value.toLowerCase().trim().replace(/\s+/g, ' ')
}

function normalizeCampaignName(value: string): string {
  return value.toLowerCase().trim().replace(/\s+/g, ' ')
}

function isExcludedCampaignName(campaignName: string): boolean {
  return EXCLUDED_CAMPAIGN_NAMES.has(normalizeCampaignName(campaignName))
}

function isExcludedCustomLabel(customLabel: string): boolean {
  return EXCLUDED_CUSTOM_LABELS.has(customLabel.toLowerCase().trim())
}

function isExcludedCampaign(campaignName: string): boolean {
  if (!campaignName) {
    return false
  }

  if (isExcludedCampaignName(campaignName)) {
    return true
  }

  const match = campaignName.match(CAMPAIGN_NAME_PATTERN)
  if (!match) {
    return false
  }

  return isExcludedCustomLabel(match[1].trim())
}

function parseCampaign(name: string): ParsedCampaign | null {
  if (!name || TEST_CAMPAIGN_PATTERN.test(name) || isExcludedCampaign(name)) {
    return null
  }

  const match = name.match(CAMPAIGN_NAME_PATTERN)
  if (!match) {
    return null
  }

  const tier = match[2].toUpperCase() as FunnelTier
  return {
    customLabel0: match[1].trim(),
    tier,
  }
}

export function summarizeCampaignSetIntegrity(
  campaignNames: string[],
  adGroupPairKeys: string[]
): CampaignSetIntegritySummary {
  const tiers: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']
  const labelTiers = new Map<string, Set<FunnelTier>>()
  const nonPatternCampaigns: string[] = []
  const includedCampaignNames = campaignNames.filter((campaignName) => !isExcludedCampaign(campaignName))

  let parsedFunnelCampaigns = 0
  for (const campaignName of includedCampaignNames) {
    const parsed = parseCampaign(campaignName)
    if (!parsed) {
      nonPatternCampaigns.push(campaignName)
      continue
    }

    parsedFunnelCampaigns += 1
    const current = labelTiers.get(parsed.customLabel0) ?? new Set<FunnelTier>()
    current.add(parsed.tier)
    labelTiers.set(parsed.customLabel0, current)
  }

  let adGroupNameMismatchCount = 0
  for (const pairKey of adGroupPairKeys) {
    const separatorIndex = pairKey.indexOf('|')
    if (separatorIndex < 0) {
      continue
    }
    const campaignName = pairKey.slice(0, separatorIndex)
    const adGroupName = pairKey.slice(separatorIndex + 1)
    if (isExcludedCampaign(campaignName)) {
      continue
    }
    if (campaignName !== adGroupName) {
      adGroupNameMismatchCount += 1
    }
  }

  const labelsWithMissingTiers = [...labelTiers.entries()]
    .map(([customLabel0, presentTierSet]) => {
      const presentTiers = tiers.filter((tier) => presentTierSet.has(tier))
      const missingTiers = tiers.filter((tier) => !presentTierSet.has(tier))
      return {
        custom_label_0: customLabel0,
        present_tiers: presentTiers,
        missing_tiers: missingTiers,
      }
    })
    .filter((item) => item.missing_tiers.length > 0)
    .sort((a, b) => a.custom_label_0.localeCompare(b.custom_label_0))

  return {
    enabled_shopping_campaigns: includedCampaignNames.length,
    parsed_funnel_campaigns: parsedFunnelCampaigns,
    non_pattern_campaign_count: nonPatternCampaigns.length,
    non_pattern_campaigns: nonPatternCampaigns.sort((a, b) => a.localeCompare(b)),
    ad_group_name_mismatch_count: adGroupNameMismatchCount,
    custom_label_0_count: labelTiers.size,
    labels_with_missing_tiers: labelsWithMissingTiers,
  }
}

function buildDateWindow(startDate?: string, endDate?: string): DateWindow {
  const end = endDate ? new Date(endDate) : new Date()
  const start = startDate ? new Date(startDate) : new Date(end)

  if (!startDate) {
    start.setDate(start.getDate() - 30)
  }

  const startIso = start.toISOString().split('T')[0]
  const endIso = end.toISOString().split('T')[0]

  return { startDate: startIso, endDate: endIso }
}

function cacheKey(window: DateWindow): string {
  return `${window.startDate}:${window.endDate}`
}

function getLabelCampaignSet(context: AdsContext, label: string): LabelCampaignSet | null {
  const resolved = context.labelNameByNormalized.get(label.toLowerCase().trim()) ?? label
  return context.labelCampaigns.get(resolved) ?? null
}

function campaignKey(campaignName: string, term: string): string {
  return `${campaignName}|${term}`
}

function adGroupKey(campaignName: string, adGroupName: string, term: string): string {
  return `${campaignName}|${adGroupName}|${term}`
}

function sharedKey(action: SharedAction, term: string): string {
  return `${action}|${term}`
}

function addToSetMap(map: Map<string, Set<string>>, key: string, value: string) {
  const current = map.get(key) ?? new Set<string>()
  current.add(value)
  map.set(key, current)
}

function removeFromSetMap(map: Map<string, Set<string>>, key: string, value: string) {
  const current = map.get(key)
  if (!current) {
    return
  }
  current.delete(value)
  if (current.size === 0) {
    map.delete(key)
  } else {
    map.set(key, current)
  }
}

function blockedTiersForAssignment(target: AssignmentTier): FunnelTier[] {
  if (target === 'high') {
    return ['MEDIUM', 'LOW']
  }
  if (target === 'medium') {
    return ['HIGH', 'LOW']
  }
  if (target === 'low') {
    return ['HIGH', 'MEDIUM']
  }
  return []
}

function existingTierForLabel(
  context: AdsContext,
  label: string,
  normalizedTerm: string
): ExistingTierResult | null {
  const labelCampaigns = getLabelCampaignSet(context, label)
  if (!labelCampaigns?.HIGH || !labelCampaigns.MEDIUM || !labelCampaigns.LOW) {
    return {
      tier: 'Unknown',
      error: true,
      errorMessage: 'Missing one or more funnel campaigns for this custom_label_0',
    }
  }

  const campaignNames = [labelCampaigns.HIGH, labelCampaigns.MEDIUM, labelCampaigns.LOW]

  const campaignNegativeIn = campaignNames.filter((campaignName) =>
    context.campaignNegativeTermsByCampaign.get(campaignName)?.has(normalizedTerm)
  )

  if (campaignNegativeIn.length === 3) {
    return {
      tier: 'Campaign Negative',
      error: false,
      errorMessage: null,
    }
  }

  if (campaignNegativeIn.length > 0 && campaignNegativeIn.length < 3) {
    return {
      tier: 'Campaign Negative',
      error: true,
      errorMessage: 'Campaign negative incomplete',
    }
  }

  const inHigh = Boolean(
    context.adGroupNegativeTermsByCampaignAdGroup
      .get(`${labelCampaigns.HIGH}|${labelCampaigns.HIGH}`)
      ?.has(normalizedTerm)
  )
  const inMedium = Boolean(
    context.adGroupNegativeTermsByCampaignAdGroup
      .get(`${labelCampaigns.MEDIUM}|${labelCampaigns.MEDIUM}`)
      ?.has(normalizedTerm)
  )
  const inLow = Boolean(
    context.adGroupNegativeTermsByCampaignAdGroup
      .get(`${labelCampaigns.LOW}|${labelCampaigns.LOW}`)
      ?.has(normalizedTerm)
  )

  const adGroupCount = [inHigh, inMedium, inLow].filter(Boolean).length

  if (adGroupCount === 0) {
    return null
  }

  if (adGroupCount === 3) {
    return {
      tier: 'Unknown',
      error: true,
      errorMessage: 'Blocked in all 3 tiers',
    }
  }

  if (adGroupCount === 1) {
    return {
      tier: 'Unknown',
      error: true,
      errorMessage: 'Only blocked in 1 tier',
    }
  }

  if (inMedium && inLow && !inHigh) {
    return { tier: 'High', error: false, errorMessage: null }
  }
  if (inHigh && inLow && !inMedium) {
    return { tier: 'Medium', error: false, errorMessage: null }
  }
  if (inHigh && inMedium && !inLow) {
    return { tier: 'Low', error: false, errorMessage: null }
  }

  return {
    tier: 'Unknown',
    error: true,
    errorMessage: 'Invalid tier configuration',
  }
}

function existsInLabelFunnel(context: AdsContext, label: string, normalizedTerm: string): boolean {
  const labelCampaigns = getLabelCampaignSet(context, label)
  if (!labelCampaigns) {
    return false
  }

  const campaigns = [labelCampaigns.HIGH, labelCampaigns.MEDIUM, labelCampaigns.LOW].filter(
    Boolean
  ) as string[]

  for (const campaignName of campaigns) {
    if (context.campaignNegativeTermsByCampaign.get(campaignName)?.has(normalizedTerm)) {
      return true
    }

    const adGroupPairKey = `${campaignName}|${campaignName}`
    if (
      context.adGroupNegativeTermsByCampaignAdGroup
        .get(adGroupPairKey)
        ?.has(normalizedTerm)
    ) {
      return true
    }
  }

  return false
}

async function fetchAdsContext(window: DateWindow): Promise<AdsContext> {
  const key = cacheKey(window)
  const existing = contextCache.get(key)
  const now = Date.now()
  if (existing && existing.expiresAt > now) {
    return existing.value
  }

  const customer = getCustomer()
  const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID as string

  const [campaignRows, adGroupRows, sharedSetRows, campaignNegativeRows, adGroupNegativeRows, searchRows] =
    await Promise.all([
      runGoogleAdsOperation('query_enabled_shopping_campaigns', () =>
        customer.query(`
        SELECT
          campaign.id,
          campaign.name
        FROM campaign
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
      `)
      ),
      runGoogleAdsOperation('query_enabled_shopping_ad_groups', () =>
        customer.query(`
        SELECT
          campaign.name,
          ad_group.id,
          ad_group.name
        FROM ad_group
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND ad_group.status = ENABLED
      `)
      ),
      runGoogleAdsOperation('query_negative_shared_sets', () =>
        customer.query(`
        SELECT
          shared_set.id,
          shared_set.name
        FROM shared_set
        WHERE shared_set.type = NEGATIVE_KEYWORDS
      `)
      ),
      runGoogleAdsOperation('query_campaign_negative_keywords', () =>
        customer.query(`
        SELECT
          campaign.name,
          campaign_criterion.criterion_id,
          campaign_criterion.keyword.text,
          campaign_criterion.keyword.match_type
        FROM campaign_criterion
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND campaign_criterion.type = KEYWORD
          AND campaign_criterion.negative = TRUE
      `)
      ),
      runGoogleAdsOperation('query_ad_group_negative_keywords', () =>
        customer.query(`
        SELECT
          campaign.name,
          ad_group.name,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type
        FROM ad_group_criterion
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND ad_group.status = ENABLED
          AND ad_group_criterion.type = KEYWORD
          AND ad_group_criterion.negative = TRUE
      `)
      ),
      runGoogleAdsOperation('query_shopping_search_terms', () =>
        customer.query(`
        SELECT
          campaign.name,
          ad_group.name,
          search_term_view.search_term,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM search_term_view
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND ad_group.status = ENABLED
          AND segments.date BETWEEN '${window.startDate}' AND '${window.endDate}'
      `)
      ),
    ])

  const labelCampaigns = new Map<string, LabelCampaignSet>()
  const labelNameByNormalized = new Map<string, string>()
  const campaignIdByName = new Map<string, string>()

  for (const row of campaignRows as Array<Record<string, unknown>>) {
    const campaign = (row.campaign ?? {}) as Record<string, string>
    const campaignName = campaign.name
    const campaignId = campaign.id
    if (!campaignName || !campaignId || isExcludedCampaign(campaignName)) {
      continue
    }

    campaignIdByName.set(campaignName, campaignId)

    const parsed = parseCampaign(campaignName)
    if (!parsed) {
      continue
    }

    const normalizedLabel = parsed.customLabel0.toLowerCase()
    const current = labelCampaigns.get(parsed.customLabel0) ?? {}
    current[parsed.tier] = campaignName
    labelCampaigns.set(parsed.customLabel0, current)
    labelNameByNormalized.set(normalizedLabel, parsed.customLabel0)
  }

  const adGroupIdByKey = new Map<string, string>()
  for (const row of adGroupRows as Array<Record<string, unknown>>) {
    const campaign = (row.campaign ?? {}) as Record<string, string>
    const adGroup = (row.ad_group ?? {}) as Record<string, string>
    if (!campaign.name || !adGroup.name || !adGroup.id || isExcludedCampaign(campaign.name)) {
      continue
    }

    adGroupIdByKey.set(`${campaign.name}|${adGroup.name}`, adGroup.id)
  }

  const sharedSetIdByAction = new Map<SharedAction, string>()
  for (const row of sharedSetRows as Array<Record<string, unknown>>) {
    const sharedSet = (row.shared_set ?? {}) as Record<string, string>
    const id = sharedSet.id
    const name = sharedSet.name
    if (!id || !name) {
      continue
    }

    ;(Object.keys(SHARED_LIST_NAME_BY_ACTION) as SharedAction[]).forEach((action) => {
      if (SHARED_LIST_NAME_BY_ACTION[action] === name) {
        sharedSetIdByAction.set(action, id)
      }
    })
  }

  const sharedKeywordsByAction = new Map<SharedAction, Set<string>>()
  const sharedCriterionIdsByActionAndTerm = new Map<string, Set<string>>()

  const sharedActionIds = [...sharedSetIdByAction.entries()].map(([action, id]) => ({
    action,
    id,
  }))

  if (sharedActionIds.length > 0) {
    const idClause = sharedActionIds.map(({ id }) => id).join(', ')
    const sharedCriteriaRows = (await runGoogleAdsOperation('query_shared_criteria', () =>
      customer.query(`
      SELECT
        shared_set.id,
        shared_set.name,
        shared_criterion.criterion_id,
        shared_criterion.keyword.text
      FROM shared_criterion
      WHERE shared_set.id IN (${idClause})
    `)
    )) as Array<Record<string, unknown>>

    const actionBySetId = new Map<string, SharedAction>(
      sharedActionIds.map(({ action, id }) => [id, action])
    )

    for (const row of sharedCriteriaRows) {
      const sharedSet = (row.shared_set ?? {}) as Record<string, string>
      const criterion = (row.shared_criterion ?? {}) as Record<string, unknown>
      const keyword = (criterion.keyword ?? {}) as Record<string, string>
      const action = actionBySetId.get(sharedSet.id)
      const text = keyword.text
      const criterionId = criterion.criterion_id
      if (!action || !text || !criterionId) {
        continue
      }

      const normalized = normalizeSearchTerm(text)
      const current = sharedKeywordsByAction.get(action) ?? new Set<string>()
      current.add(normalized)
      sharedKeywordsByAction.set(action, current)
      addToSetMap(
        sharedCriterionIdsByActionAndTerm,
        sharedKey(action, normalized),
        String(criterionId)
      )
    }
  }

  for (const action of Object.keys(SHARED_LIST_NAME_BY_ACTION) as SharedAction[]) {
    if (!sharedKeywordsByAction.has(action)) {
      sharedKeywordsByAction.set(action, new Set<string>())
    }
  }

  const campaignNegativeTermsByCampaign = new Map<string, Set<string>>()
  const campaignNegativeCriterionIdsByCampaignAndTerm = new Map<string, Set<string>>()

  for (const row of campaignNegativeRows as Array<Record<string, unknown>>) {
    const campaign = (row.campaign ?? {}) as Record<string, string>
    const criterion = (row.campaign_criterion ?? {}) as Record<string, unknown>
    const keyword = (criterion.keyword ?? {}) as Record<string, string>
    if (!campaign.name || !keyword.text || isExcludedCampaign(campaign.name)) {
      continue
    }
    const normalized = normalizeSearchTerm(keyword.text)
    addToSetMap(campaignNegativeTermsByCampaign, campaign.name, normalized)
    if (criterion.criterion_id) {
      addToSetMap(
        campaignNegativeCriterionIdsByCampaignAndTerm,
        campaignKey(campaign.name, normalized),
        String(criterion.criterion_id)
      )
    }
  }

  const adGroupNegativeTermsByCampaignAdGroup = new Map<string, Set<string>>()
  const adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm = new Map<string, Set<string>>()

  for (const row of adGroupNegativeRows as Array<Record<string, unknown>>) {
    const campaign = (row.campaign ?? {}) as Record<string, string>
    const adGroup = (row.ad_group ?? {}) as Record<string, string>
    const criterion = (row.ad_group_criterion ?? {}) as Record<string, unknown>
    const keyword = (criterion.keyword ?? {}) as Record<string, string>
    if (!campaign.name || !adGroup.name || !keyword.text || isExcludedCampaign(campaign.name)) {
      continue
    }
    const normalized = normalizeSearchTerm(keyword.text)
    const pairKey = `${campaign.name}|${adGroup.name}`
    addToSetMap(adGroupNegativeTermsByCampaignAdGroup, pairKey, normalized)
    if (criterion.criterion_id) {
      addToSetMap(
        adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm,
        adGroupKey(campaign.name, adGroup.name, normalized),
        String(criterion.criterion_id)
      )
    }
  }

  const parsedSearchRows: SearchTermRow[] = []
  for (const row of searchRows as Array<Record<string, unknown>>) {
    const campaign = (row.campaign ?? {}) as Record<string, string>
    const adGroup = (row.ad_group ?? {}) as Record<string, string>
    const searchTermView = (row.search_term_view ?? {}) as Record<string, string>
    const metrics = (row.metrics ?? {}) as Record<string, string | number>
    if (isExcludedCampaign(campaign.name)) {
      continue
    }

    const parsed = parseCampaign(campaign.name)
    if (!parsed || !searchTermView.search_term) {
      continue
    }

    parsedSearchRows.push({
      searchTerm: searchTermView.search_term,
      campaignName: campaign.name,
      adGroupName: adGroup.name,
      customLabel0: parsed.customLabel0,
      sourceTier: parsed.tier,
      impressions: Number(metrics.impressions ?? 0),
      clicks: Number(metrics.clicks ?? 0),
      costMicros: Number(metrics.cost_micros ?? 0),
      conversions: Number(metrics.conversions ?? 0),
      conversionsValue: Number(metrics.conversions_value ?? 0),
    })
  }

  const context: AdsContext = {
    customer,
    customerId,
    dateWindow: window,
    labelCampaigns,
    labelNameByNormalized,
    campaignIdByName,
    adGroupIdByKey,
    sharedSetIdByAction,
    sharedKeywordsByAction,
    sharedCriterionIdsByActionAndTerm,
    campaignNegativeTermsByCampaign,
    campaignNegativeCriterionIdsByCampaignAndTerm,
    adGroupNegativeTermsByCampaignAdGroup,
    adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm,
    searchRows: parsedSearchRows,
  }

  contextCache.set(key, { value: context, expiresAt: Date.now() + CACHE_TTL_MS })

  return context
}

function isTermInAnySharedList(context: AdsContext, normalizedTerm: string): boolean {
  for (const action of Object.keys(SHARED_LIST_NAME_BY_ACTION) as SharedAction[]) {
    if (context.sharedKeywordsByAction.get(action)?.has(normalizedTerm)) {
      return true
    }
  }
  return false
}

function aggregateByTermAndLabel(searchRows: SearchTermRow[]): Map<string, Map<string, AssignmentAggregate>> {
  const result = new Map<string, Map<string, AssignmentAggregate>>()

  for (const row of searchRows) {
    const normalized = normalizeSearchTerm(row.searchTerm)
    const byLabel = result.get(normalized) ?? new Map<string, AssignmentAggregate>()
    const current = byLabel.get(row.customLabel0) ?? {
      customLabel0: row.customLabel0,
      sourceCampaign: row.campaignName,
      sourceTier: row.sourceTier,
      sourceImpressionsMax: 0,
      impressions: 0,
      clicks: 0,
      costMicros: 0,
      conversions: 0,
      conversionsValue: 0,
    }

    current.impressions += row.impressions
    current.clicks += row.clicks
    current.costMicros += row.costMicros
    current.conversions += row.conversions
    current.conversionsValue += row.conversionsValue

    if (row.impressions > current.sourceImpressionsMax) {
      current.sourceCampaign = row.campaignName
      current.sourceTier = row.sourceTier
      current.sourceImpressionsMax = row.impressions
    }

    byLabel.set(row.customLabel0, current)
    result.set(normalized, byLabel)
  }

  return result
}

export async function getNeedsDecisionTerms(
  options: GetNeedsDecisionOptions
): Promise<NeedsDecisionResponse> {
  const dateWindow = buildDateWindow(options.startDate, options.endDate)
  const context = await fetchAdsContext(dateWindow)
  const grouped = aggregateByTermAndLabel(context.searchRows)
  const selectedLabel = options.customLabel0?.toLowerCase().trim()
  const minImpressions = options.minImpressions ?? 0
  const limit = options.limit ?? 500
  const offset = options.offset ?? 0
  const sortBy = options.sortBy ?? 'impressions_desc'

  const terms: NeedsDecisionTerm[] = []

  for (const [normalizedTerm, labelMap] of grouped.entries()) {
    if (isTermInAnySharedList(context, normalizedTerm)) {
      continue
    }

    const assignments: NeedsDecisionTerm['custom_label_0s'] = []

    for (const aggregate of labelMap.values()) {
      if (selectedLabel && aggregate.customLabel0.toLowerCase() !== selectedLabel) {
        continue
      }
      if (aggregate.impressions < minImpressions) {
        continue
      }

      if (existsInLabelFunnel(context, aggregate.customLabel0, normalizedTerm)) {
        continue
      }

      assignments.push({
        custom_label_0: aggregate.customLabel0,
        source_campaign: aggregate.sourceCampaign,
        source_tier: aggregate.sourceTier,
        impressions: aggregate.impressions,
        clicks: aggregate.clicks,
        cost_micros: aggregate.costMicros,
        conversions: aggregate.conversions,
        conversions_value: aggregate.conversionsValue,
      })
    }

    if (assignments.length > 0) {
      terms.push({
        search_term: normalizedTerm,
        custom_label_0s: assignments.sort((a, b) => b.impressions - a.impressions),
      })
    }
  }

  const enrichedTerms = terms.map(enrichNeedsDecisionTerm)

  const sumMetric = (term: NeedsDecisionTerm, field: 'impressions' | 'clicks' | 'cost_micros' | 'conversions' | 'conversions_value') =>
    term.custom_label_0s.reduce((sum, value) => sum + value[field], 0)

  enrichedTerms.sort((a, b) => {
    if (sortBy === 'impact_desc') {
      return (b.value_score?.impact_score ?? 0) - (a.value_score?.impact_score ?? 0)
    }
    if (sortBy === 'cost_desc') {
      return sumMetric(b, 'cost_micros') - sumMetric(a, 'cost_micros')
    }
    if (sortBy === 'conversions_desc') {
      return sumMetric(b, 'conversions') - sumMetric(a, 'conversions')
    }
    if (sortBy === 'labels_desc') {
      return b.custom_label_0s.length - a.custom_label_0s.length
    }
    if (sortBy === 'search_asc') {
      return a.search_term.localeCompare(b.search_term)
    }
    return sumMetric(b, 'impressions') - sumMetric(a, 'impressions')
  })

  const pagedTerms = enrichedTerms.slice(offset, offset + limit)

  return {
    terms: pagedTerms,
    total_count: enrichedTerms.length,
    returned_count: pagedTerms.length,
    limit,
    offset,
    has_next: offset + pagedTerms.length < enrichedTerms.length,
    custom_labels: [...context.labelCampaigns.keys()].sort((a, b) => a.localeCompare(b)),
    date_window: dateWindow,
    data_source: SHOPPING_FUNNEL_DATA_SOURCE,
    generated_at: new Date().toISOString(),
    cache_ttl_ms: SHOPPING_FUNNEL_CACHE_TTL_MS,
  }
}

export async function getExistingFunnelTerms(
  options: GetExistingFunnelOptions
): Promise<ExistingFunnelResponse> {
  const dateWindow = buildDateWindow(options.startDate, options.endDate)
  const context = await fetchAdsContext(dateWindow)
  const grouped = aggregateByTermAndLabel(context.searchRows)
  const selectedLabel = options.customLabel0?.toLowerCase().trim()
  const selectedTier = options.tier && options.tier !== 'all' ? options.tier : null
  const minImpressions = options.minImpressions ?? 0
  const limit = options.limit ?? 2000
  const offset = options.offset ?? 0
  const sortBy = options.sortBy ?? 'impressions_desc'

  const terms: ExistingFunnelTerm[] = []
  let errorTermCount = 0

  for (const [normalizedTerm, labelMap] of grouped.entries()) {
    const totalImpressions = [...labelMap.values()].reduce((sum, value) => sum + value.impressions, 0)
    if (totalImpressions < minImpressions) {
      continue
    }

    const funnels: ExistingFunnelTerm['funnels'] = []
    let hasError = false

    for (const aggregate of labelMap.values()) {
      if (selectedLabel && aggregate.customLabel0.toLowerCase() !== selectedLabel) {
        continue
      }

      const existing = existingTierForLabel(context, aggregate.customLabel0, normalizedTerm)
      if (!existing) {
        continue
      }

      if (selectedTier) {
        const normalizedTier = existing.tier === 'Campaign Negative'
          ? 'campaign_negative'
          : existing.tier.toLowerCase()
        if (normalizedTier !== selectedTier) {
          continue
        }
      }

      if (existing.error) {
        hasError = true
      }

      funnels.push({
        custom_label_0: aggregate.customLabel0,
        tier: existing.tier,
        error: existing.error,
        error_message: existing.errorMessage,
      })
    }

    if (funnels.length === 0) {
      continue
    }

    if (options.showErrorsOnly && !hasError) {
      continue
    }

    if (hasError) {
      errorTermCount += 1
    }

    terms.push({
      search_term: normalizedTerm,
      total_impressions: totalImpressions,
      total_clicks: [...labelMap.values()].reduce((sum, value) => sum + value.clicks, 0),
      total_cost_micros: [...labelMap.values()].reduce((sum, value) => sum + value.costMicros, 0),
      total_conversions: [...labelMap.values()].reduce((sum, value) => sum + value.conversions, 0),
      total_conversions_value: [...labelMap.values()].reduce(
        (sum, value) => sum + value.conversionsValue,
        0
      ),
      funnels,
    })
  }

  terms.sort((a, b) => {
    if (sortBy === 'errors_first') {
      const aHasError = a.funnels.some((f) => f.error)
      const bHasError = b.funnels.some((f) => f.error)
      if (aHasError !== bHasError) return aHasError ? -1 : 1
      return b.total_impressions - a.total_impressions
    }
    if (sortBy === 'cost_desc') return b.total_cost_micros - a.total_cost_micros
    if (sortBy === 'conversions_desc') return b.total_conversions - a.total_conversions
    if (sortBy === 'search_asc') return a.search_term.localeCompare(b.search_term)
    return b.total_impressions - a.total_impressions
  })

  const pagedTerms = terms.slice(offset, offset + limit)

  return {
    terms: pagedTerms,
    total_count: terms.length,
    returned_count: pagedTerms.length,
    limit,
    offset,
    has_next: offset + pagedTerms.length < terms.length,
    error_count: errorTermCount,
    custom_labels: [...context.labelCampaigns.keys()].sort((a, b) => a.localeCompare(b)),
    date_window: dateWindow,
    data_source: SHOPPING_FUNNEL_DATA_SOURCE,
    generated_at: new Date().toISOString(),
    cache_ttl_ms: SHOPPING_FUNNEL_CACHE_TTL_MS,
  }
}

export async function getLabelTierPerformance(options: {
  startDate?: string
  endDate?: string
}): Promise<LabelTierPerformanceResponse> {
  const dateWindow = buildDateWindow(options.startDate, options.endDate)
  const context = await fetchAdsContext(dateWindow)

  const rowsByKey = new Map<
    string,
    {
      custom_label_0: string
      tier: 'HIGH' | 'MEDIUM' | 'LOW'
      impressions: number
      clicks: number
      cost_micros: number
      conversions: number
      conversions_value: number
    }
  >()

  for (const row of context.searchRows) {
    const key = `${row.customLabel0}|${row.sourceTier}`
    const current = rowsByKey.get(key) ?? {
      custom_label_0: row.customLabel0,
      tier: row.sourceTier,
      impressions: 0,
      clicks: 0,
      cost_micros: 0,
      conversions: 0,
      conversions_value: 0,
    }

    current.impressions += row.impressions
    current.clicks += row.clicks
    current.cost_micros += row.costMicros
    current.conversions += row.conversions
    current.conversions_value += row.conversionsValue
    rowsByKey.set(key, current)
  }

  const rows = [...rowsByKey.values()]
    .map((row) => {
      const spend = row.cost_micros / 1_000_000
      const roas = spend > 0 ? row.conversions_value / spend : 0
      return {
        ...row,
        roas: Number(roas.toFixed(4)),
      }
    })
    .sort((a, b) => b.conversions_value - a.conversions_value)

  return {
    rows,
    total_rows: rows.length,
    date_window: dateWindow,
    data_source: SHOPPING_FUNNEL_DATA_SOURCE,
    generated_at: new Date().toISOString(),
    cache_ttl_ms: SHOPPING_FUNNEL_CACHE_TTL_MS,
  }
}

async function removeSharedKeyword(
  context: AdsContext,
  action: SharedAction,
  normalizedTerm: string
) {
  const ids = context.sharedCriterionIdsByActionAndTerm.get(sharedKey(action, normalizedTerm))
  const sharedSetId = context.sharedSetIdByAction.get(action)
  if (!ids || !sharedSetId || ids.size === 0) {
    return
  }

  const resourcesToRemove = [...ids].map((criterionId) =>
    ResourceNames.sharedCriterion(context.customerId, sharedSetId, criterionId)
  )
  await runGoogleAdsOperation('remove_shared_criteria', () =>
    context.customer.sharedCriteria.remove(resourcesToRemove)
  )

  context.sharedKeywordsByAction.get(action)?.delete(normalizedTerm)
  context.sharedCriterionIdsByActionAndTerm.delete(sharedKey(action, normalizedTerm))
}

async function ensureSharedKeyword(
  context: AdsContext,
  action: SharedAction,
  rawTerm: string
) {
  const normalizedTerm = normalizeSearchTerm(rawTerm)
  if (context.sharedKeywordsByAction.get(action)?.has(normalizedTerm)) {
    return
  }

  const sharedSetId = context.sharedSetIdByAction.get(action)
  if (!sharedSetId) {
    throw new Error(`Shared set not found for action ${action}`)
  }

  const response = await runGoogleAdsOperation('create_shared_criterion', () =>
    context.customer.sharedCriteria.create([
      {
        shared_set: ResourceNames.sharedSet(context.customerId, sharedSetId),
        keyword: {
          text: rawTerm,
          match_type: enums.KeywordMatchType.EXACT,
        },
      },
    ])
  )

  context.sharedKeywordsByAction.get(action)?.add(normalizedTerm)

  for (const result of response.results ?? []) {
    const resourceName = result.resource_name
    if (!resourceName) {
      continue
    }
    const criterionId = resourceName.split('~').pop()
    if (criterionId) {
      addToSetMap(
        context.sharedCriterionIdsByActionAndTerm,
        sharedKey(action, normalizedTerm),
        criterionId
      )
    }
  }
}

async function removeCampaignNegative(
  context: AdsContext,
  campaignName: string,
  normalizedTerm: string
) {
  const campaignId = context.campaignIdByName.get(campaignName)
  if (!campaignId) {
    return
  }

  const key = campaignKey(campaignName, normalizedTerm)
  const ids = context.campaignNegativeCriterionIdsByCampaignAndTerm.get(key)
  if (!ids || ids.size === 0) {
    return
  }

  const resourcesToRemove = [...ids].map((criterionId) =>
    ResourceNames.campaignCriterion(context.customerId, campaignId, criterionId)
  )
  await runGoogleAdsOperation('remove_campaign_criteria', () =>
    context.customer.campaignCriteria.remove(resourcesToRemove)
  )

  removeFromSetMap(context.campaignNegativeTermsByCampaign, campaignName, normalizedTerm)
  context.campaignNegativeCriterionIdsByCampaignAndTerm.delete(key)
}

async function ensureCampaignNegative(
  context: AdsContext,
  campaignName: string,
  rawTerm: string
) {
  const normalizedTerm = normalizeSearchTerm(rawTerm)
  if (context.campaignNegativeTermsByCampaign.get(campaignName)?.has(normalizedTerm)) {
    return
  }

  const campaignId = context.campaignIdByName.get(campaignName)
  if (!campaignId) {
    throw new Error(`Campaign not found: ${campaignName}`)
  }

  const response = await runGoogleAdsOperation('create_campaign_criterion', () =>
    context.customer.campaignCriteria.create([
      {
        campaign: ResourceNames.campaign(context.customerId, campaignId),
        negative: true,
        keyword: {
          text: rawTerm,
          match_type: enums.KeywordMatchType.EXACT,
        },
      },
    ])
  )

  addToSetMap(context.campaignNegativeTermsByCampaign, campaignName, normalizedTerm)

  for (const result of response.results ?? []) {
    const resourceName = result.resource_name
    if (!resourceName) {
      continue
    }
    const criterionId = resourceName.split('~').pop()
    if (criterionId) {
      addToSetMap(
        context.campaignNegativeCriterionIdsByCampaignAndTerm,
        campaignKey(campaignName, normalizedTerm),
        criterionId
      )
    }
  }
}

async function removeAdGroupNegative(
  context: AdsContext,
  campaignName: string,
  adGroupName: string,
  normalizedTerm: string
) {
  const pair = `${campaignName}|${adGroupName}`
  const adGroupId = context.adGroupIdByKey.get(pair)
  if (!adGroupId) {
    return
  }

  const key = adGroupKey(campaignName, adGroupName, normalizedTerm)
  const ids = context.adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm.get(key)
  if (!ids || ids.size === 0) {
    return
  }

  const resourcesToRemove = [...ids].map((criterionId) =>
    ResourceNames.adGroupCriterion(context.customerId, adGroupId, criterionId)
  )
  await runGoogleAdsOperation('remove_ad_group_criteria', () =>
    context.customer.adGroupCriteria.remove(resourcesToRemove)
  )

  removeFromSetMap(context.adGroupNegativeTermsByCampaignAdGroup, pair, normalizedTerm)
  context.adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm.delete(key)
}

async function ensureAdGroupNegative(
  context: AdsContext,
  campaignName: string,
  adGroupName: string,
  rawTerm: string
) {
  const normalizedTerm = normalizeSearchTerm(rawTerm)
  const pair = `${campaignName}|${adGroupName}`
  if (context.adGroupNegativeTermsByCampaignAdGroup.get(pair)?.has(normalizedTerm)) {
    return
  }

  const adGroupId = context.adGroupIdByKey.get(pair)
  if (!adGroupId) {
    throw new Error(`Ad group not found for campaign ${campaignName}`)
  }

  const response = await runGoogleAdsOperation('create_ad_group_criterion', () =>
    context.customer.adGroupCriteria.create([
      {
        ad_group: ResourceNames.adGroup(context.customerId, adGroupId),
        negative: true,
        keyword: {
          text: rawTerm,
          match_type: enums.KeywordMatchType.EXACT,
        },
      },
    ])
  )

  addToSetMap(context.adGroupNegativeTermsByCampaignAdGroup, pair, normalizedTerm)

  for (const result of response.results ?? []) {
    const resourceName = result.resource_name
    if (!resourceName) {
      continue
    }
    const criterionId = resourceName.split('~').pop()
    if (criterionId) {
      addToSetMap(
        context.adGroupNegativeCriterionIdsByCampaignAdGroupAndTerm,
        adGroupKey(campaignName, adGroupName, normalizedTerm),
        criterionId
      )
    }
  }
}

async function clearLabelFunnelTerm(
  context: AdsContext,
  label: string,
  normalizedTerm: string
) {
  const campaigns = getLabelCampaignSet(context, label)
  if (!campaigns?.HIGH || !campaigns.MEDIUM || !campaigns.LOW) {
    throw new Error(`Funnel campaigns not fully configured for custom_label_0: ${label}`)
  }

  const names = [campaigns.HIGH, campaigns.MEDIUM, campaigns.LOW]
  for (const campaignName of names) {
    await removeCampaignNegative(context, campaignName, normalizedTerm)
    await removeAdGroupNegative(context, campaignName, campaignName, normalizedTerm)
  }
}

async function applyTierAssignment(
  context: AdsContext,
  rawTerm: string,
  assignment: FunnelDecisionAssignment,
  actionsCompleted: string[]
) {
  const normalizedTerm = normalizeSearchTerm(rawTerm)
  const campaigns = getLabelCampaignSet(context, assignment.custom_label_0)
  if (!campaigns?.HIGH || !campaigns.MEDIUM || !campaigns.LOW) {
    throw new Error(`Funnel campaigns not found for custom_label_0: ${assignment.custom_label_0}`)
  }

  await clearLabelFunnelTerm(context, assignment.custom_label_0, normalizedTerm)
  actionsCompleted.push(`Cleared existing negatives in ${assignment.custom_label_0} funnel`)

  if (assignment.tier === 'campaign_negative') {
    await ensureCampaignNegative(context, campaigns.HIGH, rawTerm)
    await ensureCampaignNegative(context, campaigns.MEDIUM, rawTerm)
    await ensureCampaignNegative(context, campaigns.LOW, rawTerm)
    actionsCompleted.push(
      `Added campaign negatives to HIGH/MEDIUM/LOW for ${assignment.custom_label_0}`
    )
    return
  }

  const blocked = blockedTiersForAssignment(assignment.tier)
  for (const tier of blocked) {
    const campaignName = campaigns[tier]
    if (!campaignName) {
      continue
    }
    await ensureAdGroupNegative(context, campaignName, campaignName, rawTerm)
  }

  actionsCompleted.push(
    `Applied ${assignment.tier.toUpperCase()} targeting for ${assignment.custom_label_0}`
  )
}

async function removeFromAllSharedLists(context: AdsContext, normalizedTerm: string) {
  for (const action of Object.keys(SHARED_LIST_NAME_BY_ACTION) as SharedAction[]) {
    await removeSharedKeyword(context, action, normalizedTerm)
  }
}

export async function postDecisions(
  decisions: PostDecisionItem[],
  options?: { startDate?: string; endDate?: string }
): Promise<PostDecisionsResponse> {
  const dateWindow = buildDateWindow(options?.startDate, options?.endDate)
  const context = await fetchAdsContext(dateWindow)
  const results: PostDecisionResult[] = []

  for (const decision of decisions) {
    const actionsCompleted: string[] = []
    const normalizedTerm = normalizeSearchTerm(decision.search_term)

    try {
      if (decision.action_type === 'funnel') {
        const assignments = decision.assignments ?? []
        if (assignments.length === 0) {
          throw new Error('Funnel decision requires at least one custom_label_0 assignment')
        }

        await removeFromAllSharedLists(context, normalizedTerm)
        for (const assignment of assignments) {
          await applyTierAssignment(context, decision.search_term, assignment, actionsCompleted)
        }
      } else {
        const action = decision.action_type as SharedAction
        await ensureSharedKeyword(context, action, decision.search_term)
        actionsCompleted.push(
          `Added "${decision.search_term}" to ${SHARED_LIST_NAME_BY_ACTION[action]}`
        )
      }

      results.push({
        search_term: decision.search_term,
        status: 'success',
        actions_completed: actionsCompleted,
      })
    } catch (error) {
      results.push({
        search_term: decision.search_term,
        status: 'error',
        actions_completed: actionsCompleted,
        error: error instanceof Error ? error.message : 'Unknown error',
        error_code: getErrorCodeFromUnknown(error),
        retry_count: getRetryCountFromUnknown(error),
      })
    }
  }

  const successCount = results.filter((result) => result.status === 'success').length
  return {
    results,
    success_count: successCount,
    error_count: results.length - successCount,
  }
}

function convertTierLabelToAssignmentTier(value: string): AssignmentTier {
  const normalized = value.toLowerCase().trim()
  if (normalized === 'campaign negative' || normalized === 'campaign_negative') {
    return 'campaign_negative'
  }
  if (normalized === 'high') return 'high'
  if (normalized === 'medium') return 'medium'
  if (normalized === 'low') return 'low'
  throw new Error(`Unsupported tier value: ${value}`)
}

export async function updateExistingAssignments(
  updates: ExistingFunnelUpdate[],
  options?: { startDate?: string; endDate?: string }
): Promise<UpdateExistingResponse> {
  const dateWindow = buildDateWindow(options?.startDate, options?.endDate)
  const context = await fetchAdsContext(dateWindow)
  const results: ExistingFunnelUpdateResult[] = []

  for (const update of updates) {
    const actionsCompleted: string[] = []
    const normalizedTerm = normalizeSearchTerm(update.search_term)
    try {
      if (update.new_action) {
        await clearLabelFunnelTerm(context, update.custom_label_0, normalizedTerm)
        actionsCompleted.push(`Cleared funnel negatives for ${update.custom_label_0}`)

        const action = update.new_action as SharedAction
        await ensureSharedKeyword(context, action, update.search_term)
        actionsCompleted.push(
          `Moved "${update.search_term}" to ${SHARED_LIST_NAME_BY_ACTION[action]}`
        )
      } else if (update.new_tier) {
        const tier = convertTierLabelToAssignmentTier(update.new_tier)
        await removeFromAllSharedLists(context, normalizedTerm)
        await applyTierAssignment(
          context,
          update.search_term,
          { custom_label_0: update.custom_label_0, tier },
          actionsCompleted
        )
      } else {
        throw new Error('Update must include new_tier or new_action')
      }

      results.push({
        search_term: update.search_term,
        custom_label_0: update.custom_label_0,
        status: 'success',
        actions_completed: actionsCompleted,
      })
    } catch (error) {
      results.push({
        search_term: update.search_term,
        custom_label_0: update.custom_label_0,
        status: 'error',
        actions_completed: actionsCompleted,
        error: error instanceof Error ? error.message : 'Unknown error',
        error_code: getErrorCodeFromUnknown(error),
        retry_count: getRetryCountFromUnknown(error),
      })
    }
  }

  const successCount = results.filter((result) => result.status === 'success').length
  return {
    results,
    success_count: successCount,
    error_count: results.length - successCount,
  }
}

export function defaultDateWindow(range: string | null): DateWindow {
  const end = new Date()
  const start = new Date(end)
  switch ((range ?? '30d').toLowerCase()) {
    case '7d':
      start.setDate(start.getDate() - 7)
      break
    case '60d':
      start.setDate(start.getDate() - 60)
      break
    case '90d':
      start.setDate(start.getDate() - 90)
      break
    default:
      start.setDate(start.getDate() - 30)
      break
  }

  return {
    startDate: start.toISOString().split('T')[0],
    endDate: end.toISOString().split('T')[0],
  }
}

export function sanitizeDateInput(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined
  }
  const trimmed = value.trim()
  if (!trimmed) {
    return undefined
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return undefined
  }
  return trimmed
}

export function sanitizeCustomLabel(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined
  }
  const cleaned = value.trim()
  return cleaned.length > 0 ? cleaned : undefined
}

export function sanitizeLimit(value: string | null | undefined, fallback: number, max: number): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return Math.min(Math.floor(parsed), max)
}

export function sanitizeOffset(value: string | null | undefined): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0
  }
  return Math.floor(parsed)
}

export function sanitizeMinImpressions(value: string | null | undefined): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0
  }
  return Math.floor(parsed)
}

export function sanitizeTierFilter(value: string | null | undefined): AssignmentTier | 'all' {
  if (!value) {
    return 'all'
  }
  const normalized = value.toLowerCase()
  if (normalized === 'campaign_negative') return 'campaign_negative'
  if (normalized === 'high') return 'high'
  if (normalized === 'medium') return 'medium'
  if (normalized === 'low') return 'low'
  return 'all'
}

export function shouldShowErrorsOnly(value: string | null | undefined): boolean {
  if (!value) {
    return false
  }
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

export function sharedListNameForAction(action: SharedAction): string {
  return SHARED_LIST_NAME_BY_ACTION[action]
}

export function escapeSearchTermForSql(value: string): string {
  return escapeGaqlLiteral(value)
}

export async function getAvailableCustomLabels(
  options?: { startDate?: string; endDate?: string }
): Promise<string[]> {
  const dateWindow = buildDateWindow(options?.startDate, options?.endDate)
  const context = await fetchAdsContext(dateWindow)
  return [...context.labelCampaigns.keys()].sort((a, b) => a.localeCompare(b))
}

export async function getFunnelCampaignList(
  options?: { startDate?: string; endDate?: string }
): Promise<Array<{ name: string; custom_label_0: string; tier: FunnelTier; id: string }>> {
  const dateWindow = buildDateWindow(options?.startDate, options?.endDate)
  const context = await fetchAdsContext(dateWindow)
  const results: Array<{ name: string; custom_label_0: string; tier: FunnelTier; id: string }> = []

  for (const [label, campaignSet] of context.labelCampaigns.entries()) {
    for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
      const campaignName = campaignSet[tier]
      if (!campaignName) {
        continue
      }
      const campaignId = context.campaignIdByName.get(campaignName)
      if (!campaignId) {
        continue
      }
      results.push({
        id: campaignId,
        name: campaignName,
        custom_label_0: label,
        tier,
      })
    }
  }

  return results.sort((a, b) => a.name.localeCompare(b.name))
}

export async function getShoppingFunnelDataLineage(
  options?: { startDate?: string; endDate?: string }
): Promise<ShoppingFunnelLineageResponse> {
  const dateWindow = buildDateWindow(options?.startDate, options?.endDate)
  const context = await fetchAdsContext(dateWindow)

  const integrity = summarizeCampaignSetIntegrity(
    [...context.campaignIdByName.keys()],
    [...context.adGroupIdByKey.keys()]
  )

  return {
    data_source: SHOPPING_FUNNEL_DATA_SOURCE,
    generated_at: new Date().toISOString(),
    cache_ttl_ms: SHOPPING_FUNNEL_CACHE_TTL_MS,
    date_window: dateWindow,
    integrity,
  }
}
