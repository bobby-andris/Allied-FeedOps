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
import { ArrowLeft, ChevronDown, ChevronRight, AlertCircle, Info } from 'lucide-react'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { ConfidenceBadge } from './ConfidenceBadge'
import { FallbackIndicator } from './FallbackIndicator'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'
import { formatDollars } from '@/lib/formatting'

interface TermScorecardProps {
  term: TermScore
  allScoresForTerm?: TermScore[]
  onBack: () => void
  onSwitchLabel?: (term: TermScore) => void
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

const FACTOR_TOOLTIPS: Record<string, string> = {
  'ROAS Position': 'How well this term\'s ROAS fits the target tier\'s distribution. Computed as a robust z-score using median and MAD. 0 = perfect median fit, negative = below. Weight: 50% of tier fit score.',
  'Consistency': 'Performance stability. 0.9 = all funnel assignments agree, 0.3 = conflicting. Weight: 30% of confidence.',
  'Data Volume': 'Reliability from click volume. min(clicks/100, 1.0). Maxes at 100+ clicks. Weight: 30% of confidence.',
  'Intent Alignment': 'Query specificity vs tier profile. Generic queries fit HIGH, specific queries fit LOW. Weight: 20% of confidence.',
  'Feed Alignment': 'Query-to-feed attribute matching via TF-IDF (60%) + specificity (40%). From Cloud Run /score-intent. Weight: 55% of unified intent.',
  'Behavioral Intent': 'Google Ads purchase signals: relative CTR (30%), CPC ceiling (25%), micro-conversions (20%), cost velocity (10%). Weight: 45% of unified intent.',
}

const TIER_TOOLTIPS: Record<string, string> = {
  'HIGH': 'Top-of-funnel tier. Catches generic, broad searches (e.g., "grab bar"). Highest Target ROAS setting restricts bidding. Expected: lowest ROAS, lowest CVR.',
  'MEDIUM': 'Mid-funnel tier. Catches category + 1 attribute queries (e.g., "polished nickel grab bar"). Moderate Target ROAS. Expected: moderate ROAS and CVR.',
  'LOW': 'Bottom-of-funnel tier. Catches specific, high-intent searches with 2+ attributes (e.g., "polished nickel grab bar 18in"). Lowest Target ROAS allows aggressive bidding. Expected: highest ROAS and CVR.',
}

const TIER_DESCRIPTIONS: Record<string, string> = {
  'HIGH': 'Top-of-funnel -- highest Target ROAS setting restricts bidding on broad queries.',
  'MEDIUM': 'Mid-funnel -- moderate Target ROAS for category-level queries.',
  'LOW': 'Bottom-of-funnel -- lowest Target ROAS allows aggressive bidding on high-intent queries.',
}

function buildNarrativeCurrentState(term: TermScore): string {
  const clicks = term.totalClicks ?? 0
  const impressions = term.totalImpressions ?? 0
  const cost = formatDollars((term.totalCostMicros ?? 0) / 1_000_000)
  const conversions = term.totalConversions ?? 0
  const tierDesc = TIER_DESCRIPTIONS[term.currentTier] ?? ''
  return `"${term.searchTerm}" is in the ${term.currentTier} tier for the ${term.customLabel0} product group. ${tierDesc} Over the last 90 days: ${impressions.toLocaleString()} impressions, ${clicks.toLocaleString()} clicks, ${cost} spent, ${conversions} purchase${conversions !== 1 ? 's' : ''}.`
}

function buildNarrativeProposedChange(term: TermScore): string {
  const destination = term.targetTier ?? term.recommendedTier
  const trigger = term.trigger ?? 'observe'
  let line = ''

  if (trigger === 'wasted_spend' && term.recommendedAction === 'block') {
    line = 'Add as account-level negative keyword -- completely stop bidding on this term.'
  } else if (trigger === 'wasted_spend') {
    line = 'Move to HIGH tier to restrict bidding via highest tROAS cap.'
  } else if (trigger === 'demote_underperform') {
    line = `Move to ${destination} to restrict bidding -- this query is too generic for aggressive spend.`
  } else if (trigger === 'promote_conversion') {
    line = `Move to ${destination} for more aggressive bidding -- this term has proven conversions.`
  } else if (trigger === 'promote_intent') {
    line = `Move to ${destination} for more aggressive bidding -- intent signals are strong despite zero conversions so far.`
  } else if (trigger === 'under_invested') {
    line = `Increase budget allocation -- performing well but not getting enough impressions in ${term.currentTier}.`
  } else {
    line = `No change recommended -- performing as expected in ${term.currentTier}.`
  }

  if (term.impact) {
    line += ` Expected savings/gain: ${formatDollars(term.impact.low)}--${formatDollars(term.impact.high)}/mo.`
  }
  return line
}

function buildNarrativeWhy(term: TermScore): string {
  const trigger = term.trigger ?? 'observe'
  const cost = formatDollars((term.totalCostMicros ?? 0) / 1_000_000)

  if (trigger === 'wasted_spend') {
    let why = `Zero purchases despite ${cost} spend exceeds the wasted-spend threshold.`
    if (term.behavioralSignals) {
      why += ` Relative CTR of ${term.behavioralSignals.rCTR.toFixed(1)}x tier median ${term.behavioralSignals.rCTR >= 1.0 ? 'suggests engagement but no conversion' : 'indicates low engagement'}.`
    }
    return why
  }
  if (trigger === 'demote_underperform') {
    let why = ''
    if (term.intentScore) {
      const expectedTier = term.intentScore.unifiedScore >= 0.60 ? 'LOW' : term.intentScore.unifiedScore >= 0.30 ? 'MEDIUM' : 'HIGH'
      why = `Query intent score of ${term.intentScore.unifiedScore.toFixed(2)} maps to ${expectedTier} tier, but currently in ${term.currentTier}.`
    }
    const wordCount = term.searchTerm.trim().split(/\s+/).length
    why += ` Query has ${wordCount} word${wordCount !== 1 ? 's' : ''}, indicating ${wordCount <= 2 ? 'broad' : 'moderate'} specificity.`
    return why.trim()
  }
  if (trigger === 'promote_conversion') {
    let why = `${term.totalConversions} conversion${term.totalConversions !== 1 ? 's' : ''} confirm${term.totalConversions === 1 ? 's' : ''} purchase intent.`
    if (term.intentScore) {
      const expectedTier = term.intentScore.unifiedScore >= 0.60 ? 'LOW' : term.intentScore.unifiedScore >= 0.30 ? 'MEDIUM' : 'HIGH'
      why += ` Intent score ${term.intentScore.unifiedScore.toFixed(2)} maps to ${expectedTier}. More aggressive bidding would capture more volume.`
    }
    return why
  }
  if (trigger === 'promote_intent') {
    let why = ''
    if (term.intentScore) {
      why = `Intent score ${term.intentScore.unifiedScore.toFixed(2)} exceeds the 0.65 threshold.`
    }
    if (term.behavioralSignals && term.behavioralSignals.rCTR >= 1.5) {
      why += ` Relative CTR of ${term.behavioralSignals.rCTR.toFixed(1)}x tier median confirms engagement.`
    } else {
      const wordCount = term.searchTerm.trim().split(/\s+/).length
      why += ` Query has ${wordCount} word${wordCount !== 1 ? 's' : ''} indicating high specificity.`
    }
    return why.trim()
  }
  if (trigger === 'under_invested') {
    return 'Performing well but not getting enough impressions. Market volume suggests more demand exists.'
  }
  return 'This term\'s intent profile matches its current tier placement.'
}

interface ScorecardFactor {
  name: string
  score: number
  expandedDetail: string
}

function buildFactors(term: TermScore): ScorecardFactor[] {
  // Prefer targetTier (from trigger system) over recommendedTier (statistical best-fit)
  const destination = term.targetTier ?? term.recommendedTier
  const fitScore = term.tierFitScores[destination] ?? 0
  // Normalize fit score to 0-1 range (z-scores typically range -3 to +3, clamp to 0-1)
  const normalizedFit = Math.max(0, Math.min(1, (fitScore + 2) / 4))

  const factors: ScorecardFactor[] = [
    {
      name: 'ROAS Position',
      score: normalizedFit,
      expandedDetail: `Tier fit z-score: ${fitScore.toFixed(3)} (normalized: ${normalizedFit.toFixed(2)}). Higher values indicate better alignment with the ${destination} tier distribution. Based on robust z-score using median and MAD.`,
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
      expandedDetail: `Score: ${term.confidence.factors.intentAlignment.toFixed(3)}. Measures how well this term's intent signals align with the ${destination} tier's typical intent profile.`,
    },
  ]

  // Add unified intent score if available (from Phase 34.2 intent scoring)
  if (term.intentScore) {
    factors.push({
      name: 'Feed Alignment',
      score: term.intentScore.feedAlignmentScore,
      expandedDetail: `Score: ${term.intentScore.feedAlignmentScore.toFixed(3)}. How well this query's attributes match your product feed data. Combines TF-IDF term importance (60%) and query specificity (40%).`,
    })
    factors.push({
      name: 'Behavioral Intent',
      score: term.intentScore.behavioralScore,
      expandedDetail: `Score: ${term.intentScore.behavioralScore.toFixed(3)}. Purchase intent signals from Google Ads behavior: relative CTR, CPC ceiling proximity, micro-conversions, and cost velocity.`,
    })
  }

  return factors
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
          {FACTOR_TOOLTIPS[factor.name] && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-3.5 w-3.5 text-muted-foreground shrink-0 cursor-help" />
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p>{FACTOR_TOOLTIPS[factor.name]}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
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

export function TermScorecard({ term, allScoresForTerm, onBack, onSwitchLabel }: TermScorecardProps) {
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
        {(term.trigger && term.trigger !== 'observe') && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5">
            <AlertCircle className="h-3 w-3" />
            {term.trigger === 'wasted_spend' ? 'Wasted Spend' :
             term.trigger === 'promote_intent' ? 'Intent-Proven' :
             term.trigger === 'promote_conversion' ? 'Conversion-Proven' :
             term.trigger === 'demote_underperform' ? 'Underperforming' :
             term.trigger === 'under_invested' ? 'Under-Invested' : 'Opportunity'}
          </span>
        )}
        {!term.trigger && term.isMisplaced && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5">
            <AlertCircle className="h-3 w-3" />
            Opportunity
          </span>
        )}
      </div>

      {/* Narrative Briefing */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Narrative Briefing</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <p className="text-sm leading-relaxed">
              <span className="font-semibold">Current State: </span>
              {buildNarrativeCurrentState(term)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-sm leading-relaxed">
              <span className="font-semibold">Proposed Change: </span>
              {buildNarrativeProposedChange(term)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-sm leading-relaxed">
              <span className="font-semibold">Why: </span>
              {buildNarrativeWhy(term)}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Raw Google Ads Data */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Raw Google Ads Data</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Impressions</p>
              <p className="text-sm font-mono font-medium">{(term.totalImpressions ?? 0).toLocaleString()}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Clicks</p>
              <p className="text-sm font-mono font-medium">{(term.totalClicks ?? 0).toLocaleString()}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">CTR</p>
              <p className="text-sm font-mono font-medium">
                {(term.totalImpressions ?? 0) > 0
                  ? `${(((term.totalClicks ?? 0) / (term.totalImpressions ?? 1)) * 100).toFixed(2)}%`
                  : '0.00%'}
              </p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Avg CPC</p>
              <p className="text-sm font-mono font-medium">
                ${((term.totalAverageCpcMicros ?? 0) / 1_000_000).toFixed(2)}
              </p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Total Cost</p>
              <p className="text-sm font-mono font-medium">{formatDollars(term.totalCostMicros / 1_000_000)}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">ROAS</p>
              <p className="text-sm font-mono font-medium">{term.actualRoas.toFixed(2)}x</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Conversions</p>
              <p className="text-sm font-mono font-medium">{term.totalConversions}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">All Conv.</p>
              <p className="text-sm font-mono font-medium">{(term.totalAllConversions ?? 0).toLocaleString()}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
              <p className="text-xs text-muted-foreground">Conv. Value</p>
              <p className="text-sm font-mono font-medium">{formatDollars(term.totalConversionsValue ?? 0)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Verdict section */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Verdict</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm leading-relaxed">{term.verdict}</p>

          {(() => {
            // Use targetTier from trigger system when available, fall back to recommendedTier
            const destination = term.targetTier ?? term.recommendedTier
            const hasMovement = (term.trigger && term.trigger !== 'observe') || term.isMisplaced
            const showArrow = hasMovement && destination !== term.currentTier
            if (!showArrow) return null
            return (
              <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <span className={`font-medium ${tierTextColor[term.currentTier]}`}>
                  {term.currentTier}
                </span>
                <span className="text-muted-foreground">&rarr;</span>
                <span className={`font-medium ${tierTextColor[destination]}`}>
                  {destination}
                </span>
                {term.impact && (
                  <span className="ml-auto text-xs">
                    Moving this term could add {formatDollars(term.impact.low)}&ndash;{formatDollars(term.impact.high)}/mo
                  </span>
                )}
              </div>
            )
          })()}
        </CardContent>
      </Card>

      {/* Decision Reasoning — detailed breakdown of WHY this action was recommended */}
      {term.trigger && term.trigger !== 'observe' && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Decision Reasoning</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Trigger explanation */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Trigger</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  term.trigger === 'wasted_spend' ? 'bg-red-100 text-red-800' :
                  term.trigger === 'demote_underperform' ? 'bg-amber-100 text-amber-800' :
                  term.trigger === 'promote_conversion' ? 'bg-green-100 text-green-800' :
                  term.trigger === 'promote_intent' ? 'bg-blue-100 text-blue-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {term.trigger === 'wasted_spend' ? 'A: Wasted Spend' :
                   term.trigger === 'demote_underperform' ? 'B: Low Intent — Demote' :
                   term.trigger === 'promote_conversion' ? 'C: High Intent — Promote (Conversion-Proven)' :
                   term.trigger === 'promote_intent' ? 'D: High Intent — Promote (Intent-Proven)' :
                   term.trigger === 'under_invested' ? 'E: Under-Invested' : term.trigger}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                {term.trigger === 'wasted_spend' && (
                  <>This term spent <span className="font-medium text-red-700">{formatDollars(term.totalCostMicros / 1_000_000)}</span> with <span className="font-medium text-red-700">zero purchases</span>. Exceeds the $15 wasted spend threshold. {term.currentTier === 'HIGH' ? 'Block this term entirely.' : `Demote to ${term.targetTier} to restrict bidding.`}</>
                )}
                {term.trigger === 'demote_underperform' && (
                  <>Query intent analysis indicates this is a <span className="font-medium">generic/broad query</span> that belongs in a more restricted tier. {term.intentScore ? <>Unified intent score of <span className="font-medium">{term.intentScore.unifiedScore.toFixed(2)}</span> maps to {term.intentScore.unifiedScore < 0.30 ? 'HIGH' : 'MEDIUM'} tier, but currently in {term.currentTier}.</> : <>Word count suggests lower specificity than current {term.currentTier} tier requires.</>}</>
                )}
                {term.trigger === 'promote_conversion' && (
                  <>Query intent analysis indicates this is a <span className="font-medium">specific, high-intent query</span> that deserves more aggressive bidding. Has <span className="font-medium text-green-700">{term.totalConversions} conversion{term.totalConversions !== 1 ? 's' : ''}</span> confirming purchase intent. {term.intentScore ? <>Unified intent score of <span className="font-medium">{term.intentScore.unifiedScore.toFixed(2)}</span> maps to {term.intentScore.unifiedScore >= 0.60 ? 'LOW' : 'MEDIUM'} tier.</> : null}</>
                )}
                {term.trigger === 'promote_intent' && (
                  <>Zero conversions yet, but intent signals strongly suggest this query will convert. {term.intentScore ? <>Unified intent score of <span className="font-medium">{term.intentScore.unifiedScore.toFixed(2)}</span> exceeds the 0.65 threshold.</> : null} {term.behavioralSignals && term.behavioralSignals.rCTR >= 1.5 ? <> Relative CTR of <span className="font-medium">{term.behavioralSignals.rCTR.toFixed(1)}x</span> tier median supports promotion.</> : <>Query has {term.searchTerm.trim().split(/\s+/).length}+ words indicating high specificity.</>}</>
                )}
                {term.trigger === 'under_invested' && (
                  <>This term is performing well but not getting enough impressions. Market volume suggests significantly more search demand exists than current ad spend captures.</>
                )}
              </p>
            </div>

            {/* Supporting evidence grid */}
            <div className="border-t pt-3">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Supporting Evidence</span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-2">
                <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                  <p className="text-xs text-muted-foreground">Spend</p>
                  <p className="text-sm font-mono font-medium">{formatDollars(term.totalCostMicros / 1_000_000)}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                  <p className="text-xs text-muted-foreground">Conversions</p>
                  <p className="text-sm font-mono font-medium">{term.totalConversions}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                  <p className="text-xs text-muted-foreground">ROAS</p>
                  <p className="text-sm font-mono font-medium">{term.actualRoas.toFixed(2)}x</p>
                </div>
                {term.intentScore && (
                  <>
                    <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                      <p className="text-xs text-muted-foreground">Feed Alignment</p>
                      <p className={`text-sm font-mono font-medium ${scoreColor(term.intentScore.feedAlignmentScore)}`}>
                        {term.intentScore.feedAlignmentScore.toFixed(2)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                      <p className="text-xs text-muted-foreground">Behavioral</p>
                      <p className={`text-sm font-mono font-medium ${scoreColor(term.intentScore.behavioralScore)}`}>
                        {term.intentScore.behavioralScore.toFixed(2)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                      <p className="text-xs text-muted-foreground">Unified Intent</p>
                      <p className={`text-sm font-mono font-medium ${scoreColor(term.intentScore.unifiedScore)}`}>
                        {term.intentScore.unifiedScore.toFixed(2)}
                      </p>
                    </div>
                  </>
                )}
                {term.behavioralSignals && (
                  <>
                    <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                      <p className="text-xs text-muted-foreground">Relative CTR</p>
                      <p className="text-sm font-mono font-medium">{term.behavioralSignals.rCTR.toFixed(2)}x</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                      <p className="text-xs text-muted-foreground">CPC Ceiling</p>
                      <p className="text-sm font-mono font-medium">{(term.behavioralSignals.cpcCeilingRatio * 100).toFixed(0)}%</p>
                    </div>
                  </>
                )}
                <div className="rounded-lg bg-muted/50 p-2.5 space-y-0.5">
                  <p className="text-xs text-muted-foreground">Word Count</p>
                  <p className="text-sm font-mono font-medium">{term.searchTerm.trim().split(/\s+/).length}</p>
                </div>
              </div>
            </div>

            {/* Intent tier mapping explanation */}
            {term.intentScore && (
              <div className="border-t pt-3">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Intent → Tier Mapping</span>
                <div className="mt-2 flex items-center gap-2 text-xs">
                  {[
                    { tier: 'HIGH' as FunnelTier, range: '< 0.30', label: 'Generic' },
                    { tier: 'MEDIUM' as FunnelTier, range: '0.30 – 0.60', label: 'Mid' },
                    { tier: 'LOW' as FunnelTier, range: '> 0.60', label: 'Specific' },
                  ].map(({ tier, range, label }) => {
                    const expectedTier = term.intentScore!.unifiedScore >= 0.60 ? 'LOW'
                      : term.intentScore!.unifiedScore >= 0.30 ? 'MEDIUM' : 'HIGH'
                    const isExpected = tier === expectedTier
                    const isCurrent = tier === term.currentTier
                    return (
                      <div
                        key={tier}
                        className={`flex-1 rounded-lg border p-2 text-center ${
                          isExpected ? 'border-primary bg-primary/5 font-medium' : 'border-muted'
                        }`}
                      >
                        <p className={`font-medium ${tierTextColor[tier]}`}>{tier}</p>
                        <p className="text-muted-foreground">{range}</p>
                        <p className="text-muted-foreground">{label}</p>
                        {isExpected && <p className="text-primary text-[10px] mt-0.5">Expected</p>}
                        {isCurrent && !isExpected && <p className="text-amber-600 text-[10px] mt-0.5">Current</p>}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Multi-Label Context */}
      {allScoresForTerm && allScoresForTerm.length > 1 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Multi-Label Context</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">
              This term appears in {allScoresForTerm.length} product groups:
            </p>
            <div className="space-y-2">
              {allScoresForTerm.map(score => {
                const isCurrentView = score.customLabel0 === term.customLabel0
                const destination = score.targetTier ?? score.recommendedTier
                const hasMovement = destination !== score.currentTier
                return (
                  <div
                    key={score.customLabel0}
                    className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm ${
                      isCurrentView ? 'border-primary bg-primary/5' : 'hover:bg-muted/50 cursor-pointer'
                    }`}
                    onClick={() => {
                      if (!isCurrentView && onSwitchLabel) onSwitchLabel(score)
                    }}
                  >
                    <span className="font-medium min-w-[120px]">{score.customLabel0}</span>
                    {hasMovement ? (
                      <span className="flex items-center gap-1.5 text-xs">
                        <span className={tierTextColor[score.currentTier]}>{score.currentTier}</span>
                        <span className="text-muted-foreground">&rarr;</span>
                        <span className={tierTextColor[destination]}>{destination}</span>
                      </span>
                    ) : (
                      <span className="text-xs text-green-700">Aligned in {score.currentTier}</span>
                    )}
                    {score.trigger && score.trigger !== 'observe' && (
                      <span className="text-xs text-muted-foreground">
                        ({score.trigger === 'wasted_spend' ? 'Wasted Spend' :
                          score.trigger === 'demote_underperform' ? 'Demote' :
                          score.trigger === 'promote_conversion' ? 'Conversion-Proven' :
                          score.trigger === 'promote_intent' ? 'Intent-Proven' :
                          score.trigger === 'under_invested' ? 'Under-Invested' : score.trigger})
                      </span>
                    )}
                    <span className="ml-auto text-xs">
                      {isCurrentView ? (
                        <span className="text-primary font-medium">Currently viewing</span>
                      ) : (
                        <span className="text-primary hover:underline">View this label</span>
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

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
            const isRecommended = t === (term.targetTier ?? term.recommendedTier)
            const isBest = fitScore === maxFit
            // Normalize for display: z-scores can be negative, shift to 0-100
            const barValue = Math.max(0, Math.min(100, ((fitScore + 2) / 4) * 100))

            return (
              <div key={t} className="flex items-center gap-3">
                <span className={`text-sm font-medium w-20 inline-flex items-center gap-1 ${tierTextColor[t]}`}>
                  {t}
                  {TIER_TOOLTIPS[t] && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3.5 w-3.5 text-muted-foreground shrink-0 cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p>{TIER_TOOLTIPS[t]}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
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

      {/* Behavioral signals (when available from Phase 34.2) */}
      {term.behavioralSignals && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Behavioral Signals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Relative CTR', value: term.behavioralSignals.rCTR, format: (v: number) => `${v.toFixed(2)}x`, explain: 'vs tier median' },
                { label: 'CPC Ceiling', value: term.behavioralSignals.cpcCeilingRatio, format: (v: number) => `${(v * 100).toFixed(0)}%`, explain: 'of tier cap' },
                { label: 'Micro-Conversions', value: term.behavioralSignals.microConversionDelta, format: (v: number) => v.toFixed(1), explain: 'non-purchase actions' },
                { label: 'Composite', value: term.behavioralSignals.composite, format: (v: number) => v.toFixed(2), explain: 'weighted score' },
              ].map(s => (
                <div key={s.label} className="rounded-lg border p-3 text-center space-y-1">
                  <p className="text-lg font-mono font-semibold">{s.format(s.value)}</p>
                  <p className="text-xs font-medium">{s.label}</p>
                  <p className="text-[10px] text-muted-foreground">{s.explain}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
