import {
  computeAttributionQuality,
  getCanonicalGa4PropertyId,
  isNotSetValue,
  normalizePropertyId,
  runGa4Report,
} from '@/lib/ga4/client'

export type SourceMediumQualityBucket = 'not_set' | 'data_not_available' | 'valid'
export type LandingPageQualityBucket = 'blank' | 'not_set' | 'valid'
export type CampaignPatternClass = 'not_set' | 'missing_name' | 'nonstandard' | 'valid_named'
export type RootCauseType = 'source_medium' | 'campaign_pattern' | 'landing_page'

export interface Ga4SourceMediumQualityRow {
  sourceMedium: string
  bucket: SourceMediumQualityBucket
  sessions: number
  transactions: number
  purchaseRevenue: number
  revenueShare: number
  sessionShare: number
}

export interface Ga4LandingPageQualityRow {
  landingPage: string
  bucket: LandingPageQualityBucket
  sessions: number
  transactions: number
  purchaseRevenue: number
  revenueShare: number
  sessionShare: number
}

export interface Ga4CampaignPatternRow {
  campaignName: string
  patternClass: CampaignPatternClass
  sessions: number
  transactions: number
  purchaseRevenue: number
  revenueShare: number
  sessionShare: number
}

export interface Ga4AttributionRootCauseRow {
  rootCauseType: RootCauseType
  rootCauseKey: string
  sessions: number
  transactions: number
  purchaseRevenue: number
  revenueShare: number
  sessionShare: number
  sampleValues: string[]
}

export interface Ga4AttributionTrendPoint {
  reportDate: string
  totalRevenue: number
  unassignedRevenue: number
  notSetCampaignRevenue: number
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  qualityScore: number
}

export interface Ga4ShopifyReconciliationSummary {
  propertyId: string
  startDate: string
  endDate: string
  ga4Revenue: number
  shopifyRevenue: number
  revenueDelta: number
  revenueRatio: number | null
  orderCount: number
  generatedAt: string
}

export interface AttributionIncidentSummary {
  ruleId: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'open' | 'acknowledged' | 'resolved' | 'ignored'
  message: string
  impactedEntities: Array<Record<string, unknown>>
  metadata: Record<string, unknown>
  triggered: boolean
}

export interface ResolvedGa4DateWindow {
  startDate: string
  endDate: string
  start: Date
  end: Date
  lookbackDays: number
}

const VALID_CAMPAIGN_PATTERNS: RegExp[] = [
  /^AVD - Shopping - US - .+ - (HIGH|MEDIUM|LOW)(?: \((HIGH|MEDIUM|LOW)\))?$/i,
  /^AVD - Shopping - BRANDED - US$/i,
]

function clampNumeric(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  return value
}

function normalizeDimensionValue(value: string | undefined): string {
  return (value ?? '').trim()
}

function normalizeNotSetToken(value: string): string {
  return value.toLowerCase().replace(/\s+/g, '')
}

function formatIsoDate(date: Date): string {
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseRelativeDate(input: string, now: Date): Date {
  const normalized = input.trim().toLowerCase()
  if (normalized === 'today') {
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  }
  if (normalized === 'yesterday') {
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 1))
  }
  const agoMatch = normalized.match(/^(\d+)daysago$/)
  if (agoMatch) {
    const days = Number(agoMatch[1])
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - days))
  }

  const parsed = new Date(input)
  if (!Number.isNaN(parsed.getTime())) {
    return new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()))
  }

  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
}

function parseGa4DateDimension(value: string): string {
  if (!/^\d{8}$/.test(value)) {
    return value
  }

  const year = value.slice(0, 4)
  const month = value.slice(4, 6)
  const day = value.slice(6, 8)
  return `${year}-${month}-${day}`
}

