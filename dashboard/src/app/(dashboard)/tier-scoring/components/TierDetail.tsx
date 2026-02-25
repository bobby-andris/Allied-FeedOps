'use client'

import { useMemo, useState } from 'react'
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
import { ArrowLeft, ArrowUpDown, CheckCircle2, AlertCircle } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { FallbackIndicator } from './FallbackIndicator'
import { MisplacedTermRow } from './MisplacedTermRow'
import type { TermScore, TierDistribution } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface TierDetailProps {
  tier: FunnelTier
  distribution: TierDistribution
  scores: TermScore[]
  groupName: string
  onBack: () => void
  onSelectTerm: (term: TermScore) => void
}

type SortKey = 'term' | 'roas' | 'cvr' | 'cpc' | 'confidence' | 'status'
type SortDir = 'asc' | 'desc'

function formatDollars(amount: number): string {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

const tierColors: Record<FunnelTier, string> = {
  HIGH: 'text-emerald-800',
  MEDIUM: 'text-blue-800',
  LOW: 'text-amber-800',
}

export function TierDetail({
  tier,
  distribution,
  scores,
  groupName,
  onBack,
  onSelectTerm,
}: TierDetailProps) {
  const [sortKey, setSortKey] = useState<SortKey>('status')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const misplacedTerms = useMemo(
    () => scores.filter(s => s.isMisplaced).sort((a, b) => (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0)),
    [scores]
  )

  // Inline callout
  const callout = useMemo(() => {
    if (misplacedTerms.length === 0) {
      return {
        type: 'success' as const,
        text: `All ${scores.length} terms are a good fit for ${tier} tier`,
      }
    }
    const topTerm = misplacedTerms[0]
    const impactStr = topTerm.impact
      ? `$${Math.round(topTerm.impact.mid)}/mo`
      : ''
    return {
      type: 'warning' as const,
      text: `This tier has ${misplacedTerms.length} term${misplacedTerms.length !== 1 ? 's' : ''} that may perform better in ${topTerm.recommendedTier} — the top opportunity is "${topTerm.searchTerm}" with ${impactStr} potential impact`,
    }
  }, [misplacedTerms, scores.length, tier])

  // Sort logic
  const sortedScores = useMemo(() => {
    const sorted = [...scores]
    sorted.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'term':
          cmp = a.searchTerm.localeCompare(b.searchTerm)
          break
        case 'roas':
          cmp = (a.tierFitScores[a.recommendedTier] ?? 0) - (b.tierFitScores[b.recommendedTier] ?? 0)
          break
        case 'cvr':
          cmp = (a.confidence.factors.consistency ?? 0) - (b.confidence.factors.consistency ?? 0)
          break
        case 'cpc':
          cmp = (a.confidence.factors.dataVolume ?? 0) - (b.confidence.factors.dataVolume ?? 0)
          break
        case 'confidence':
          cmp = a.confidence.score - b.confidence.score
          break
        case 'status':
          // Misplaced first, then by impact
          if (a.isMisplaced !== b.isMisplaced) {
            cmp = a.isMisplaced ? 1 : -1
          } else {
            cmp = (a.impact?.mid ?? 0) - (b.impact?.mid ?? 0)
          }
          break
      }
      return sortDir === 'desc' ? -cmp : cmp
    })
    return sorted
  }, [scores, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const { metrics } = distribution

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5">
        <ArrowLeft className="h-4 w-4" />
        Back to {groupName}
      </Button>

      {/* Tier header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className={`text-xl font-bold ${tierColors[tier]}`}>
          {tier} Tier — {groupName}
        </h2>
        <span className="text-sm text-muted-foreground">
          {scores.length} terms
        </span>
        <FallbackIndicator
          level={distribution.fallbackLevel}
          groupName={groupName}
          tierName={tier}
        />
      </div>

      {/* Inline callout */}
      <div className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${
        callout.type === 'success'
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-amber-50 border-amber-200 text-amber-800'
      }`}>
        {callout.type === 'success' ? (
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
        ) : (
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
        )}
        <p>{callout.text}</p>
      </div>

      {/* Distribution summary */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <span>
              <span className="text-muted-foreground">Typical ROAS: </span>
              <span className="font-medium">{metrics.roas.p50.toFixed(2)}x</span>
            </span>
            <span>
              <span className="text-muted-foreground">Typical CVR: </span>
              <span className="font-medium">{(metrics.cvr.p50 * 100).toFixed(1)}%</span>
            </span>
            <span>
              <span className="text-muted-foreground">Typical CPC: </span>
              <span className="font-medium">${metrics.cpc.p50.toFixed(2)}</span>
            </span>
            <span>
              <span className="text-muted-foreground">Typical CTR: </span>
              <span className="font-medium">{(metrics.ctr.p50 * 100).toFixed(1)}%</span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Term list table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            All Terms ({scores.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <button className="flex items-center gap-1" onClick={() => toggleSort('term')}>
                    Search Term
                    <ArrowUpDown className="h-3 w-3" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center gap-1" onClick={() => toggleSort('roas')}>
                    Fit Score
                    <ArrowUpDown className="h-3 w-3" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center gap-1" onClick={() => toggleSort('confidence')}>
                    Confidence
                    <ArrowUpDown className="h-3 w-3" />
                  </button>
                </TableHead>
                <TableHead>
                  <button className="flex items-center gap-1" onClick={() => toggleSort('status')}>
                    Status
                    <ArrowUpDown className="h-3 w-3" />
                  </button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedScores.map(term => (
                <TableRow
                  key={term.searchTerm}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onSelectTerm(term)}
                >
                  <TableCell className="font-medium max-w-[240px] truncate" title={term.searchTerm}>
                    {term.searchTerm}
                  </TableCell>
                  <TableCell className="text-sm">
                    {term.tierFitScores[tier]?.toFixed(2) ?? '—'}
                  </TableCell>
                  <TableCell>
                    <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
                  </TableCell>
                  <TableCell>
                    {term.isMisplaced ? (
                      <span className="flex items-center gap-1.5 text-xs">
                        <span className={tierColors[term.currentTier]}>{term.currentTier}</span>
                        <span className="text-muted-foreground">&rarr;</span>
                        <span className={tierColors[term.recommendedTier]}>{term.recommendedTier}</span>
                        {term.impact && (
                          <span className="text-muted-foreground ml-1">
                            {formatDollars(term.impact.low)}&ndash;{formatDollars(term.impact.high)}/mo
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-xs text-green-700 flex items-center gap-1">
                        <CheckCircle2 className="h-3 w-3" />
                        Well-placed
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Dedicated Misplaced Terms Section */}
      {misplacedTerms.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              Misplaced Terms in {tier} Tier ({misplacedTerms.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {misplacedTerms.map(term => (
              <MisplacedTermRow
                key={term.searchTerm}
                term={term}
                onClick={() => onSelectTerm(term)}
              />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
