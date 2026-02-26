'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Ban, ArrowDown, Check, X, Undo2 } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { ReasonBadge } from './ReasonBadge'
import { TierMovementArrow } from './TierMovementArrow'
import { ImpactBadge } from './ImpactBadge'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { ClassifiedTerm } from '../lib/reason-codes'
import type { ApproveOptions } from './LeakageTermRow'

interface ActionQueueRowProps {
  term: ClassifiedTerm
  rank: number
  onViewDetails: (term: TermScore) => void
  showUndo?: boolean
  onUndo?: (searchTerm: string, customLabel0: string) => void
  onApprove?: (term: TermScore, options?: ApproveOptions) => void
  onReject?: (term: TermScore) => void
  reviewStatus?: 'pending' | 'accepted' | 'rejected' | 'expired'
}

export function ActionQueueRow({ term, rank, onViewDetails, showUndo, onUndo, onApprove, onReject, reviewStatus = 'pending' }: ActionQueueRowProps) {
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
      className="flex items-center gap-4 rounded-lg border px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors"
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
      {/* Rank */}
      <span className="text-sm font-mono text-muted-foreground w-6 shrink-0">#{rank}</span>

      {/* Term name + verdict */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium truncate">{term.searchTerm}</span>
          <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
          <ReasonBadge reasonCode={term.reasonCode} />
          {term.intentScore && (
            <Badge
              variant="outline"
              className={
                term.intentScore.unifiedScore >= 0.65
                  ? 'border-green-300 text-green-700 bg-green-50'
                  : term.intentScore.unifiedScore >= 0.40
                  ? 'border-amber-300 text-amber-700 bg-amber-50'
                  : 'border-red-300 text-red-700 bg-red-50'
              }
            >
              Intent: {term.intentScore.unifiedScore.toFixed(2)}
            </Badge>
          )}
          {term.trigger === 'promote_intent' && (
            <Badge variant="outline" className="border-blue-300 text-blue-700 bg-blue-50">
              Intent-Proven
            </Badge>
          )}
          {term.trigger === 'promote_conversion' && (
            <Badge variant="outline" className="border-green-300 text-green-700 bg-green-50">
              Conversion-Proven
            </Badge>
          )}
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
                    <ArrowDown className="h-3.5 w-3.5" />
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