function summarizeShares<T extends { sessions: number; purchaseRevenue: number }, U>(
  rows: T[],
  mapper: (row: T, revenueShare: number, sessionShare: number) => U
): U[] {
  const totalRevenue = rows.reduce((sum, row) => sum + row.purchaseRevenue, 0)
  const totalSessions = rows.reduce((sum, row) => sum + row.sessions, 0)

  return rows.map((row) => {
    const revenueShare = totalRevenue > 0 ? row.purchaseRevenue / totalRevenue : 0
    const sessionShare = totalSessions > 0 ? row.sessions / totalSessions : 0
    return mapper(row, Number(revenueShare.toFixed(6)), Number(sessionShare.toFixed(6)))
  })
}

export function classifySourceMedium(value: string): SourceMediumQualityBucket {
  const normalized = normalizeDimensionValue(value)
  if (!normalized || isNotSetValue(normalized)) {
    return 'not_set'
  }

  const compact = normalizeNotSetToken(normalized)
  if (
    compact === '(datanotavailable)' ||
    compact === 'datanotavailable' ||
    compact.includes('datanotavailable')
  ) {
    return 'data_not_available'
  }

  return 'valid'
}

export function classifyLandingPage(value: string): LandingPageQualityBucket {
  const normalized = normalizeDimensionValue(value)
  if (!normalized) {
    return 'blank'
  }
  if (isNotSetValue(normalized)) {
    return 'not_set'
  }
  return 'valid'
}

export function classifyCampaignPattern(value: string): CampaignPatternClass {
  const normalized = normalizeDimensionValue(value)
  if (!normalized) {
    return 'missing_name'
  }
  if (isNotSetValue(normalized)) {
    return 'not_set'
  }

  const matchesKnownPattern = VALID_CAMPAIGN_PATTERNS.some((pattern) => pattern.test(normalized))
  return matchesKnownPattern ? 'valid_named' : 'nonstandard'
}

export function resolveGa4DateWindow(
  startDateInput: string | undefined,
  endDateInput: string | undefined
): ResolvedGa4DateWindow {
  const now = new Date()
  const startValue = startDateInput ?? '30daysAgo'
  const endValue = endDateInput ?? 'yesterday'

  const parsedStart = parseRelativeDate(startValue, now)
  const parsedEnd = parseRelativeDate(endValue, now)
  const start = parsedStart <= parsedEnd ? parsedStart : parsedEnd
  const end = parsedEnd >= parsedStart ? parsedEnd : parsedStart
  const lookbackMs = end.getTime() - start.getTime()
  const lookbackDays = Math.max(1, Math.floor(lookbackMs / (24 * 60 * 60 * 1000)) + 1)

  return {
    startDate: formatIsoDate(start),
    endDate: formatIsoDate(end),
    start,
    end,
    lookbackDays,
  }
}

export async function fetchGa4SourceMediumQuality(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}) {
  const report = await runGa4Report({
    propertyId: options?.propertyId,
    startDate: options?.startDate,
    endDate: options?.endDate,
    limit: options?.limit ?? 2000,
    dimensions: ['sessionSourceMedium'],
    metrics: ['sessions', 'transactions', 'purchaseRevenue'],
    orderBys: [{ metric: { metricName: 'purchaseRevenue' }, desc: true }],
  })

  const rows = summarizeShares(
    report.rows.map((row) => {
      const [sourceMedium] = row.dimensions
      const [sessions, transactions, purchaseRevenue] = row.metrics
      return {
        sourceMedium: normalizeDimensionValue(sourceMedium) || '(blank)',
        bucket: classifySourceMedium(sourceMedium ?? ''),
        sessions: clampNumeric(sessions),
        transactions: clampNumeric(transactions),
        purchaseRevenue: clampNumeric(purchaseRevenue),
      } satisfies Omit<Ga4SourceMediumQualityRow, 'revenueShare' | 'sessionShare'>
    }),
    (row, revenueShare, sessionShare) => ({
      ...row,
      revenueShare,
      sessionShare,
    })
  )

  return {
    propertyId: report.propertyId,
    startDate: report.startDate,
    endDate: report.endDate,
    rows,
    generatedAt: report.generatedAt,
  }
}

