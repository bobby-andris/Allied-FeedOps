import { computePlatformReadiness, type PlatformReadinessByPlatform } from '@/lib/publishing/platform-readiness'
import type { Platform } from '@/lib/publishing/types'

const PLATFORM_ORDER: Platform[] = ['google', 'bing', 'shopify']

type ApprovalFlag = boolean | number | string | null | undefined

export interface ContentApprovalRecord {
  platform: string | null
  content_type: string | null
  approved_content: string | null
}

export interface VariantRecord {
  finish: string | null
}

export interface VariantApprovalRecord {
  finish: string | null
  approval_status: string | null
  title_approved: ApprovalFlag
  description_approved: ApprovalFlag
}

export interface VariantImageRecord {
  finish: string | null
  approval_status: string | null
  user_selected: boolean | null
}

export interface PublishEventSnapshotRecord {
  platform: string | null
  published_at: string | null
  published_title: string | null
  published_description: string | null
  content_version: number | null
}

export interface LatestPublishSnapshot {
  publishedAt: string
  publishedTitle: string | null
  publishedDescription: string | null
  contentVersion: number | null
}

export interface PlatformProgress {
  platform: Platform
  state: 'published' | 'partial' | 'ready' | 'blocked'
  ready: boolean
  blockerSummary: string | null
  publishedSnapshot: LatestPublishSnapshot | null
}

export interface PlatformContentState {
  titleApproved: boolean
  descriptionApproved: boolean
}

function isApprovedFlag(value: ApprovalFlag): boolean {
  return value === true || value === 1 || value === '1'
}

function isPlatform(value: string | null | undefined): value is Platform {
  return value === 'google' || value === 'bing' || value === 'shopify'
}

export function computePlatformReadinessForSku(args: {
  contentRecords: ContentApprovalRecord[]
  variants: VariantRecord[]
  variantApprovals: VariantApprovalRecord[]
  variantImages: VariantImageRecord[]
  shopifyMasterImageReady?: boolean
}): PlatformReadinessByPlatform {
  const requiredVariantFinishes = new Set(
    args.variants
      .map((variant) => variant.finish)
      .filter((finish): finish is string => Boolean(finish)),
  )

  const approvedVariantContentFinishes = new Set(
    args.variantApprovals
      .filter((approval) =>
        approval.finish
        && approval.approval_status === 'approved'
        && isApprovedFlag(approval.title_approved)
        && isApprovedFlag(approval.description_approved),
      )
      .map((approval) => approval.finish as string),
  )

  const selectedVariantImageFinishes = new Set(
    args.variantImages
      .filter((image) => image.finish && image.approval_status === 'approved' && image.user_selected)
      .map((image) => image.finish as string),
  )

  const contentByPlatform: Record<Platform, { titleApproved: boolean; descriptionApproved: boolean }> = {
    google: { titleApproved: false, descriptionApproved: false },
    bing: { titleApproved: false, descriptionApproved: false },
    shopify: { titleApproved: false, descriptionApproved: false },
  }

  for (const record of args.contentRecords) {
    if (!isPlatform(record.platform)) {
      continue
    }
    if (record.content_type === 'title' && record.approved_content) {
      contentByPlatform[record.platform].titleApproved = true
    }
    if (record.content_type === 'description' && record.approved_content) {
      contentByPlatform[record.platform].descriptionApproved = true
    }
  }

  return computePlatformReadiness({
    content: contentByPlatform,
    variantApprovalsReady:
      requiredVariantFinishes.size > 0 && approvedVariantContentFinishes.size >= requiredVariantFinishes.size,
    variantImagesReady:
      requiredVariantFinishes.size > 0 && selectedVariantImageFinishes.size >= requiredVariantFinishes.size,
    shopifyMasterImageReady: Boolean(args.shopifyMasterImageReady),
  })
}

export function latestProductionPublishSnapshots(
  events: PublishEventSnapshotRecord[],
): Partial<Record<Platform, LatestPublishSnapshot>> {
  const snapshots: Partial<Record<Platform, LatestPublishSnapshot>> = {}

  for (const event of events) {
    if (!isPlatform(event.platform) || !event.published_at) {
      continue
    }
    const existing = snapshots[event.platform]
    if (!existing || new Date(event.published_at).getTime() > new Date(existing.publishedAt).getTime()) {
      snapshots[event.platform] = {
        publishedAt: event.published_at,
        publishedTitle: event.published_title,
        publishedDescription: event.published_description,
        contentVersion: event.content_version,
      }
    }
  }

  return snapshots
}

export function computeContentStateByPlatform(
  contentRecords: ContentApprovalRecord[],
): Partial<Record<Platform, PlatformContentState>> {
  const result: Partial<Record<Platform, PlatformContentState>> = {}
  for (const record of contentRecords) {
    if (!isPlatform(record.platform)) continue
    if (!result[record.platform]) result[record.platform] = { titleApproved: false, descriptionApproved: false }
    if (record.content_type === 'title' && record.approved_content) result[record.platform]!.titleApproved = true
    if (record.content_type === 'description' && record.approved_content) result[record.platform]!.descriptionApproved = true
  }
  return result
}

export function buildPlatformProgress(
  readiness: PlatformReadinessByPlatform,
  snapshots: Partial<Record<Platform, LatestPublishSnapshot>>,
  contentState?: Partial<Record<Platform, PlatformContentState>>,
): PlatformProgress[] {
  return PLATFORM_ORDER.map((platform) => {
    const publishedSnapshot = snapshots[platform] ?? null
    const readinessResult = readiness[platform]
    const blockerSummary = readinessResult.blockers[0]?.actionableMessage ?? null

    const cs = contentState?.[platform]
    const isPartial = cs != null && (cs.titleApproved || cs.descriptionApproved) && !(cs.titleApproved && cs.descriptionApproved)

    const state: PlatformProgress['state'] = publishedSnapshot
      ? 'published'
      : readinessResult.ready
        ? 'ready'
        : isPartial
          ? 'partial'
          : 'blocked'

    return {
      platform,
      state,
      ready: readinessResult.ready,
      blockerSummary,
      publishedSnapshot,
    }
  })
}
