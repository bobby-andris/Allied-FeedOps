/**
 * OpportunityTermRow — displays a term flagged as an optimization opportunity.
 * (File originally named MisplacedTermRow; keeping name for import stability.)
 */
'use client'

import { ArrowUp, ArrowDown } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface MisplacedTermRowProps {
  term: TermScore
  onClick?: () => void
}

function getArrowProps(current: FunnelTier, recommended: FunnelTier) {
  const tierRank: Record<FunnelTier, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }
  const goingUp = tierRank[recommended] > tierRank[current]

  if (goingUp) {
    // Moving to higher tier
    if (recommended === 'HIGH') return { Icon: ArrowUp, color: 'text-emerald-600' }
    return { Icon: ArrowUp, color: 'text-blue-600' }
  }
  // Moving to lower tier
  if (recommended === 'LOW') return { Icon: ArrowDown, color: 'text-red-600' }
  return { Icon: ArrowDown, color: 'text-orange-600' }
}

function formatDollars(amount: number): string {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

const tierTextColor: Record<FunnelTier, string> = {
  HIGH: 'text-emerald-800',
  MEDIUM: 'text-blue-800',
  LOW: 'text-amber-800',
}

export function MisplacedTermRow({ term, onClick }: MisplacedTermRowProps) {
  const { Icon, color } = getArrowProps(term.currentTier, term.recommendedTier)
  const verdictSnippet = term.verdict.length > 60
    ? term.verdict.slice(0, 57) + '...'
    : term.verdict

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm ${
        onClick ? 'cursor-pointer hover:bg-muted/50 transition-colors' : ''
      }`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      {/* Search term */}
      <span className="font-medium truncate min-w-0 max-w-[180px]" title={term.searchTerm}>
        {term.searchTerm}
      </span>

      {/* Arrow indicator: current -> recommended */}
      <span className="flex items-center gap-1.5 shrink-0">
        <span className={`text-xs font-medium ${tierTextColor[term.currentTier]}`}>
          {term.currentTier}
        </span>
        <Icon className={`h-3.5 w-3.5 ${color}`} />
        <span className={`text-xs font-medium ${tierTextColor[term.recommendedTier]}`}>
          {term.recommendedTier}
        </span>
      </span>

      {/* Impact range */}
      <span className="text-xs text-muted-foreground shrink-0">
        {term.impact ? (
          <>{formatDollars(term.impact.low)}&ndash;{formatDollars(term.impact.high)}/mo</>
        ) : (
          <>&mdash;</>
        )}
      </span>

      {/* Confidence */}
      <span className="shrink-0">
        <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
      </span>

      {/* Verdict snippet */}
      <span className="text-xs text-muted-foreground truncate min-w-0 hidden lg:block">
        {verdictSnippet}
      </span>
    </div>
  )
}
