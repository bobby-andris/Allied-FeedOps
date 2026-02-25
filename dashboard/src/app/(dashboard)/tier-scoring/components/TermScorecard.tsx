'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ArrowLeft, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react'
import { ConfidenceBadge } from './ConfidenceBadge'
import { FallbackIndicator } from './FallbackIndicator'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface TermScorecardProps {
  term: TermScore
  onBack: () => void
}

function formatDollars(amount: number): string {
  if (Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

function scoreColor(score: number): string {
  if (score > 0.7) return 'text-green-700'
  if (score >= 0.4) return 'text-amber-700'
  return 'text-red-700'
}

function progressColor(score: number): string {
  if (score > 0.7) return '[&>[data-slot=progress-indicator]]:bg-green-500'
  if (score >= 0.4) return '[&>[data-slot=progress-indicator]]:bg-amber-500'
  return '[&>[data-slot=progress-indicator]]:bg-red-500'
}

const tierTextColor: Record<FunnelTier, string> = {
  HIGH: 'text-emerald-800',
  MEDIUM: 'text-blue-800',
  LOW: 'text-amber-800',
}

const tierBgColor: Record<FunnelTier, string> = {
  HIGH: 'bg-emerald-100',
  MEDIUM: 'bg-blue-100',
  LOW: 'bg-amber-100',
}

interface ScorecardFactor {
  name: string
  score: number
  expandedDetail: string
}

function buildFactors(term: TermScore): ScorecardFactor[] {
  const recommended = term.recommendedTier
  const fitScore = term.tierFitScores[recommended] ?? 0
  // Normalize fit score to 0-1 range (z-scores typically range -3 to +3, clamp to 0-1)
  const normalizedFit = Math.max(0, Math.min(1, (fitScore + 2) / 4))

  return [
    {
      name: 'ROAS Position',
      score: normalizedFit,
      expandedDetail: `Tier fit z-score: ${fitScore.toFixed(3)} (normalized: ${normalizedFit.toFixed(2)}). Higher values indicate better alignment with the ${recommended} tier distribution. Based on robust z-score using median and MAD.`,
    },
    {
      name: 'Consistency',
      score: term.confidence.factors.consistency,
      expandedDetail: `Score: ${term.confidence.factors.consistency.toFixed(3)}. Based on metric stability across the term's performance data. Higher values indicate less variance — the term behaves predictably.`,
    },
    {
      name: 'Data Volume',
      score: term.confidence.factors.dataVolume,
      expandedDetail: `Score: ${term.confidence.factors.dataVolume.toFixed(3)}. Based on click and conversion volume. At 100+ clicks this factor maxes out. More data produces more reliable scoring.`,
    },
    {
      name: 'Intent Alignment',
      score: term.confidence.factors.intentAlignment,
      expandedDetail: `Score: ${term.confidence.factors.intentAlignment.toFixed(3)}. Measures how well this term's intent signals align with the ${recommended} tier's typical intent profile.`,
    },
  ]
}

function ExpandableFactor({ factor }: { factor: ScorecardFactor }) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="w-full">
        <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          )}
          <span className="text-sm font-medium min-w-[130px] text-left">{factor.name}</span>
          <Progress
            value={factor.score * 100}
            className={`h-2 flex-1 ${progressColor(factor.score)}`}
          />
          <span className={`text-sm font-mono w-12 text-right ${scoreColor(factor.score)}`}>
            {factor.score.toFixed(2)}
          </span>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-8 mr-3 mb-2 px-3 py-2 bg-muted/30 rounded text-xs text-muted-foreground">
          {factor.expandedDetail}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function TermScorecard({ term, onBack }: TermScorecardProps) {
  const factors = buildFactors(term)
  const tiers: FunnelTier[] = ['HIGH', 'MEDIUM', 'LOW']
  const maxFit = Math.max(...tiers.map(t => term.tierFitScores[t] ?? 0))

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5">
        <ArrowLeft className="h-4 w-4" />
        Back to {term.currentTier} tier
      </Button>

      {/* Term header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-xl font-bold">{term.searchTerm}</h2>
        <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
        {term.isMisplaced && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5">
            <AlertCircle className="h-3 w-3" />
            Opportunity
          </span>
        )}
      </div>

      {/* Verdict section */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Verdict</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm leading-relaxed">{term.verdict}</p>

          {term.isMisplaced && (
            <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <span className={`font-medium ${tierTextColor[term.currentTier]}`}>
                {term.currentTier}
              </span>
              <span className="text-muted-foreground">&rarr;</span>
              <span className={`font-medium ${tierTextColor[term.recommendedTier]}`}>
                {term.recommendedTier}
              </span>
              {term.impact && (
                <span className="ml-auto text-xs">
                  Moving this term could add {formatDollars(term.impact.low)}&ndash;{formatDollars(term.impact.high)}/mo
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Peer context */}
      {term.peerContext && (
        <p className="text-sm text-muted-foreground px-1">
          {term.peerContext}
        </p>
      )}

      {/* Visual scorecard */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Scoring Factors</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {factors.map(factor => (
            <ExpandableFactor key={factor.name} factor={factor} />
          ))}
        </CardContent>
      </Card>

      {/* Tier fit comparison */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tier Fit Comparison</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {tiers.map(t => {
            const fitScore = term.tierFitScores[t] ?? 0
            const isRecommended = t === term.recommendedTier
            const isBest = fitScore === maxFit
            // Normalize for display: z-scores can be negative, shift to 0-100
            const barValue = Math.max(0, Math.min(100, ((fitScore + 2) / 4) * 100))

            return (
              <div key={t} className="flex items-center gap-3">
                <span className={`text-sm font-medium w-20 ${tierTextColor[t]}`}>
                  {t}
                </span>
                <div className="flex-1 relative">
                  <div className={`h-6 rounded-full overflow-hidden ${
                    isRecommended ? 'bg-primary/10' : 'bg-muted'
                  }`}>
                    <div
                      className={`h-full rounded-full transition-all ${
                        isRecommended ? tierBgColor[t] : 'bg-muted-foreground/20'
                      }`}
                      style={{ width: `${barValue}%` }}
                    />
                  </div>
                </div>
                <span className={`text-sm font-mono w-14 text-right ${
                  isBest ? 'font-bold' : 'text-muted-foreground'
                }`}>
                  {fitScore.toFixed(2)}
                </span>
                {isRecommended && (
                  <span className="text-[10px] font-medium text-primary uppercase">Best</span>
                )}
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* Confidence breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Confidence Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-medium">Overall:</span>
            <ConfidenceBadge level={term.confidence.level} score={term.confidence.score} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { label: 'Data Volume', weight: '30%', value: term.confidence.factors.dataVolume, explain: 'Reliability based on click/conversion volume' },
              { label: 'Consistency', weight: '30%', value: term.confidence.factors.consistency, explain: 'Metric stability over time' },
              { label: 'Significance', weight: '20%', value: term.confidence.factors.significance, explain: 'Statistical separability between tiers' },
              { label: 'Intent Alignment', weight: '20%', value: term.confidence.factors.intentAlignment, explain: 'Match with tier intent profile' },
            ].map(f => (
              <div key={f.label} className="rounded-lg border p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{f.label} ({f.weight})</span>
                  <span className={`text-sm font-mono ${scoreColor(f.value)}`}>
                    {f.value.toFixed(2)}
                  </span>
                </div>
                <Progress
                  value={f.value * 100}
                  className={`h-1.5 ${progressColor(f.value)}`}
                />
                <p className="text-xs text-muted-foreground">{f.explain}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Fallback transparency */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Data Source</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <FallbackIndicator level={term.fallbackLevel} groupName={term.customLabel0} />
            {term.fallbackLevel === 'per_group' ? (
              <span className="text-sm text-muted-foreground">
                Scored using {term.customLabel0}-specific distributions — most reliable level
              </span>
            ) : term.fallbackLevel === 'global' ? (
              <span className="text-sm text-muted-foreground">
                Scored using category-wide distributions — less group-specific but still data-driven
              </span>
            ) : (
              <span className="text-sm text-muted-foreground">
                Scored using default baselines — limited real data available, treat scores with caution
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
