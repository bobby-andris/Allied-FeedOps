'use client'

import { useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { AlertCircle, CheckCircle, ChevronDown, ChevronRight, Lightbulb, MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'
import { analyzeContent, type Platform, type QualityAnalysis } from '@/lib/quality-scoring'

interface QualityAnalyzerProps {
  title: string
  description: string
  platform: Platform
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 bg-green-100 dark:bg-green-900/30'
  if (score >= 70) return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30'
  return 'text-red-600 bg-red-100 dark:bg-red-900/30'
}

function getProgressColor(score: number): string {
  // Score is 0-10, convert to percentage thresholds
  if (score >= 8) return 'bg-green-500'
  if (score >= 6) return 'bg-yellow-500'
  return 'bg-red-500'
}

function ScoreRow({ label, score, max = 10 }: { label: string; score: number; max?: number }) {
  const percentage = (score / max) * 100

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground w-20 shrink-0">{label}</span>
      <div className="flex-1 relative">
        <Progress value={percentage} className="h-2" />
        <div
          className={cn(
            'absolute inset-0 h-2 rounded-full transition-all',
            getProgressColor(score)
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs font-medium w-6 text-right">{score}</span>
    </div>
  )
}

function TrustBadge({ label, present }: { label: string; present: boolean }) {
  return (
    <Badge
      variant={present ? 'default' : 'outline'}
      className={cn(
        'text-xs gap-1',
        present ? 'bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400' : ''
      )}
    >
      {present && <CheckCircle className="h-3 w-3" />}
      {label}
    </Badge>
  )
}

function TitleZonesSection({ analysis }: { analysis: QualityAnalysis }) {
  const [isOpen, setIsOpen] = useState(false)
  const zones = analysis.titleZoneAnalysis

  if (!zones) return null

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium w-full hover:text-foreground text-muted-foreground">
        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <MapPin className="h-4 w-4" />
        Title Zones
        <Badge variant="outline" className="ml-auto text-xs">
          {zones.zoneScore}/10
        </Badge>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2">
        <div className="text-xs space-y-1.5 pl-6">
          <div className="flex gap-2">
            <span className="text-muted-foreground w-16 shrink-0">Mobile:</span>
            <span className="font-mono text-[11px] bg-muted px-1 rounded break-all">
              {zones.mobileZone || '(empty)'}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-muted-foreground w-16 shrink-0">Desktop:</span>
            <span className="font-mono text-[11px] bg-muted px-1 rounded break-all">
              {zones.desktopZone || '(empty)'}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-muted-foreground w-16 shrink-0">Extended:</span>
            <span className="font-mono text-[11px] bg-muted px-1 rounded break-all">
              {zones.extendedZone || '(none)'}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 pl-6 pt-1">
          <Badge variant={zones.hasProductTypeInMobile ? 'default' : 'outline'} className="text-[10px]">
            Product Type
          </Badge>
          <Badge variant={zones.hasDimensionInDesktop ? 'default' : 'outline'} className="text-[10px]">
            Dimension
          </Badge>
          <Badge variant={zones.hasMaterialInDesktop ? 'default' : 'outline'} className="text-[10px]">
            Material
          </Badge>
          <Badge variant={zones.hasBrandAtEnd ? 'default' : 'outline'} className="text-[10px]">
            Brand
          </Badge>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function QualityAnalyzer({ title, description, platform }: QualityAnalyzerProps) {
  const analysis = useMemo(() => {
    if (!title && !description) return null
    return analyzeContent(title || '', description || '', platform)
  }, [title, description, platform])

  if (!analysis) {
    return (
      <Card className="h-fit">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Quality Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No content to analyze</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-fit">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Quality Analysis</CardTitle>
          <Badge
            className={cn(
              'font-bold text-sm px-2.5',
              getScoreColor(analysis.compositeScore)
            )}
          >
            {analysis.compositeScore}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score Breakdown */}
        <div className="space-y-2">
          <ScoreRow label="Title (CTR)" score={analysis.ctrProxy} />
          <ScoreRow label="Desc (CVR)" score={analysis.cvrProxy} />
          <ScoreRow label="Brand Voice" score={analysis.brandVoice} />
          <ScoreRow label="Readability" score={analysis.readability} />
        </div>

        {/* Title Zones */}
        <TitleZonesSection analysis={analysis} />

        {/* Issues */}
        {analysis.issues.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-medium flex items-center gap-1.5 text-yellow-600 dark:text-yellow-500">
              <AlertCircle className="h-3.5 w-3.5" />
              Issues ({analysis.issues.length})
            </h4>
            <ul className="text-xs space-y-1 pl-5">
              {analysis.issues.map((issue, i) => (
                <li key={i} className="text-muted-foreground list-disc">
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Suggestions */}
        {analysis.suggestions.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-medium flex items-center gap-1.5 text-blue-600 dark:text-blue-500">
              <Lightbulb className="h-3.5 w-3.5" />
              Suggestions
            </h4>
            <ul className="text-xs space-y-1 pl-5">
              {analysis.suggestions.map((suggestion, i) => (
                <li key={i} className="text-muted-foreground list-disc">
                  {suggestion}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Trust Signals */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Trust Signals</h4>
          <div className="flex flex-wrap gap-1">
            <TrustBadge label="Solid Brass" present={analysis.trustSignals.solidBrass} />
            <TrustBadge label="Warranty" present={analysis.trustSignals.lifetimeWarranty} />
            <TrustBadge label="Virginia" present={analysis.trustSignals.virginia} />
            <TrustBadge label="Finishes" present={analysis.trustSignals.finishVariety} />
            <TrustBadge label="Matching" present={analysis.trustSignals.matchingAccessories} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
