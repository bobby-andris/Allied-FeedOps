'use client'

import { useMemo, useCallback, useState, useRef, useEffect } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { ChevronRight } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { skuToUrlPath } from "@/lib/sku-utils"
import type { PlatformProgress } from "@/lib/review/platform-progress"
import type { PlatformContentState } from "@/lib/review/platform-progress"
import type { Platform } from "@/lib/publishing/types"
import type { LifestyleImageLifecycle } from "@/app/(dashboard)/review/page"

interface SkuRow {
  master_sku: string
  approval_status: string | null
  product_title: string | null
  thumbnail_url: string | null
  avg_quality_score: number | null
  platform_progress: PlatformProgress[]
  per_platform_approval: Partial<Record<Platform, PlatformContentState>>
  legacy_published_by_platform: Partial<Record<Platform, boolean>>
  lifestyle_images: LifestyleImageLifecycle
}

interface ReviewListClientProps {
  skus: SkuRow[]
}

type BadgeState = PlatformProgress['state']
type StatusFilter = 'all' | 'needs-review' | 'partial' | 'approved' | 'published' | 'published-legacy'
const STATUS_FILTERS: StatusFilter[] = ['all', 'needs-review', 'partial', 'approved', 'published', 'published-legacy']

interface BadgeStyle {
  className: string
  label: string
}

function getPlatformBadgeStyle(state: BadgeState, isLegacyMethod = false): BadgeStyle {
  if (state === 'published' && isLegacyMethod) {
    return { className: 'bg-orange-100 text-orange-800', label: 'Published (Legacy)' }
  }
  switch (state) {
    case 'published':
      return { className: 'bg-green-100 text-green-800', label: 'Published' }
    case 'ready':
      return { className: 'bg-blue-100 text-blue-800', label: 'Approved' }
    case 'partial':
      return { className: 'bg-yellow-100 text-yellow-800', label: 'Partial' }
    case 'blocked':
    default:
      return { className: 'bg-gray-100 text-gray-600', label: 'Review' }
  }
}

function isPlatform(value: string): value is Platform {
  return value === 'google' || value === 'bing' || value === 'shopify'
}

function getPlatformAbbrev(platform: Platform): string {
  switch (platform) {
    case 'google':
      return 'G'
    case 'bing':
      return 'B'
    case 'shopify':
      return 'S'
  }
}

