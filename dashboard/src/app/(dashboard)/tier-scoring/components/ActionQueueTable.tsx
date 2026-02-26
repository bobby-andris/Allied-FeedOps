'use client'

import { useMemo, useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle2 } from 'lucide-react'
import { ActionQueueRow } from './ActionQueueRow'
import { ActionGroupHeader } from './ActionGroupHeader'
import { groupActionableTerms } from '../lib/reason-codes'
import type { ActionGroup, ClassifiedTerm } from '../lib/reason-codes'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
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

const DEFAULT_VISIBLE = 10

const ACCENT_CLASSES: Record<ActionGroup, string> = {
  stop_wasting: 'border-l-2 border-l-red-500',
  restrict_bidding: 'border-l-2 border-l-amber-500',
  bid_aggressive: 'border-l-2 border-l-green-500',
}

function makeKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}::${customLabel0}`
}

export function ActionQueueTable({ terms, onSelectTerm, recommendationStatuses, onUndo, onApprove, onReject }: ActionQueueTableProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<ActionGroup>>(() => new Set(['stop_wasting', 'restrict_bidding', 'bid_aggressive']))
  const [showAllMap, setShowAllMap] = useState<Record<string, boolean>>({})

  // Sort accepted-first within each group, then group by action type
  const groups = useMemo(() => {
    // Partition accepted first within input terms to preserve accepted-first ordering
    if (!recommendationStatuses) return groupActionableTerms(terms)

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
    return groupActionableTerms([...accepted, ...others])
  }, [terms, recommendationStatuses])

  const toggleGroup = useCallback((key: ActionGroup) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

  const handleBatchApprove = useCallback((highConfTerms: ClassifiedTerm[]) => {
    for (const t of highConfTerms) {
      onApprove?.(t)
    }
  }, [onApprove])

  const totalTerms = groups.reduce((sum, g) => sum + g.terms.length, 0)

  if (totalTerms === 0) {
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
            Top Opportunities ({totalTerms} total)
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            Grouped by action type, sorted by impact
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.map(group => {
          const isExpanded = expandedGroups.has(group.key)
          const showAll = showAllMap[group.key] ?? false
          const visibleTerms = showAll ? group.terms : group.terms.slice(0, DEFAULT_VISIBLE)
          const hasMore = !showAll && group.terms.length > DEFAULT_VISIBLE

          return (
            <div key={group.key} className="space-y-2">
              <ActionGroupHeader
                group={group}
                groupKey={group.key}
                isExpanded={isExpanded}
                onToggle={() => toggleGroup(group.key)}
                onBatchApprove={handleBatchApprove}
              />

              {isExpanded && (
                <div className="space-y-2 pl-2">
                  {visibleTerms.map(term => {
                    const key = makeKey(term.searchTerm, term.customLabel0)
                    const status = recommendationStatuses?.[key]
                    return (
                      <ActionQueueRow
                        key={key}
                        term={term}
                        accentClass={ACCENT_CLASSES[group.key]}
                        onViewDetails={onSelectTerm}
                        onUndo={onUndo}
                        onApprove={onApprove}
                        onReject={onReject}
                        reviewStatus={status?.status ?? 'pending'}
                      />
                    )
                  })}

                  {hasMore && (
                    <div className="flex justify-center pt-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowAllMap(prev => ({ ...prev, [group.key]: true }))}
                      >
                        Show all {group.terms.length}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
