'use client'

import { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ArrowLeft, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react'
import { FallbackIndicator } from './FallbackIndicator'
import { ConfidenceBadge } from './ConfidenceBadge'
import { DistributionChart } from './DistributionChart'
import type { GroupDistributions, TermScore, FallbackLevel } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface GroupDetailProps {
  group: GroupDistributions
  scores: TermScore[]
  onBack: () => void
  onSelectTier: (tier: FunnelTier) => void
}

const TIER_ORDER: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']

const tierColors: Record<FunnelTier, { fill: string; bg: string; text: string }> = {
  HIGH: { fill: '#10b981', bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-800' },
  MEDIUM: { fill: '#3b82f6', bg: 'bg-blue-50 border-blue-200', text: 'text-blue-800' },
  LOW: { fill: '#f59e0b', bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800' },
}

function formatDollars(amount: number): string {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

function formatMetricCompact(value: number, metric: string): string {
  if (metric === 'cpc') return `$${value.toFixed(2)}`
  if (metric === 'cvr' || metric === 'ctr') return `${(value * 100).toFixed(1)}%`
  return `${value.toFixed(2)}x`
}

export function GroupDetail({ group, scores, onBack, onSelectTier }: GroupDetailProps) {
  const misplacedTerms = useMemo(
    () => scores.filter(s => s.isMisplaced).sort((a, b) => (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0)),
    [scores]
  )

  // Generate inline callout
  const callout = useMemo(() => {
    if (misplacedTerms.length === 0) {
      return { type: 'success' as const, text: `All terms in ${group.customLabel0} align with current tiers — no action needed` }
    }

    // Find tier with most misplaced terms
    const tierCounts: Record<string, number> = {}
    for (const t of misplacedTerms) {
      tierCounts[t.currentTier] = (tierCounts[t.currentTier] ?? 0) + 1
    }
    const topTier = Object.entries(tierCounts).sort(([, a], [, b]) => b - a)[0]
    const boundary = topTier[0] === 'HIGH'
      ? group.boundaries.highFloor.value
      : group.boundaries.lowCeiling.value

    return {
      type: 'warning' as const,
      text: `${topTier[0]} tier has ${topTier[1]} term${topTier[1] !== 1 ? 's' : ''} where data suggests a different tier could improve performance — look at terms with ROAS ${topTier[0] === 'HIGH' ? 'below' : 'above'} ${boundary.toFixed(1)}x`,
    }
  }, [misplacedTerms, group])

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5">
        <ArrowLeft className="h-4 w-4" />
        Back to all groups
      </Button>

      {/* Group header */}
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold">{group.customLabel0}</h2>
        <FallbackIndicator
          level={TIER_ORDER.reduce<FallbackLevel>((worst, t) => {
            const level = group.tiers[t]?.fallbackLevel ?? 'per_group'
            if (level === 'defaults') return 'defaults'
            if (level === 'global' && worst !== 'defaults') return 'global'
            return worst
          }, 'per_group')}
          groupName={group.customLabel0}
        />
        <span className="text-sm text-muted-foreground">
          {group.scoredTerms} of {group.totalTerms} terms scored
        </span>
      </div>

      {/* Inline callout */}
      <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${
        callout.type === 'success'
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-amber-50 border-amber-200 text-amber-800'
      }`}>
        {callout.type === 'success' ? (
          <CheckCircle2 className="h-4 w-4 shrink-0" />
        ) : (
          <AlertCircle className="h-4 w-4 shrink-0" />
        )}
        <p>{callout.text}</p>
      </div>

      {/* Tier distributions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {TIER_ORDER.map(tier => {
          const tierDist = group.tiers[tier]
          const isInsufficient = group.insufficientTiers.includes(tier)
          const termCount = tierDist?.sampleSize ?? 0
          const colors = tierColors[tier]

          return (
            <Card key={tier} className={`relative ${isInsufficient ? 'opacity-60' : ''}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className={`text-base ${colors.text}`}>
                    {tier} Tier
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">{termCount} terms</span>
                </div>
                {tierDist && (
                  <FallbackIndicator level={tierDist.fallbackLevel} groupName={group.customLabel0} tierName={tier} />
                )}
              </CardHeader>
              <CardContent className="space-y-3">
                {isInsufficient ? (
                  <div className="text-center py-4">
                    <p className="text-sm text-muted-foreground">Limited data ({termCount} terms)</p>
                    <p className="text-xs text-muted-foreground mt-1">Need at least 5 terms for reliable distributions</p>
                  </div>
                ) : tierDist ? (
                  <>
                    {/* ROAS distribution chart */}
                    <DistributionChart
                      distribution={tierDist.metrics.roas}
                      metricName="ROAS"
                      tierColor={colors.fill}
                    />

                    {/* Compact stat row */}
                    <div className="grid grid-cols-3 gap-2 text-center">
                      {(['cvr', 'cpc', 'ctr'] as const).map(metric => (
                        <div key={metric} className="rounded-md bg-muted p-1.5">
                          <p className="text-[10px] text-muted-foreground uppercase">{metric}</p>
                          <p className="text-xs font-medium">
                            {formatMetricCompact(tierDist.metrics[metric].p50, metric)}
                          </p>
                        </div>
                      ))}
                    </div>

                    {/* View terms link */}
                    <button
                      className="w-full flex items-center justify-center gap-1 text-xs text-primary hover:underline pt-1"
                      onClick={() => onSelectTier(tier)}
                    >
                      View {termCount} terms
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">No data</p>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Tier boundaries */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tier Boundaries (ROAS)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-6 text-sm">
            <div className="space-y-1">
              <p className="text-muted-foreground">HIGH tier floor</p>
              <p className="font-semibold">{group.boundaries.highFloor.value.toFixed(2)}x ROAS</p>
              {group.boundaries.highFloor.capped && (
                <p className="text-xs text-amber-600">
                  Data suggests {group.boundaries.highFloor.uncappedValue.toFixed(2)}x but capped at {group.boundaries.highFloor.value.toFixed(2)}x (15% max shift)
                </p>
              )}
              {group.boundaries.highFloor.previousValue !== null && (
                <p className="text-xs text-muted-foreground">
                  Changed from {group.boundaries.highFloor.previousValue.toFixed(2)}x
                </p>
              )}
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">LOW tier ceiling</p>
              <p className="font-semibold">{group.boundaries.lowCeiling.value.toFixed(2)}x ROAS</p>
              {group.boundaries.lowCeiling.capped && (
                <p className="text-xs text-amber-600">
                  Data suggests {group.boundaries.lowCeiling.uncappedValue.toFixed(2)}x but capped at {group.boundaries.lowCeiling.value.toFixed(2)}x (15% max shift)
                </p>
              )}
              {group.boundaries.lowCeiling.previousValue !== null && (
                <p className="text-xs text-muted-foreground">
                  Changed from {group.boundaries.lowCeiling.previousValue.toFixed(2)}x
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Misplaced terms table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Optimization Opportunities ({misplacedTerms.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {misplacedTerms.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-lg px-4 py-3">
              <CheckCircle2 className="h-4 w-4" />
              No optimization opportunities in this group — all terms align with current tiers
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Search Term</TableHead>
                  <TableHead>Current</TableHead>
                  <TableHead></TableHead>
                  <TableHead>Recommended</TableHead>
                  <TableHead>Impact (range)</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {misplacedTerms.map(term => (
                  <TableRow key={term.searchTerm}>
                    <TableCell className="font-medium max-w-[200px] truncate" title={term.searchTerm}>
                      {term.searchTerm}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs font-medium ${tierColors[term.currentTier].text}`}>
                        {term.currentTier}
                      </span>
                    </TableCell>
                    <TableCell className="px-1">
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs font-medium ${tierColors[term.recommendedTier].text}`}>
                        {term.recommendedTier}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      {term.impact ? (
                        <span>
                          {formatDollars(term.impact.low)}&ndash;{formatDollars(term.impact.high)}/mo
                        </span>
                      ) : (
                        <span className="text-muted-foreground">&mdash;</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