function getPlatformLabel(platform: Platform): string {
  switch (platform) {
    case 'google':
      return 'Google'
    case 'bing':
      return 'Bing'
    case 'shopify':
      return 'Shopify'
  }
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

function PlatformBadge({
  progress,
  isLegacyMethod = false,
}: {
  progress: PlatformProgress
  isLegacyMethod?: boolean
}) {
  const abbrev = getPlatformAbbrev(progress.platform)
  const { className, label } = getPlatformBadgeStyle(progress.state, isLegacyMethod)
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${className}`}
      title={progress.blockerSummary || undefined}
    >
      {abbrev}: {label}
    </span>
  )
}

function SkuThumbnail({ url, sku }: { url: string | null; sku: string }) {
  if (url) {
    return (
      <img
        src={url}
        alt={sku}
        className="w-10 h-10 object-cover rounded flex-shrink-0"
      />
    )
  }
  return (
    <div className="w-10 h-10 rounded bg-muted flex-shrink-0" />
  )
}

const PLATFORMS: Platform[] = ['google', 'bing', 'shopify']

// Compact inline badge for the list row
function ImageRowBadge({ images }: { images: LifestyleImageLifecycle }) {
  const { total, approved, published } = images
  if (published > 0) {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-800">
        Img: Published
      </span>
    )
  }
  if (approved > 0) {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-800">
        Img: Approved
      </span>
    )
  }
  if (total > 0) {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800">
        Img: Generated
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-500">
      Img: None
    </span>
  )
}

// Full panel badge with counts and guidance text
function LifestyleImageBadge({ images }: { images: LifestyleImageLifecycle }) {
  const { total, approved, published } = images

  if (total === 0) {
    return (
      <div className="flex items-center gap-2 pt-1 border-t border-border/20">
        <span className="text-xs text-muted-foreground">Lifestyle image:</span>
        <span className="text-xs px-2 py-0.5 rounded font-medium bg-gray-100 text-gray-500">
          None generated
        </span>
      </div>
    )
  }

  if (published > 0) {
    return (
      <div className="flex items-center gap-2 pt-1 border-t border-border/20">
        <span className="text-xs text-muted-foreground">Lifestyle image:</span>
        <span className="text-xs px-2 py-0.5 rounded font-medium bg-green-100 text-green-800">
          ✓ Published — {published}/{total} variant{total !== 1 ? 's' : ''} on Shopify
        </span>
      </div>
    )
  }

  if (approved > 0) {
    return (
      <div className="flex items-center gap-2 pt-1 border-t border-border/20">
        <span className="text-xs text-muted-foreground">Lifestyle image:</span>
        <span className="text-xs px-2 py-0.5 rounded font-medium bg-blue-100 text-blue-800">
          Approved — {approved}/{total} variant{total !== 1 ? 's' : ''}, not yet published
        </span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 pt-1 border-t border-border/20">
      <span className="text-xs text-muted-foreground">Lifestyle image:</span>
      <span className="text-xs px-2 py-0.5 rounded font-medium bg-yellow-100 text-yellow-800">
        Generated — {total} variant{total !== 1 ? 's' : ''}, needs approval
      </span>
    </div>
  )
}

function SkuPreviewPanel({
  sku,
  optimisticApprovals,
  onApprove,
  onClose,
}: {
  sku: SkuRow
  optimisticApprovals: Set<string>
  onApprove: (platform: string) => void
  onClose: () => void
}) {
  return (
    <div className="border-l-4 border-primary/30 bg-muted/20 ml-4">
      {/* Header row: title + prominent Open Full Review button */}
      <div className="flex items-start justify-between gap-4 px-4 pt-4 pb-3 border-b border-border/30">
        <div>
          <p className="text-sm font-semibold">{sku.product_title ?? sku.master_sku}</p>
          {sku.avg_quality_score !== null && (
            <p className={`text-xs mt-0.5 ${getScoreColor(sku.avg_quality_score)}`}>
              Quality score: {sku.avg_quality_score}
            </p>
          )}
        </div>
        <Link
          href={`/review/${skuToUrlPath(sku.master_sku)}`}
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Open Full Review
          <ChevronRight className="h-3 w-3" />
        </Link>
      </div>

      <div className="px-4 py-3 space-y-3">
        {/* Per-platform content status + approval buttons */}
        <div className="space-y-2">
          {PLATFORMS.map(platform => {
            const progress = sku.platform_progress.find(p => p.platform === platform)
            const alreadyPublished = progress?.state === 'published'
            const alreadyApproved = progress?.state === 'ready' || optimisticApprovals.has(platform)
            const isLegacyPublished = Boolean(sku.legacy_published_by_platform[platform])
            const { className: badgeClass, label: stateLabel } = getPlatformBadgeStyle(
              progress?.state ?? 'blocked',
              isLegacyPublished,
            )
            const platformLabel = getPlatformLabel(platform)
            return (
              <div key={platform} className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${badgeClass}`}>
                  {platformLabel}: {stateLabel}
                </span>
                {!alreadyPublished && !alreadyApproved && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onApprove(platform) }}
                    className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                  >
                    Mark Approved
                  </button>
                )}
                {alreadyApproved && !alreadyPublished && (
                  <span className="text-xs text-blue-600 font-medium">Approved</span>
                )}
              </div>
            )
          })}
        </div>

        {/* Lifestyle image lifecycle */}
        <LifestyleImageBadge images={sku.lifestyle_images} />

        {/* Close link */}
        <div className="flex justify-end">
          <button
            onClick={(e) => { e.stopPropagation(); onClose() }}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export function ReviewListClient({ skus }: ReviewListClientProps) {
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const router = useRouter()

  const statusParam = searchParams.get('status')
  const activeStatus: StatusFilter = STATUS_FILTERS.includes(statusParam as StatusFilter)
    ? (statusParam as StatusFilter)
    : 'all'
  const activePlatform = searchParams.get('platform') ?? 'all'

  // Inline expand state
  const [expandedSku, setExpandedSku] = useState<string | null>(null)
  // Optimistic approval state: tracks which platforms have been approved in this session
  const [optimisticApprovals, setOptimisticApprovals] = useState<Record<string, Set<string>>>({})

  // Ref for auto-scroll to expanded panel
  const expandedRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (expandedSku && expandedRef.current) {
      expandedRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [expandedSku])

  const applyFilter = useCallback((status: StatusFilter, platform: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (status === 'all') params.delete('status')
    else params.set('status', status)
    if (platform === 'all') params.delete('platform')
    else params.set('platform', platform)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }, [searchParams, pathname, router])

  const handleQuickApprove = useCallback(async (masterSku: string, platform: string) => {
    // Optimistic update
    setOptimisticApprovals(prev => ({
      ...prev,
      [masterSku]: new Set([...(prev[masterSku] ?? []), platform]),
    }))

    try {
      const res = await fetch('/api/review/approve-platform', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ master_sku: masterSku, platform }),
      })
      if (!res.ok) {
        // Rollback optimistic update on failure
        setOptimisticApprovals(prev => {
          const updated = new Set(prev[masterSku] ?? [])
          updated.delete(platform)
          return { ...prev, [masterSku]: updated }
        })
        console.error('Approval failed:', await res.text())
      }
    } catch {
      // Rollback on network error
      setOptimisticApprovals(prev => {
        const updated = new Set(prev[masterSku] ?? [])
        updated.delete(platform)
        return { ...prev, [masterSku]: updated }
      })
    }
  }, [])

  // Compute per-platform 4-state counts from already-fetched SKU data
  const stats = useMemo(() => {
    const platforms = ['google', 'bing', 'shopify'] as const
    return platforms.map(platform => {
      const platformProgress = skus.map(sku =>
        sku.platform_progress.find(p => p.platform === platform)
      )
      return {
        platform,
        label: platform === 'google' ? 'Google' : platform === 'bing' ? 'Bing' : 'Shopify',
        needsReview: platformProgress.filter(p => p?.state === 'blocked').length,
        partial: platformProgress.filter(p => p?.state === 'partial').length,
        approved: platformProgress.filter(p => p?.state === 'ready').length,
        published: platformProgress.filter(p => p?.state === 'published').length,
        legacyPublished: skus.filter(sku => Boolean(sku.legacy_published_by_platform[platform])).length,
      }
    })
  }, [skus])

  // Filter SKUs by active status and platform
  const filteredSkus = useMemo(() => {
    return skus.filter(sku => {
      const platformsToCheck = activePlatform === 'all'
        ? sku.platform_progress
        : sku.platform_progress.filter(p => p.platform === activePlatform)

      if (activeStatus === 'all') return true
      if (activeStatus === 'published-legacy') {
        if (activePlatform === 'all') {
          return Object.values(sku.legacy_published_by_platform).some(Boolean)
        }
        return isPlatform(activePlatform) && Boolean(sku.legacy_published_by_platform[activePlatform])
      }

      const targetState = activeStatus === 'needs-review' ? 'blocked'
        : activeStatus === 'partial' ? 'partial'
        : activeStatus === 'approved' ? 'ready'
        : 'published' // activeStatus === 'published'

      return platformsToCheck.some(p => p.state === targetState)
    })
  }, [skus, activeStatus, activePlatform])

  return (
    <div>
      {/* Stats summary bar */}
      <div className="grid grid-cols-3 gap-3 mb-4 p-4 bg-muted/30 rounded-lg">
        {stats.map(s => (
          <div key={s.platform} className="space-y-2">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {s.label}
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => applyFilter('needs-review', s.platform)}
                className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                {s.needsReview} Needs Review
              </button>
              <button
                onClick={() => applyFilter('partial', s.platform)}
                className="text-xs px-2 py-1 rounded bg-yellow-100 hover:bg-yellow-200 transition-colors"
              >
                {s.partial} Partial
              </button>
              <button
                onClick={() => applyFilter('approved', s.platform)}
                className="text-xs px-2 py-1 rounded bg-blue-100 hover:bg-blue-200 transition-colors"
              >
                {s.approved} Approved
              </button>
              <button
                onClick={() => applyFilter('published', s.platform)}
                className="text-xs px-2 py-1 rounded bg-green-100 hover:bg-green-200 transition-colors"
              >
                {s.published} Published
              </button>
              <button
                onClick={() => applyFilter('published-legacy', s.platform)}
                className="text-xs px-2 py-1 rounded bg-orange-100 hover:bg-orange-200 transition-colors"
              >
                {s.legacyPublished} Legacy
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex gap-3 mb-4">
        <Select value={activeStatus} onValueChange={v => applyFilter(v as StatusFilter, activePlatform)}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="needs-review">Needs Review</SelectItem>
            <SelectItem value="partial">Partial</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="published">Published</SelectItem>
            <SelectItem value="published-legacy">Published (Legacy Method)</SelectItem>
          </SelectContent>
        </Select>

        <Select value={activePlatform} onValueChange={v => applyFilter(activeStatus, v)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Platforms" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Platforms</SelectItem>
            <SelectItem value="google">Google</SelectItem>
            <SelectItem value="bing">Bing</SelectItem>
            <SelectItem value="shopify">Shopify</SelectItem>
          </SelectContent>
        </Select>

        {(activeStatus !== 'all' || activePlatform !== 'all') && (
          <button
            onClick={() => applyFilter('all', 'all')}
            className="text-sm text-muted-foreground hover:text-foreground px-2"
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto text-sm text-muted-foreground self-center">
          {filteredSkus.length} of {skus.length} SKUs
        </span>
      </div>

      {/* Column header row */}
      <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted-foreground uppercase tracking-wide border-b border-border">
        <div className="w-10 flex-shrink-0" />
        <div className="w-28 flex-shrink-0">SKU</div>
        <div className="flex-1 min-w-0">Product</div>
        <div className="flex gap-1 flex-shrink-0">
          <span className="w-[66px] text-center">Google</span>
          <span className="w-[66px] text-center">Bing</span>
          <span className="w-[66px] text-center">Shopify</span>
          <span className="w-[88px] text-center">Image</span>
        </div>
        <div className="w-8 text-right flex-shrink-0">Score</div>
        <div className="w-4 flex-shrink-0" />
      </div>

      {/* SKU rows */}
      <div className="divide-y divide-border/40">
        {filteredSkus.length === 0 ? (
          <div className="px-4 py-8 text-center text-muted-foreground text-sm">
            No SKUs found
          </div>
        ) : (
          filteredSkus.map((sku) => (
            <div key={sku.master_sku}>
              {/* Clickable row — toggles inline expand */}
              <div
                onClick={() => setExpandedSku(prev => prev === sku.master_sku ? null : sku.master_sku)}
                className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 rounded-md cursor-pointer transition-colors"
              >
                <SkuThumbnail url={sku.thumbnail_url} sku={sku.master_sku} />
                <span className="font-medium text-sm w-28 flex-shrink-0">{sku.master_sku}</span>
                <span className="text-sm text-muted-foreground truncate flex-1 min-w-0">
                  {sku.product_title ?? '—'}
                </span>
                <div className="flex gap-1 flex-shrink-0">
                  {sku.platform_progress.map((progress) => (
                    <PlatformBadge
                      key={progress.platform}
                      progress={progress}
                      isLegacyMethod={Boolean(sku.legacy_published_by_platform[progress.platform])}
                    />
                  ))}
                  <ImageRowBadge images={sku.lifestyle_images} />
                </div>
                <span className={`text-sm font-medium w-8 text-right flex-shrink-0 ${getScoreColor(sku.avg_quality_score)}`}>
                  {sku.avg_quality_score ?? '—'}
                </span>
                <ChevronRight className={`h-4 w-4 text-muted-foreground flex-shrink-0 transition-transform ${expandedSku === sku.master_sku ? 'rotate-90' : ''}`} />
              </div>

              {/* Inline preview panel — shown when row is expanded */}
              {expandedSku === sku.master_sku && (
                <div ref={expandedRef}>
                  <SkuPreviewPanel
                    sku={sku}
                    optimisticApprovals={optimisticApprovals[sku.master_sku] ?? new Set()}
                    onApprove={(platform) => handleQuickApprove(sku.master_sku, platform)}
                    onClose={() => setExpandedSku(null)}
                  />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
