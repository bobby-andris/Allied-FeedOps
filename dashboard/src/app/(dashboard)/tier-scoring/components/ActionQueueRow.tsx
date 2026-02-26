'use client'

import { Button } from '@/components/ui/button'
import { Undo2 } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { TierMovementArrow } from './TierMovementArrow'
import { ImpactBadge } from './ImpactBadge'
import { generatePlainVerdict } from '../lib/plain-verdict'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'

interface ActionQueueRowProps {
  term: TermScore
  rank: number
  onViewDetails: (term: TermScore) => void
  showUndo?: boolean
  onUndo?: (searchTerm: string, customLabel0: string) => void
}

export function ActionQueueRow({ term, rank, onViewDetails, showUndo, onUndo }: ActionQueueRowProps) {
  const verdict = generatePlainVerdict(term)

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
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{term.searchTerm}</span>
          <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
        </div>
        <p className="text-sm text-muted-foreground mt-0.5 truncate">{verdict}</p>
      </div>

      {/* Tier movement arrow */}
      <div className="shrink-0 hidden sm:block">
        <TierMovementArrow current={term.currentTier} recommended={term.recommendedTier} />
      </div>

      {/* Impact */}
      <div className="shrink-0">
        <ImpactBadge impact={term.impact} />
      </div>

      {/* Undo button (for accepted recommendations) */}
      {showUndo && onUndo && (
        <Button
          variant="ghost"
          size="sm"
          className="gap-1 text-muted-foreground shrink-0"
          onClick={(e) => {
            e.stopPropagation()
            onUndo(term.searchTerm, term.customLabel0)
          }}
        >
          <Undo2 className="h-3.5 w-3.5" />
          Undo
        </Button>
      )}
    </div>
  )
}
