'use client'

import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { CheckCircle2 } from 'lucide-react'
import { LeakageTermRow } from './LeakageTermRow'
import type { ApproveOptions } from './LeakageTermRow'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { ClassifiedTerm } from '../lib/reason-codes'
import type { RecommendationStatus } from '../hooks/useRecommendations'

interface LeakageTermListProps {
  terms: ClassifiedTerm[]
  statuses: Record<string, RecommendationStatus>
  onApprove: (term: TermScore, options?: ApproveOptions) => void
  onReject: (term: TermScore, reason?: string) => void
  onUndo: (searchTerm: string, customLabel0: string) => void
  onViewDetails: (term: TermScore) => void
}

const PAGE_SIZE = 20

function makeKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}::${customLabel0}`
}

export function LeakageTermList({
  terms,
  statuses,
  onApprove,
  onReject,
  onUndo,
  onViewDetails,
}: LeakageTermListProps) {
  const [showCount, setShowCount] = useState(PAGE_SIZE)

  // Filter out accepted terms (they belong in Action Queue)
  const visibleTerms = useMemo(() => {
    return terms.filter(t => {
      const key = makeKey(t.searchTerm, t.customLabel0)
      const s = statuses[key]
      return !s || s.status !== 'accepted'
    })
  }, [terms, statuses])

  const displayedTerms = visibleTerms.slice(0, showCount)
  const hasMore = showCount < visibleTerms.length

  if (visibleTerms.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-700 py-8 justify-center">
        <CheckCircle2 className="h-4 w-4" />
        No actionable terms &mdash; all recommendations have been reviewed
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {displayedTerms.map((term, i) => {
        const key = makeKey(term.searchTerm, term.customLabel0)
        return (
          <LeakageTermRow
            key={key}
            term={term}
            rank={i + 1}
            status={statuses[key] ?? null}
            onApprove={onApprove}
            onReject={onReject}
            onUndo={onUndo}
            onViewDetails={onViewDetails}
          />
        )
      })}

      {hasMore && (
        <div className="flex justify-center pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowCount(prev => prev + PAGE_SIZE)}
          >
            Show {Math.min(PAGE_SIZE, visibleTerms.length - showCount)} more
          </Button>
        </div>
      )}
    </div>
  )
}
