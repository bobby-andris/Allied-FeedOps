import { google } from 'googleapis'

export interface Ga4CampaignRow {
  channelGroup: string
  campaignName: string
  sessions: number
  transactions: number
  purchaseRevenue: number
}

export interface Ga4CampaignReportResult {
  propertyId: string
  startDate: string
  endDate: string
  rows: Ga4CampaignRow[]
  generatedAt: string
}

export interface Ga4AudienceRow {
  audienceName: string
  sessions: number
  transactions: number
  purchaseRevenue: number
}

export interface Ga4AttributionQuality {
  totalRevenue: number
  unassignedRevenue: number
  notSetCampaignRevenue: number
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  qualityScore: number
  riskLevel: 'low' | 'medium' | 'high'
}

function normalizePropertyId(raw: string): string {
  if (raw.startsWith('properties/')) {
    return raw
  }
  return `properties/${raw}`
}

export function getCanonicalGa4PropertyId(): string {
  const raw =
    process.env.GOOGLE_ANALYTICS_PROPERTY_ID ??
    process.env.GA4_PROPERTY_ID ??
    'properties/342525135'
  return normalizePropertyId(raw)
}

function isNotSetValue(value: string): boolean {
  const normalized = value.toLowerCase().replace(/\s+/g, '')
  return normalized === '(notset)' || normalized === 'notset' || normalized === 'notprovided'
}

function isUnassignedChannel(channelGroup: string): boolean {
  return channelGroup.toLowerCase().trim() === 'unassigned'
}

export function computeAttributionQuality(rows: Ga4CampaignRow[]): Ga4AttributionQuality {
  const totalRevenue = rows.reduce((sum, row) => sum + row.purchaseRevenue, 0)
  const unassignedRevenue = rows
    .filter((row) => isUnassignedChannel(row.channelGroup))
    .reduce((sum, row) => sum + row.purchaseRevenue, 0)
  const notSetCampaignRevenue = rows
    .filter((row) => isNotSetValue(row.campaignName))
    .reduce((sum, row) => sum + row.purchaseRevenue, 0)

  const unassignedRevenueShare = totalRevenue > 0 ? unassignedRevenue / totalRevenue : 0
  const notSetCampaignRevenueShare = totalRevenue > 0 ? notSetCampaignRevenue / totalRevenue : 0

  const qualityScore = Math.max(
    0,
    1 - (unassignedRevenueShare * 0.65 + notSetCampaignRevenueShare * 0.35)
  )

  const riskSignal = Math.max(unassignedRevenueShare, notSetCampaignRevenueShare)
  const riskLevel: 'low' | 'medium' | 'high' =
    riskSignal >= 0.3 ? 'high' : riskSignal >= 0.12 ? 'medium' : 'low'

  return {
    totalRevenue,
    unassignedRevenue,
    notSetCampaignRevenue,
    unassignedRevenueShare,
    notSetCampaignRevenueShare,
    qualityScore: Number(qualityScore.toFixed(4)),
    riskLevel,
  }
}

function getServiceAccountCredentials() {
  const base64Key = process.env.GOOGLE_SERVICE_ACCOUNT_KEY
  if (!base64Key) {
    throw new Error('Missing GOOGLE_SERVICE_ACCOUNT_KEY')
  }

  const decoded = Buffer.from(base64Key, 'base64').toString('utf-8')
  const parsed = JSON.parse(decoded) as {
    client_email: string
    private_key: string
    project_id: string
  }

  if (!parsed.client_email || !parsed.private_key) {
    throw new Error('Invalid GOOGLE_SERVICE_ACCOUNT_KEY credentials payload')
  }

  return parsed
}

function getAnalyticsDataClient() {
  const credentials = getServiceAccountCredentials()
  const auth = new google.auth.GoogleAuth({
    credentials: {
      client_email: credentials.client_email,
      private_key: credentials.private_key,
    },
    projectId: credentials.project_id,
    scopes: ['https://www.googleapis.com/auth/analytics.readonly'],
  })

  return google.analyticsdata({
    version: 'v1beta',
    auth,
  })
}

