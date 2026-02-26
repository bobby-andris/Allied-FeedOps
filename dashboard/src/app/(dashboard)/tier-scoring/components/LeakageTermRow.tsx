'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Ban, ArrowDown, Check, X, Undo2, ChevronDown, ChevronUp } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { ReasonBadge } from './ReasonBadge'
import { TierMovementArrow } from './TierMovementArrow'
import { ImpactBadge } from './ImpactBadge'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { ClassifiedTerm } from '../lib/reason-codes'
import type { RecommendationStatus } from '../hooks/useRecommendations'

export interface ApproveOptions {
  recommendedAction?: string
  recommendedTier?: string
}

interface LeakageTermRowProps {
  term: ClassifiedTerm
  rank: number
  status: RecommendationStatus | null
  onApprove: (term: TermScore, options?: ApproveOptions) => void
  onReject: (term: TermScore, reason?: string) => void
  onUndo: (searchTerm: string, customLabel0: string) => void
  onViewDetails: (term: TermScore) => void
}

export function LeakageTermRow({
  term,
  rank,
  status,
  onApprove,
  onReject,
  onUndo,
  onViewDetails,
}: LeakageTermRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const rejectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const reviewStatus = status?.status ?? 'pending'
  const isWastedSpend = term.reasonCode === 'wasted_spend'

  // Auto-dismiss reject input after 5 seconds
  useEffect(() => {
    if (showRejectInput) {
      rejectTimerRef.current = setTimeout(() => {
        setShowRejectInput(false)
      }, 5000)
      inputRef.current?.focus()
    }
    return () => {
      if (rejectTimerRef.current) clearTimeout(rejectTimerRef.current)
    }
  }, [showRejectInput])

  // Determine action badge text based on metadata
  const getApprovedBadgeText = (): string => {
    // TODO: when hook passes metadata back, use it to distinguish Block/Demote/Approved
    return 'Approved'
  }

  const handleRowClick = () => {
    setExpanded(prev => !prev)
  }

  const handleApprove = (e: React.MouseEvent) => {
    e.stopPropagation()
    onApprove(term)
  }

  const handleBlock = (e: React.MouseEvent) => {
    e.stopPropagation()
    onApprove(term, { recommendedAction: 'global_block' })
  }

  const handleDemote = (e: React.MouseEvent) => {
    e.stopPropagation()
    // Wasted spend "Demote" pushes UP the funnel to HIGH — where restrictive tROAS/CPC caps constrain spending.
    // NOT to LOW, which would unleash aggressive bidding on a non-converting term.
    onApprove(term, { recommendedAction: 'funnel', recommendedTier: 'high' })
  }

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation()
    onReject(term)
    setShowRejectInput(true)
  }

  const handleSaveNote = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (rejectReason.trim()) {
      onReject(term, rejectReason.trim())
    }
    setShowRejectInput(false)
    setRejectReason('')
  }

  const handleUndo = (e: React.MouseEvent) => {
    e.stopPropagation()
    onUndo(term.searchTerm, term.customLabel0)
    setShowRejectInput(false)
    setRejectReason('')
  }

  const handleViewDetails = (e: React.MouseEvent) => {
    e.stopPropagation()
    onViewDetails(term)
  }

  return (
    <div className="rounded-lg border transition-colors">
      {/* Main row */}
      <div
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-muted/50"
        onClick={handleRowClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleRowClick()
          }
        }}
      >
        {/* Rank */}
        <span className="text-sm font-mono text-muted-foreground w-6 shrink-0">#{rank}</span>

        {/* Term info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium truncate">{term.searchTerm}</span>
            <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
            <ReasonBadge reasonCode={term.reasonCode} />
          </div>
          <p className="text-sm text-muted-foreground mt-0.5 truncate">{term.actionReason || term.verdict}</p>
        </div>

        {/* Tier movement */}
        <div className="shrink-0 hidden sm:block">
          <TierMovementArrow current={term.currentTier} recommended={term.recommendedTier} />
        </div>

        {/* Impact */}
        <div className="shrink-0">
          <ImpactBadge impact={term.impact} />
        </div>

        {/* Action buttons / status badges */}
        <div className="shrink-0 flex items-center gap-2">
          {reviewStatus === 'pending' && (
            <>
              {isWastedSpend ? (
                <>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleBlock}
                    className="gap-1"
                  >
                    <Ban className="h-3.5 w-3.5" />
                    Block
                  </Button>
                  {term.currentTier !== 'HIGH' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleDemote}
                      className="gap-1 border-amber-300 text-amber-700 hover:bg-amber-50"
                      title="Push to HIGH tier where restrictive settings constrain spending"
                    >
                      <ArrowDown className="h-3.5 w-3.5" />
                      Constrain
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
              <Badge className="bg-green-100 text-green-800 border-green-200">
                {getApprovedBadgeText()}
              </Badge>
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

        {/* Expand indicator */}
        <div className="shrink-0 text-muted-foreground">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </div>

      {/* Reject reason input (inline below row) */}
      {showRejectInput && reviewStatus === 'rejected' && (
        <div
          className="px-4 pb-3 flex items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          <Input
            ref={inputRef}
            placeholder="Optional: why reject this?"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            onBlur={() => {
              // Auto-dismiss on blur
              setTimeout(() => setShowRejectInput(false), 200)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.stopPropagation()
                handleSaveNote(e as unknown as React.MouseEvent)
              }
            }}
            className="flex-1 h-8 text-sm"
          />
          <Button variant="outline" size="sm" onClick={handleSaveNote}>
            Save note
          </Button>
        </div>
      )}

      {/* Expandable detail section */}
      {expanded && (
        <div className="px-4 pb-3 pt-1 border-t bg-muted/30 text-sm space-y-2">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
            <span>
              Actual ROAS: {term.actualRoas?.toFixed(2) ?? 'N/A'}x
            </span>
            <span>Peer average: {term.peerContext}</span>
            <span>
              Fit score: {term.tierFitScores[term.currentTier]?.toFixed(2) ?? '?'} &rarr;{' '}
              {term.tierFitScores[term.recommendedTier]?.toFixed(2) ?? '?'}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground text-xs">
            <span>Data {term.confidence.factors.dataVolume.toFixed(2)}</span>
            <span>&bull; Consistency {term.confidence.factors.consistency.toFixed(2)}</span>
            <span>&bull; Significance {term.confidence.factors.significance.toFixed(2)}</span>
            <span>&bull; Intent {term.confidence.factors.intentAlignment.toFixed(2)}</span>
          </div>
          <Button variant="link" size="sm" className="p-0 h-auto text-xs" onClick={handleViewDetails}>
            View full scorecard
          </Button>
        </div>
      )}
    </div>
  )
}
