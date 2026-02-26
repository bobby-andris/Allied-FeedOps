'use client'

import { useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle2 } from 'lucide-react'
import { ActionQueueRow } from './ActionQueueRow'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { ClassifiedTerm } from '../lib/reason-codes'
import type { RecommendationStatus } from '../hooks/useRecommendations'
import type { ApproveOptions } from './LeakageTermRow'

interface ActionQueueTableProps {
  terms: ClassifiedTerm[]
  onSelectTerm: (term: TermScore) => void
  recommendationStatuses?: Record<string, RecommendationStatus>
  onUndo?: (searchTerm: string, customLabel0: string) => void
  onApprove?: (term: TermScore, options?: ApproveOptions) => void
  onReject?: (term: TermScore) => void
}

const PAGE_SIZE = 20

function makeKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}::${customLabel0}`
}

export function ActionQueueTable({ terms, onSelectTerm, recommendationStatuses, onUndo, onApprove, onReject }: ActionQueueTableProps) {
  const [showCount, setShowCount] = useState(PAGE_SIZE)

  const actionQueue = useMemo(() => {
    if (!recommendationStatuses) return terms

    // Partition: accepted items first, then other misplaced items
    const accepted: ClassifiedTerm[] = []
    const others: ClassifiedTerm[] = []
    for (const term of terms) {
      const key = makeKey(term.searchTerm, term.customLabel0)
      const s = recommendationStatuses[key]
      if (s?.status === 'accepted') {
        accepted.push(term)
      } else {
        others.push(term)
      }
    }
    return [...accepted, ...others]
  }, [terms, recommendationStatuses])

  const visibleTerms = actionQueue.slice(0, showCount)
  const hasMore = showCount < actionQueue.length

  if (actionQueue.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-sm text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            All terms are performing well in their current tiers — no action needed
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            Top Opportunities ({actionQueue.length} total)
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            Sorted by potential impact
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {visibleTerms.map((term, i) => {
          const key = makeKey(term.searchTerm, term.customLabel0)
          const status = recommendationStatuses?.[key]
          return (
            <ActionQueueRow
              key={key}
              term={term}
              rank={i + 1}
              onViewDetails={onSelectTerm}
              onUndo={onUndo}
              onApprove={onApprove}
              onReject={onReject}
              reviewStatus={status?.status ?? 'pending'}
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
              Show {Math.min(PAGE_SIZE, actionQueue.length - showCount)} more
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