export async function fetchGa4LandingPageQuality(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}) {
  const report = await runGa4Report({
    propertyId: options?.propertyId,
    startDate: options?.startDate,
    endDate: options?.endDate,
    limit: options?.limit ?? 3000,
    dimensions: ['landingPagePlusQueryString'],
    metrics: ['sessions', 'transactions', 'purchaseRevenue'],
    orderBys: [{ metric: { metricName: 'purchaseRevenue' }, desc: true }],
  })

  const rows = summarizeShares(
    report.rows.map((row) => {
      const [landingPage] = row.dimensions
      const [sessions, transactions, purchaseRevenue] = row.metrics
      return {
        landingPage: normalizeDimensionValue(landingPage) || '(blank)',
        bucket: classifyLandingPage(landingPage ?? ''),
        sessions: clampNumeric(sessions),
        transactions: clampNumeric(transactions),
        purchaseRevenue: clampNumeric(purchaseRevenue),
      } satisfies Omit<Ga4LandingPageQualityRow, 'revenueShare' | 'sessionShare'>
    }),
    (row, revenueShare, sessionShare) => ({
      ...row,
      revenueShare,
      sessionShare,
    })
  )

  return {
    propertyId: report.propertyId,
    startDate: report.startDate,
    endDate: report.endDate,
    rows,
    generatedAt: report.generatedAt,
  }
}

export async function fetchGa4CampaignPatternQuality(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}) {
  const report = await runGa4Report({
    propertyId: options?.propertyId,
    startDate: options?.startDate,
    endDate: options?.endDate,
    limit: options?.limit ?? 3000,
    dimensions: ['sessionCampaignName'],
    metrics: ['sessions', 'transactions', 'purchaseRevenue'],
    orderBys: [{ metric: { metricName: 'purchaseRevenue' }, desc: true }],
  })

  const rows = summarizeShares(
    report.rows.map((row) => {
      const [campaignName] = row.dimensions
      const [sessions, transactions, purchaseRevenue] = row.metrics
      return {
        campaignName: normalizeDimensionValue(campaignName) || '(blank)',
        patternClass: classifyCampaignPattern(campaignName ?? ''),
        sessions: clampNumeric(sessions),
        transactions: clampNumeric(transactions),
        purchaseRevenue: clampNumeric(purchaseRevenue),
      } satisfies Omit<Ga4CampaignPatternRow, 'revenueShare' | 'sessionShare'>
    }),
    (row, revenueShare, sessionShare) => ({
      ...row,
      revenueShare,
      sessionShare,
    })
  )

  return {
    propertyId: report.propertyId,
    startDate: report.startDate,
    endDate: report.endDate,
    rows,
    generatedAt: report.generatedAt,
  }
}

