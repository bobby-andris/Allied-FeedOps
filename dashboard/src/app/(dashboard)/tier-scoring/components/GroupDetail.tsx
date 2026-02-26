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
import { classifyAllTerms } from '../lib/reason-codes'
import type { GroupDistributions, TermScore, FallbackLevel } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'
import { formatDollars } from '@/lib/formatting'

interface GroupDetailProps {
  group: GroupDistributions
  scores: TermScore[]
  onBack: () => void
  onSelectTier: (tier: FunnelTier) => void
  onSelectTerm: (term: TermScore) => void
}

const TIER_ORDER: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']

const tierColors: Record<FunnelTier, { fill: string; bg: string; text: string }> = {
  HIGH: { fill: '#10b981', bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-800' },
  MEDIUM: { fill: '#3b82f6', bg: 'bg-blue-50 border-blue-200', text: 'text-blue-800' },
  LOW: { fill: '#f59e0b', bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800' },
}

function formatMetricCompact(value: number, metric: string): string {
  if (metric === 'cpc') return `$${value.toFixed(2)}`
  if (metric === 'cvr' || metric === 'ctr') return `${(value * 100).toFixed(1)}%`
  return `${value.toFixed(2)}x`
}

function getTriggerBadge(trigger: string | undefined) {
  switch (trigger) {
    case 'wasted_spend':
      return <span className="inline-flex items-center rounded-full bg-red-100 text-red-800 px-2 py-0.5 text-[11px] font-medium">Block</span>
    case 'demote_underperform':
      return <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-[11px] font-medium">Demote</span>
    case 'promote_conversion':
      return <span className="inline-flex items-center rounded-full bg-green-100 text-green-800 px-2 py-0.5 text-[11px] font-medium">Promote</span>
    case 'promote_intent':
      return <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-[11px] font-medium">Promote</span>
    case 'under_invested':
      return <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-[11px] font-medium">Budget</span>
    default:
      return <span className="text-muted-foreground text-[11px]">&mdash;</span>
  }
}

export function GroupDetail({ group, scores, onBack, onSelectTier, onSelectTerm }: GroupDetailProps) {
  const actionableTerms = useMemo(() => {
    const classified = classifyAllTerms(scores)
    return classified.filter(t => t.trigger && t.trigger !== 'observe')
  }, [scores])

  // Generate inline callout
  const callout = useMemo(() => {
    if (actionableTerms.length === 0) {
      return { type: 'success' as const, text: `All terms in ${group.customLabel0} align with current tiers — no action needed` }
    }

    // Find trigger type with most terms
    const triggerCounts: Record<string, number> = {}
    for (const t of actionableTerms) {
      const key = t.trigger ?? 'unknown'
      triggerCounts[key] = (triggerCounts[key] ?? 0) + 1
    }
    const topTrigger = Object.entries(triggerCounts).sort(([, a], [, b]) => b - a)[0]

    return {
      type: 'warning' as const,
      text: `${actionableTerms.length} term${actionableTerms.length !== 1 ? 's' : ''} need attention — top issue: ${topTrigger[1]} ${topTrigger[0].replace(/_/g, ' ')} term${topTrigger[1] !== 1 ? 's' : ''}`,
    }
  }, [actionableTerms, group])

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
          {group.scoredTerms} terms scored
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
          const tierScores = scores.filter(s => s.currentTier === tier)
          const termCount = tierScores.length
          const isInsufficient = termCount === 0
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

      {/* Actionable terms table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Optimization Opportunities ({actionableTerms.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {actionableTerms.length === 0 ? (
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
                  <TableHead>Action</TableHead>
                  <TableHead></TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Impact (range)</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {actionableTerms.map(term => {
                  const targetTier = term.targetTier ?? term.recommendedTier
                  return (
                    <TableRow
                      key={`${term.searchTerm}::${term.customLabel0}`}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => onSelectTerm(term)}
                    >
                      <TableCell className="font-medium max-w-[200px] truncate" title={term.searchTerm}>
                        {term.searchTerm}
                      </TableCell>
                      <TableCell>
                        <span className={`text-xs font-medium ${tierColors[term.currentTier].text}`}>
                          {term.currentTier}
                        </span>
                      </TableCell>
                      <TableCell>
                        {getTriggerBadge(term.trigger)}
                      </TableCell>
                      <TableCell className="px-1">
                        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                      </TableCell>
                      <TableCell>
                        <span className={`text-xs font-medium ${tierColors[targetTier].text}`}>
                          {targetTier}
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
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
