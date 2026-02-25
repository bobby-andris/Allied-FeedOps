'use client'

import { useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle2 } from 'lucide-react'
import { ActionQueueRow } from './ActionQueueRow'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'

interface ActionQueueTableProps {
  scores: TermScore[]
  onSelectTerm: (term: TermScore) => void
}

const PAGE_SIZE = 20

export function ActionQueueTable({ scores, onSelectTerm }: ActionQueueTableProps) {
  const [showCount, setShowCount] = useState(PAGE_SIZE)

  const actionQueue = useMemo(() => {
    return scores
      .filter(s => s.isMisplaced)
      .sort((a, b) => (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0))
  }, [scores])

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
        {visibleTerms.map((term, i) => (
          <ActionQueueRow
            key={term.searchTerm}
            term={term}
            rank={i + 1}
            onViewDetails={onSelectTerm}
          />
        ))}

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
