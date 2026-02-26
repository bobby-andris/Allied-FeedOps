'use client'

import { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertCircle, ArrowRight, ShieldBan } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FallbackIndicator } from './FallbackIndicator'
import { classifyAllTerms } from '../lib/reason-codes'
import type { GroupDistributions, TermScore, ImpactRange } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'
import { formatDollars } from '@/lib/formatting'

interface GroupOverviewProps {
  distributions: Record<string, GroupDistributions>
  scores: TermScore[]
  onSelectGroup: (group: string) => void
  onBlockLabel?: (customLabel0: string) => void
}

const TIER_ORDER: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']

const tierColors: Record<FunnelTier, string> = {
  HIGH: 'bg-emerald-500',
  MEDIUM: 'bg-blue-500',
  LOW: 'bg-amber-500',
}

interface GroupSummary {
  group: GroupDistributions
  misplacedCount: number
  misplacedImpact: number
}

export function GroupOverview({ distributions, scores, onSelectGroup, onBlockLabel }: GroupOverviewProps) {
  const sortedGroups = useMemo(() => {
    const groups: GroupSummary[] = Object.values(distributions).map(group => {
      const groupScores = scores.filter(s => s.customLabel0 === group.customLabel0)
      const classified = classifyAllTerms(groupScores)
      const actionable = classified.filter(t => t.trigger && t.trigger !== 'observe')
      const misplacedImpact = actionable.reduce((sum, s) => sum + (s.impact?.mid ?? 0), 0)
      return { group, misplacedCount: actionable.length, misplacedImpact }
    })

    groups.sort((a, b) => {
      if (b.misplacedCount !== a.misplacedCount) return b.misplacedCount - a.misplacedCount
      return b.misplacedImpact - a.misplacedImpact
    })

    return groups
  }, [distributions, scores])

  const topGroup = sortedGroups[0]

  return (
    <div className="space-y-4">
      {topGroup && topGroup.misplacedCount > 0 && (
        <div
          className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm cursor-pointer hover:bg-amber-100 transition-colors"
          onClick={() => onSelectGroup(topGroup.group.customLabel0)}
        >
          <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-amber-800">
            <span className="font-semibold italic">{topGroup.group.customLabel0}</span>
            {' '}has {topGroup.misplacedCount} optimization {topGroup.misplacedCount !== 1 ? 'opportunities' : 'opportunity'}
            {topGroup.misplacedImpact > 0 && (
              <> with {formatDollars(topGroup.misplacedImpact)}/mo potential impact</>
            )}
            {' '}&mdash; click to investigate
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {sortedGroups.map(({ group, misplacedCount, misplacedImpact }) => {
          const isNoData = group.scoredTerms === 0

          if (isNoData) {
            return (
              <Card
                key={group.customLabel0}
                className="opacity-60 cursor-default"
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{group.customLabel0}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">No data yet</p>
                </CardContent>
              </Card>
            )
          }

          // Determine the dominant fallback level (most common across tiers)
          const fallbackLevels = TIER_ORDER.map(t => group.tiers[t]?.fallbackLevel).filter(Boolean)
          const dominantFallback = fallbackLevels.find(l => l !== 'per_group') ?? 'per_group'

          return (
            <Card
              key={group.customLabel0}
              className="cursor-pointer hover:border-primary/50 hover:shadow-sm transition-all"
              onClick={() => onSelectGroup(group.customLabel0)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base truncate">{group.customLabel0}</CardTitle>
                  <div className="flex items-center gap-2 shrink-0">
                    <FallbackIndicator level={dominantFallback} groupName={group.customLabel0} />
                    {misplacedCount > 0 && (
                      <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-medium">
                        {misplacedCount} {misplacedCount !== 1 ? 'opportunities' : 'opportunity'}
                      </span>
                    )}
                    {onBlockLabel && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          const confirmed = window.confirm(
                            `Block all terms under "${group.customLabel0}"? This will prevent all terms in this category from getting aggressive bidding.`
                          )
                          if (confirmed) {
                            onBlockLabel(group.customLabel0)
                          }
                        }}
                        title={`Block all terms in ${group.customLabel0}`}
                      >
                        <ShieldBan className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Compact tier grid */}
                <div className="grid grid-cols-3 gap-2">
                  {TIER_ORDER.map(tier => {
                    const tierDist = group.tiers[tier]
                    const groupScores = scores.filter(s => s.customLabel0 === group.customLabel0)
                    const tierTermCount = groupScores.filter(s => s.currentTier === tier).length
                    const isInsufficient = tierTermCount === 0
                    const termCount = tierTermCount
                    const roasP50 = tierDist?.metrics?.roas?.p50 ?? 0

                    return (
                      <div
                        key={tier}
                        className={`rounded-md border p-2 text-center ${
                          isInsufficient ? 'opacity-50' : ''
                        }`}
                      >
                        <div className="flex items-center justify-center gap-1 mb-1">
                          <div className={`h-2 w-2 rounded-full ${tierColors[tier]}`} />
                          <span className="text-xs font-medium text-muted-foreground">{tier}</span>
                        </div>
                        {isInsufficient ? (
                          <p className="text-xs text-muted-foreground">Limited data</p>
                        ) : (
                          <>
                            <p className="text-sm font-semibold">{roasP50.toFixed(1)}x</p>
                            <p className="text-xs text-muted-foreground">
                              ROAS &middot; {termCount} terms
                            </p>
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t">
                  <span>
                    {group.scoredTerms} terms scored
                    {misplacedCount > 0 && (
                      <> &middot; <span className="text-amber-600 font-medium">{misplacedCount} {misplacedCount !== 1 ? 'opportunities' : 'opportunity'}</span></>
                    )}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
