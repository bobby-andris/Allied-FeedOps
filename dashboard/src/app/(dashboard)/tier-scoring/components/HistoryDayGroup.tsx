'use client'

import { Button } from '@/components/ui/button'
import { Check, X, Undo2 } from 'lucide-react'
import { TierMovementArrow } from './TierMovementArrow'
import type { HistoryEntry, ReviewStatus } from '../hooks/useRecommendations'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface HistoryDayGroupProps {
  date: string // "Feb 25, 2026"
  entries: HistoryEntry[]
  onUndo: (searchTerm: string, customLabel0: string) => void
}

function getActionIcon(status: ReviewStatus) {
  switch (status) {
    case 'accepted':
      return <Check className="h-4 w-4 text-green-500" />
    case 'rejected':
      return <X className="h-4 w-4 text-red-500" />
    default:
      return <Undo2 className="h-4 w-4 text-gray-500" />
  }
}

function getActionLabel(entry: HistoryEntry): string {
  // Check for undo action in history array
  const historyArr = entry.metadata?.history
  if (Array.isArray(historyArr)) {
    const lastAction = historyArr[historyArr.length - 1]
    if (lastAction?.action === 'undone') return 'Undone'
  }

  switch (entry.review_status) {
    case 'accepted':
      return 'Approved'
    case 'rejected':
      return 'Rejected'
    case 'pending':
      return 'Undone'
    default:
      return entry.review_status
  }
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

export function HistoryDayGroup({ date, entries, onUndo }: HistoryDayGroupProps) {
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-medium text-muted-foreground px-1 pb-1">{date}</h3>
      <div className="space-y-1">
        {entries.map((entry, i) => {
          const timestamp = entry.accepted_at || entry.created_at
          const actionLabel = getActionLabel(entry)
          const rejectionReason = entry.metadata?.rejection_reason
          const currentTier = entry.metadata?.current_tier as FunnelTier | undefined
          const recommendedTier = entry.recommended_tier as FunnelTier | null
          const isAccepted = entry.review_status === 'accepted'

          return (
            <div
              key={`${entry.search_term}-${entry.custom_label_0}-${i}`}
              className="flex items-center gap-3 rounded-lg border px-4 py-2.5"
            >
              {/* Action icon */}
              <div className="shrink-0">{getActionIcon(entry.review_status)}</div>

              {/* Term name + subtitle */}
              <div className="flex-1 min-w-0">
                <span className="font-medium text-sm truncate block">{entry.search_term}</span>
                <span className="text-xs text-muted-foreground">
                  {actionLabel}
                  {rejectionReason && entry.review_status === 'rejected'
                    ? ` \u2014 ${rejectionReason}`
                    : ''}
                </span>
              </div>

              {/* Tier movement */}
              {currentTier && recommendedTier && (
                <div className="shrink-0 hidden sm:block">
                  <TierMovementArrow current={currentTier} recommended={recommendedTier} />
                </div>
              )}

              {/* Timestamp */}
              <span className="text-xs text-muted-foreground shrink-0">
                {formatTime(timestamp)}
              </span>

              {/* Undo button (only for accepted) */}
              {isAccepted && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 text-muted-foreground shrink-0"
                  onClick={() => onUndo(entry.search_term, entry.custom_label_0)}
                >
                  <Undo2 className="h-3.5 w-3.5" />
                  Undo
                </Button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Export helpers for testing
export { getActionIcon, getActionLabel, formatTime }
