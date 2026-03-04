/* eslint-disable */
'use client'

import { useState, useEffect } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { ProductGroupDetail, TierGroup } from '@/lib/market-intelligence/types'
import { BCG_QUADRANT_LABELS, BCG_COLORS } from '@/lib/market-intelligence/constants'
import { formatDollars } from '@/lib/formatting'

interface ProductGroupSlideOutProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupName: string | null
  fetchGroupDetail: (group: string) => Promise<ProductGroupDetail>
}

const TIER_COLORS: Record<string, string> = {
  HIGH: '#22c55e',
  MEDIUM: '#f59e0b',
  LOW: '#ef4444',
}

export function ProductGroupSlideOut({
  open,
  onOpenChange,
  groupName,
  fetchGroupDetail,
}: ProductGroupSlideOutProps) {
  const [detail, setDetail] = useState<ProductGroupDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !groupName) {
      setDetail(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchGroupDetail(groupName)
      .then(data => {
        if (!cancelled) setDetail(data)
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load details')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [open, groupName, fetchGroupDetail])

  const quadrantInfo = detail ? BCG_QUADRANT_LABELS[detail.quadrant] : null
  const quadrantColor = detail ? BCG_COLORS[detail.quadrant] : undefined

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[500px] sm:max-w-[500px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{groupName || 'Product Group'}</SheetTitle>
          <SheetDescription className="sr-only">Product group details</SheetDescription>
          <div className="text-muted-foreground text-sm">
            {loading ? (
              <Skeleton className="h-5 w-24" />
            ) : quadrantInfo ? (
              <Badge
                variant="outline"
                style={{ borderColor: quadrantColor, color: quadrantColor }}
              >
                {quadrantInfo.label} — {quadrantInfo.description}
              </Badge>
            ) : null}
          </div>
        </SheetHeader>

        <div className="px-4 pb-4 space-y-6">
          {loading ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 rounded-lg" />
                ))}
              </div>
              <Skeleton className="h-64 rounded-lg" />
            </div>
          ) : error ? (
            <div className="text-sm text-destructive">{error}</div>
          ) : detail ? (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="ROAS" value={`${detail.roas.toFixed(2)}x`} />
                <StatCard label="Revenue" value={formatDollars(detail.revenue)} />
                <StatCard label="Spend" value={formatDollars(detail.spend)} />
                <TrendCard trend={detail.trend} />
              </div>

              {/* Tier-Grouped Terms */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium">
                  Top Terms by Funnel Tier ({detail.topTerms.length})
                </h4>
                {(detail.tierGroups && detail.tierGroups.length > 0
                  ? detail.tierGroups
                  : fallbackTierGroups(detail.topTerms)
                ).map((group) => (
                  <TierSection key={group.tier} group={group} />
                ))}
              </div>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

const TIER_LABELS: Record<string, string> = {
  HIGH: 'High (Broad/Generic)',
  MEDIUM: 'Medium (Category)',
  LOW: 'Low (High-Intent)',
  UNKNOWN: 'Unscored',
}

function fallbackTierGroups(topTerms: ProductGroupDetail['topTerms']): TierGroup[] {
  const map = new Map<string, TierGroup>()
  for (const term of topTerms) {
    const tier = term.currentTier || 'UNKNOWN'
    if (!map.has(tier)) {
      map.set(tier, { tier, termCount: 0, totalImpressions: 0, totalRevenue: 0, terms: [] })
    }
    const g = map.get(tier)!
    g.termCount++
    g.totalImpressions += term.impressions
    g.totalRevenue += term.revenue
    g.terms.push(term)
  }
  const order = ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
  return order.filter(t => map.has(t)).map(t => map.get(t)!)
}

function TierSection({ group }: { group: TierGroup }) {
  const [expanded, setExpanded] = useState(false)
  const color = TIER_COLORS[group.tier] || '#6b7280'
  const cappedTerms = group.terms.slice(0, 10)
  const visibleTerms = expanded ? cappedTerms : cappedTerms.slice(0, 3)
  const hiddenCount = cappedTerms.length - 3

  // Compute average ROAS for the tier
  const termsWithSpend = group.terms.filter(t => t.roas > 0)
  const avgRoas = termsWithSpend.length > 0
    ? termsWithSpend.reduce((sum, t) => sum + t.roas, 0) / termsWithSpend.length
    : 0

  return (
    <div className="border rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderLeft: `3px solid ${color}` }}
      >
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="text-[10px] px-1.5 py-0"
            style={{ borderColor: color, color }}
          >
            {group.tier}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {TIER_LABELS[group.tier] ?? group.tier}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="font-semibold" style={{ color }}>
            {avgRoas.toFixed(2)}x ROAS
          </span>
          <span>{group.termCount} terms</span>
          <span>{group.totalImpressions.toLocaleString()} impr.</span>
          <span>{formatDollars(group.totalRevenue)} rev</span>
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Term</TableHead>
            <TableHead className="text-xs text-right">Impr.</TableHead>
            <TableHead className="text-xs text-right">Revenue</TableHead>
            <TableHead className="text-xs text-right">ROAS</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleTerms.map((term, i) => (
            <TableRow key={i}>
              <TableCell className="text-xs max-w-[180px] truncate">
                {term.searchTerm}
              </TableCell>
              <TableCell className="text-xs text-right">
                {term.impressions.toLocaleString()}
              </TableCell>
              <TableCell className="text-xs text-right">
                {formatDollars(term.revenue)}
              </TableCell>
              <TableCell className="text-xs text-right">
                {term.roas.toFixed(2)}x
              </TableCell>
            </TableRow>
          ))}
          {hiddenCount > 0 && (
            <TableRow>
              <TableCell colSpan={4} className="py-1.5">
                <button
                  type="button"
                  onClick={() => setExpanded(!expanded)}
                  className="text-xs text-blue-600 hover:text-blue-800 hover:underline w-full text-center"
                >
                  {expanded ? 'Show less' : `Show ${hiddenCount} more`}
                </button>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  )
}

function TrendCard({ trend }: { trend: number }) {
  const isUp = trend > 0
  const isDown = trend < 0
  const color = isUp ? 'text-green-600' : isDown ? 'text-red-600' : 'text-muted-foreground'
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus

  return (
    <div className="bg-muted/50 rounded-lg p-3">
      <div className="flex items-center gap-1.5">
        <Icon className={`h-5 w-5 ${color}`} />
        <p className={`text-2xl font-bold ${color}`}>
          {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
        </p>
      </div>
      <p className="text-xs text-muted-foreground mt-0.5">Trend</p>
    </div>
  )
}
