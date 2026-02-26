'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Ban, ArrowUp, Check, X, Undo2 } from 'lucide-react'
import { TierMovementArrow } from './TierMovementArrow'
import { ImpactBadge } from './ImpactBadge'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { ClassifiedTerm } from '../lib/reason-codes'
import type { ApproveOptions } from './LeakageTermRow'

interface ActionQueueRowProps {
  term: ClassifiedTerm
  onViewDetails: (term: TermScore) => void
  accentClass?: string
  labelCount?: number
  onUndo?: (searchTerm: string, customLabel0: string) => void
  onApprove?: (term: TermScore, options?: ApproveOptions) => void
  onReject?: (term: TermScore) => void
  reviewStatus?: 'pending' | 'accepted' | 'rejected' | 'expired'
}

export function ActionQueueRow({ term, onViewDetails, accentClass, labelCount, onUndo, onApprove, onReject, reviewStatus = 'pending' }: ActionQueueRowProps) {
  // Use trigger from determineAction() as source of truth, fall back to reasonCode
  const isWastedSpend = term.trigger === 'wasted_spend' || (!term.trigger && term.reasonCode === 'wasted_spend')

  const handleBlock = (e: React.MouseEvent) => {
    e.stopPropagation()
    onApprove?.(term, { recommendedAction: 'global_block' })
  }

  const handleDemote = (e: React.MouseEvent) => {
    e.stopPropagation()
    const target = term.targetTier ?? 'HIGH'
    onApprove?.(term, { recommendedAction: 'funnel', recommendedTier: target.toLowerCase() })
  }

  const handleApprove = (e: React.MouseEvent) => {
    e.stopPropagation()
    onApprove?.(term)
  }

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation()
    onReject?.(term)
  }

  const handleUndo = (e: React.MouseEvent) => {
    e.stopPropagation()
    onUndo?.(term.searchTerm, term.customLabel0)
  }

  return (
    <div
      className={`flex items-center gap-4 rounded-lg border px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors ${accentClass ?? ''}`}
      onClick={() => onViewDetails(term)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onViewDetails(term)
        }
      }}
    >
      {/* Term name + label + action reason */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{term.searchTerm}</span>
          {labelCount && labelCount > 1 && (
            <span className="text-xs text-muted-foreground shrink-0">({labelCount} labels)</span>
          )}
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">{term.customLabel0}</Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-0.5 truncate">{term.actionReason || term.verdict}</p>
      </div>

      {/* Tier movement arrow */}
      <div className="shrink-0 hidden sm:block">
        <TierMovementArrow current={term.currentTier} recommended={term.recommendedTier} targetTier={term.targetTier} />
      </div>

      {/* Impact */}
      <div className="shrink-0">
        <ImpactBadge impact={term.impact} />
      </div>

      {/* Action buttons */}
      <div className="shrink-0 flex items-center gap-2">
        {(reviewStatus === 'pending' || reviewStatus === 'expired') && (
          <>
            {isWastedSpend ? (
              <>
                <Button variant="destructive" size="sm" onClick={handleBlock} className="gap-1">
                  <Ban className="h-3.5 w-3.5" />
                  Block
                </Button>
                {term.currentTier !== 'HIGH' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDemote}
                    className="gap-1 border-amber-300 text-amber-700 hover:bg-amber-50"
                    title={`Demote to ${term.targetTier ?? 'HIGH'} tier to restrict spending`}
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                    Demote to {term.targetTier ?? 'HIGH'}
                  </Button>
                )}
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleApprove}
                  className="gap-1 border-green-300 text-green-700 hover:bg-green-50"
                >
                  <Check className="h-3.5 w-3.5" />
                  Approve
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleReject}
                  className="gap-1 border-red-300 text-red-700 hover:bg-red-50"
                >
                  <X className="h-3.5 w-3.5" />
                  Reject
                </Button>
              </>
            )}
          </>
        )}
        {reviewStatus === 'accepted' && (
          <>
            <Badge className="bg-green-100 text-green-800 border-green-200">Approved</Badge>
            <Button variant="ghost" size="sm" onClick={handleUndo} className="gap-1 text-muted-foreground">
              <Undo2 className="h-3.5 w-3.5" />
              Undo
            </Button>
          </>
        )}
        {reviewStatus === 'rejected' && (
          <>
            <Badge className="bg-red-100 text-red-800 border-red-200">Rejected</Badge>
            <Button variant="ghost" size="sm" onClick={handleUndo} className="gap-1 text-muted-foreground">
              <Undo2 className="h-3.5 w-3.5" />
              Undo
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