export async function fetchGa4CampaignPerformance(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}): Promise<Ga4CampaignReportResult> {
  const propertyId = normalizePropertyId(options?.propertyId ?? getCanonicalGa4PropertyId())
  const startDate = options?.startDate ?? '30daysAgo'
  const endDate = options?.endDate ?? 'yesterday'
  const limit = options?.limit ?? 200

  const analyticsData = getAnalyticsDataClient()
  const response = await analyticsData.properties.runReport({
    property: propertyId,
    requestBody: {
      dateRanges: [{ startDate, endDate }],
      dimensions: [{ name: 'sessionDefaultChannelGroup' }, { name: 'sessionCampaignName' }],
      metrics: [{ name: 'sessions' }, { name: 'transactions' }, { name: 'purchaseRevenue' }],
      limit: String(limit),
      orderBys: [{ metric: { metricName: 'purchaseRevenue' }, desc: true }],
    },
  })

  const rows = (response.data.rows ?? []).map((row) => {
    const [channelGroup, campaignName] = row.dimensionValues ?? []
    const [sessions, transactions, purchaseRevenue] = row.metricValues ?? []
    return {
      channelGroup: channelGroup?.value ?? '(unknown)',
      campaignName: campaignName?.value ?? '(unknown)',
      sessions: Number(sessions?.value ?? 0),
      transactions: Number(transactions?.value ?? 0),
      purchaseRevenue: Number(purchaseRevenue?.value ?? 0),
    } satisfies Ga4CampaignRow
  })

  return {
    propertyId,
    startDate,
    endDate,
    rows,
    generatedAt: new Date().toISOString(),
  }
}

export async function fetchGa4AttributionQuality(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}): Promise<
  Ga4AttributionQuality & {
    propertyId: string
    startDate: string
    endDate: string
    generatedAt: string
  }
> {
  const report = await fetchGa4CampaignPerformance(options)
  const quality = computeAttributionQuality(report.rows)

  return {
    ...quality,
    propertyId: report.propertyId,
    startDate: report.startDate,
    endDate: report.endDate,
    generatedAt: report.generatedAt,
  }
}

export async function fetchGa4AudiencePerformance(options?: {
  propertyId?: string
  startDate?: string
  endDate?: string
  limit?: number
}): Promise<{
  propertyId: string
  startDate: string
  endDate: string
  rows: Ga4AudienceRow[]
  generatedAt: string
}> {
  const propertyId = normalizePropertyId(options?.propertyId ?? getCanonicalGa4PropertyId())
  const startDate = options?.startDate ?? '30daysAgo'
  const endDate = options?.endDate ?? 'yesterday'
  const limit = options?.limit ?? 100

  const analyticsData = getAnalyticsDataClient()
  const response = await analyticsData.properties.runReport({
    property: propertyId,
    requestBody: {
      dateRanges: [{ startDate, endDate }],
      dimensions: [{ name: 'audienceName' }],
      metrics: [{ name: 'sessions' }, { name: 'transactions' }, { name: 'purchaseRevenue' }],
      limit: String(limit),
      orderBys: [{ metric: { metricName: 'purchaseRevenue' }, desc: true }],
    },
  })

  const rows = (response.data.rows ?? []).map((row) => {
    const [audienceName] = row.dimensionValues ?? []
    const [sessions, transactions, purchaseRevenue] = row.metricValues ?? []
    return {
      audienceName: audienceName?.value ?? '(unknown)',
      sessions: Number(sessions?.value ?? 0),
      transactions: Number(transactions?.value ?? 0),
      purchaseRevenue: Number(purchaseRevenue?.value ?? 0),
    } satisfies Ga4AudienceRow
  })

  return {
    propertyId,
    startDate,
    endDate,
    rows,
    generatedAt: new Date().toISOString(),
  }
}
