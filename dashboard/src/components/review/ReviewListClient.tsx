'use client'

import { useMemo, useCallback } from "react"
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

interface SkuRow {
  master_sku: string
  approval_status: string | null
  product_title: string | null
  thumbnail_url: string | null
  avg_quality_score: number | null
  platform_progress: PlatformProgress[]
  per_platform_approval: Partial<Record<Platform, PlatformContentState>>
}

interface ReviewListClientProps {
  skus: SkuRow[]
}

type BadgeState = PlatformProgress['state']

interface BadgeStyle {
  className: string
  label: string
}

function getPlatformBadgeStyle(state: BadgeState): BadgeStyle {
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

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

function PlatformBadge({ progress }: { progress: PlatformProgress }) {
  const abbrev = getPlatformAbbrev(progress.platform)
  const { className, label } = getPlatformBadgeStyle(progress.state)
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

export function ReviewListClient({ skus }: ReviewListClientProps) {
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const router = useRouter()

  const activeStatus = searchParams.get('status') ?? 'all'
  const activePlatform = searchParams.get('platform') ?? 'all'

  const applyFilter = useCallback((status: string, platform: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (status === 'all') params.delete('status')
    else params.set('status', status)
    if (platform === 'all') params.delete('platform')
    else params.set('platform', platform)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }, [searchParams, pathname, router])

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
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex gap-3 mb-4">
        <Select value={activeStatus} onValueChange={v => applyFilter(v, activePlatform)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="needs-review">Needs Review</SelectItem>
            <SelectItem value="partial">Partial</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="published">Published</SelectItem>
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
        <div className="flex gap-1 flex-shrink-0 w-[210px]">
          <span className="w-[66px] text-center">Google</span>
          <span className="w-[66px] text-center">Bing</span>
          <span className="w-[66px] text-center">Shopify</span>
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
            <Link
              key={sku.master_sku}
              href={`/review/${skuToUrlPath(sku.master_sku)}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 rounded-md cursor-pointer border-b border-border/40 transition-colors"
            >
              <SkuThumbnail url={sku.thumbnail_url} sku={sku.master_sku} />
              <span className="font-medium text-sm w-28 flex-shrink-0">{sku.master_sku}</span>
              <span className="text-sm text-muted-foreground truncate flex-1 min-w-0">
                {sku.product_title ?? '—'}
              </span>
              <div className="flex gap-1 flex-shrink-0">
                {sku.platform_progress.map((progress) => (
                  <PlatformBadge key={progress.platform} progress={progress} />
                ))}
              </div>
              <span className={`text-sm font-medium w-8 text-right flex-shrink-0 ${getScoreColor(sku.avg_quality_score)}`}>
                {sku.avg_quality_score ?? '—'}
              </span>
              <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
