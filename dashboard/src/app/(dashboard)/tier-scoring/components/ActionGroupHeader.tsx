'use client'

import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatDollars } from '@/lib/formatting'
import type { ActionGroup, ActionGroupData, ClassifiedTerm } from '../lib/reason-codes'

const ACCENT_BORDER: Record<ActionGroup, string> = {
  stop_wasting: 'border-l-red-500',
  restrict_bidding: 'border-l-amber-500',
  bid_aggressive: 'border-l-green-500',
}

interface ActionGroupHeaderProps {
  group: ActionGroupData
  groupKey: ActionGroup
  isExpanded: boolean
  onToggle: () => void
  onBatchApprove: (terms: ClassifiedTerm[]) => void
}

export function ActionGroupHeader({ group, groupKey, isExpanded, onToggle, onBatchApprove }: ActionGroupHeaderProps) {
  const handleBatchApprove = (e: React.MouseEvent) => {
    e.stopPropagation()
    onBatchApprove(group.terms.filter(t => t.confidence.score > 0.80))
  }

  return (
    <div
      className={`flex items-center justify-between border-l-4 ${ACCENT_BORDER[groupKey]} rounded-lg bg-muted/30 px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onToggle()
        }
      }}
    >
      {/* Left side: label, term count, total impact */}
      <div className="flex items-center gap-3">
        <span className="font-semibold text-sm">{group.label}</span>
        <span className="text-xs text-muted-foreground">
          {group.terms.length} {group.terms.length === 1 ? 'term' : 'terms'}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatDollars(group.totalImpact.low)} &ndash; {formatDollars(group.totalImpact.high)}/mo
        </span>
      </div>

      {/* Right side: batch approve + chevron */}
      <div className="flex items-center gap-2">
        {group.highConfidenceCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleBatchApprove}
          >
            Approve All High-Confidence ({group.highConfidenceCount})
          </Button>
        )}
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </div>
    </div>
  )
}
