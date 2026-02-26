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
import type { ProductGroupDetail } from '@/lib/market-intelligence/types'
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
          <SheetDescription>
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
          </SheetDescription>
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

              {/* Top Terms Table */}
              <div>
                <h4 className="text-sm font-medium mb-2">
                  Top Terms ({detail.topTerms.length})
                </h4>
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Term</TableHead>
                        <TableHead className="text-xs">Tier</TableHead>
                        <TableHead className="text-xs text-right">Impr.</TableHead>
                        <TableHead className="text-xs text-right">Revenue</TableHead>
                        <TableHead className="text-xs text-right">ROAS</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {detail.topTerms.slice(0, 20).map((term, i) => (
                        <TableRow key={i}>
                          <TableCell className="text-xs max-w-[160px] truncate">
                            {term.searchTerm}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1.5 py-0"
                              style={{
                                borderColor: TIER_COLORS[term.currentTier] || '#6b7280',
                                color: TIER_COLORS[term.currentTier] || '#6b7280',
                              }}
                            >
                              {term.currentTier}
                            </Badge>
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
                    </TableBody>
                  </Table>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
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