export function buildRootCauseRows(input: {
  sourceMediumRows: Ga4SourceMediumQualityRow[]
  landingPageRows: Ga4LandingPageQualityRow[]
  campaignPatternRows: Ga4CampaignPatternRow[]
}): Ga4AttributionRootCauseRow[] {
  const results: Ga4AttributionRootCauseRow[] = []

  const aggregateByKey = <T extends { sessions: number; transactions: number; purchaseRevenue: number }>(
    type: RootCauseType,
    rows: T[],
    keyOf: (row: T) => string,
    sampleOf: (row: T) => string
  ) => {
    const totalRevenue = rows.reduce((sum, row) => sum + row.purchaseRevenue, 0)
    const totalSessions = rows.reduce((sum, row) => sum + row.sessions, 0)
    const byKey = new Map<string, { sessions: number; transactions: number; purchaseRevenue: number; sampleValues: Set<string> }>()

    for (const row of rows) {
      const key = keyOf(row)
      const current = byKey.get(key) ?? {
        sessions: 0,
        transactions: 0,
        purchaseRevenue: 0,
        sampleValues: new Set<string>(),
      }
      current.sessions += row.sessions
      current.transactions += row.transactions
      current.purchaseRevenue += row.purchaseRevenue
      current.sampleValues.add(sampleOf(row))
      byKey.set(key, current)
    }

    for (const [rootCauseKey, value] of byKey.entries()) {
      const revenueShare = totalRevenue > 0 ? value.purchaseRevenue / totalRevenue : 0
      const sessionShare = totalSessions > 0 ? value.sessions / totalSessions : 0
      results.push({
        rootCauseType: type,
        rootCauseKey,
        sessions: value.sessions,
        transactions: value.transactions,
        purchaseRevenue: Number(value.purchaseRevenue.toFixed(4)),
        revenueShare: Number(revenueShare.toFixed(6)),
        sessionShare: Number(sessionShare.toFixed(6)),
        sampleValues: [...value.sampleValues].slice(0, 10),
      })
    }
  }

  aggregateByKey(
    'source_medium',
    input.sourceMediumRows,
    (row) => row.bucket,
    (row) => row.sourceMedium
  )
  aggregateByKey(
    'campaign_pattern',
    input.campaignPatternRows,
    (row) => row.patternClass,
    (row) => row.campaignName
  )
  aggregateByKey(
    'landing_page',
    input.landingPageRows,
    (row) => row.bucket,
    (row) => row.landingPage
  )

  return results.sort((a, b) => b.purchaseRevenue - a.purchaseRevenue)
}

export function computeLandingInvalidRevenueShare(rows: Ga4LandingPageQualityRow[]): number {
  const totalRevenue = rows.reduce((sum, row) => sum + row.purchaseRevenue, 0)
  if (totalRevenue <= 0) {
    return 0
  }

  const invalidRevenue = rows
    .filter((row) => row.bucket === 'blank' || row.bucket === 'not_set')
    .reduce((sum, row) => sum + row.purchaseRevenue, 0)

  return Number((invalidRevenue / totalRevenue).toFixed(6))
}

export function isReconciliationOutOfRange(ratio: number | null | undefined): boolean {
  if (typeof ratio !== 'number' || !Number.isFinite(ratio)) {
    return false
  }
  return ratio < 0.8 || ratio > 1.2
}

export function computeConsecutiveOutOfRangeStreak(
  ratiosOrderedLatestFirst: Array<number | null | undefined>
): number {
  let streak = 0
  for (const ratio of ratiosOrderedLatestFirst) {
    if (!isReconciliationOutOfRange(ratio)) {
      break
    }
    streak += 1
  }
  return streak
}

export function evaluateAttributionIncidents(input: {
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  landingInvalidRevenueShare: number
  reconciliationRatio: number | null
  reconciliationOutOfRangeStreak: number
  propertyId: string
  reportDate: string
}): AttributionIncidentSummary[] {
  const incidents: AttributionIncidentSummary[] = []

  if (input.unassignedRevenueShare >= 0.25) {
    incidents.push({
      ruleId: 'ga4_unassigned_revenue_share',
      severity: 'critical',
      status: 'open',
      message: `Unassigned revenue share is ${(input.unassignedRevenueShare * 100).toFixed(2)}%, above 25% threshold.`,
      impactedEntities: [{ property_id: input.propertyId }],
      metadata: {
        report_date: input.reportDate,
        observed_share: input.unassignedRevenueShare,
        threshold: 0.25,
      },
      triggered: true,
    })
  }

  if (input.notSetCampaignRevenueShare >= 0.15) {
    incidents.push({
      ruleId: 'ga4_not_set_campaign_revenue_share',
      severity: 'high',
      status: 'open',
      message: `(not set) campaign revenue share is ${(input.notSetCampaignRevenueShare * 100).toFixed(2)}%, above 15% threshold.`,
      impactedEntities: [{ property_id: input.propertyId }],
      metadata: {
        report_date: input.reportDate,
        observed_share: input.notSetCampaignRevenueShare,
        threshold: 0.15,
      },
      triggered: true,
    })
  }

  if (input.landingInvalidRevenueShare >= 0.1) {
    incidents.push({
      ruleId: 'ga4_invalid_landing_page_revenue_share',
      severity: 'high',
      status: 'open',
      message: `Landing page blank/(not set) revenue share is ${(input.landingInvalidRevenueShare * 100).toFixed(2)}%, above 10% threshold.`,
      impactedEntities: [{ property_id: input.propertyId }],
      metadata: {
        report_date: input.reportDate,
        observed_share: input.landingInvalidRevenueShare,
        threshold: 0.1,
      },
      triggered: true,
    })
  }

  if (
    isReconciliationOutOfRange(input.reconciliationRatio) &&
    input.reconciliationOutOfRangeStreak >= 3
  ) {
    incidents.push({
      ruleId: 'ga4_shopify_reconciliation_ratio',
      severity: 'medium',
      status: 'open',
      message:
        `GA4/Shopify reconciliation ratio is ${
          (input.reconciliationRatio ?? 0).toFixed(4)
        } and has remained outside [0.80, 1.20] for ${input.reconciliationOutOfRangeStreak} consecutive snapshots.`,
      impactedEntities: [{ property_id: input.propertyId }],
      metadata: {
        report_date: input.reportDate,
        ratio: input.reconciliationRatio,
        streak: input.reconciliationOutOfRangeStreak,
        lower_bound: 0.8,
        upper_bound: 1.2,
      },
      triggered: true,
    })
  }

  return incidents
}

export async function fetchGa4AttributionTrend(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}) {
  const report = await runGa4Report({
    propertyId: options?.propertyId,
    startDate: options?.startDate,
    endDate: options?.endDate,
    limit: options?.limit ?? 20000,
    dimensions: ['date', 'sessionDefaultChannelGroup', 'sessionCampaignName'],
    metrics: ['sessions', 'transactions', 'purchaseRevenue'],
    orderBys: [{ dimension: { dimensionName: 'date' }, desc: false }],
  })

  const byDate = new Map<
    string,
    Array<{
      channelGroup: string
      campaignName: string
      sessions: number
      transactions: number
      purchaseRevenue: number
    }>
  >()

  for (const row of report.rows) {
    const [dateRaw, channelGroup, campaignName] = row.dimensions
    const [sessions, transactions, purchaseRevenue] = row.metrics
    const date = parseGa4DateDimension(dateRaw ?? '')
    const current = byDate.get(date) ?? []
    current.push({
      channelGroup: channelGroup ?? '(unknown)',
      campaignName: campaignName ?? '(unknown)',
      sessions: clampNumeric(sessions),
      transactions: clampNumeric(transactions),
      purchaseRevenue: clampNumeric(purchaseRevenue),
    })
    byDate.set(date, current)
  }

  const points: Ga4AttributionTrendPoint[] = [...byDate.entries()]
    .map(([reportDate, rows]) => {
      const quality = computeAttributionQuality(rows)
      return {
        reportDate,
        totalRevenue: Number(quality.totalRevenue.toFixed(4)),
        unassignedRevenue: Number(quality.unassignedRevenue.toFixed(4)),
        notSetCampaignRevenue: Number(quality.notSetCampaignRevenue.toFixed(4)),
        unassignedRevenueShare: Number(quality.unassignedRevenueShare.toFixed(6)),
        notSetCampaignRevenueShare: Number(quality.notSetCampaignRevenueShare.toFixed(6)),
        qualityScore: Number(quality.qualityScore.toFixed(6)),
      }
    })
    .sort((a, b) => a.reportDate.localeCompare(b.reportDate))

  return {
    propertyId: report.propertyId,
    startDate: report.startDate,
    endDate: report.endDate,
    points,
    generatedAt: report.generatedAt,
  }
}

export function getNormalizedForensicsPropertyId(rawPropertyId?: string): string {
  return normalizePropertyId(rawPropertyId ?? getCanonicalGa4PropertyId())
}
