'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown, ChevronRight, Check, X, Lightbulb } from 'lucide-react'
import type { CompetitorPattern } from '@/lib/supabase/types'
import {
  getPatternLabel,
  checkIfContentHasPattern,
} from '@/lib/competitors/pattern-extraction'

interface PatternAnalysisProps {
  patterns: CompetitorPattern[]
  ourContent?: {
    title: string | null
    description: string | null
  } | null
}

const PATTERN_TYPE_LABELS: Record<string, string> = {
  title_structure: 'Title Structure',
  keyword: 'Keywords',
  benefit: 'Benefits',
  trust_signal: 'Trust Signals',
  competitor_brand: 'Competitors',
}

const PATTERN_TYPE_ORDER = [
  'title_structure',
  'benefit',
  'trust_signal',
  'keyword',
  'competitor_brand',
]

export function PatternAnalysis({ patterns, ourContent }: PatternAnalysisProps) {
  const [openSections, setOpenSections] = useState<Set<string>>(
    new Set(['title_structure', 'benefit'])
  )

  // Group patterns by type
  const grouped = patterns.reduce(
    (acc, p) => {
      if (!acc[p.pattern_type]) acc[p.pattern_type] = []
      acc[p.pattern_type].push(p)
      return acc
    },
    {} as Record<string, CompetitorPattern[]>
  )

  const toggleSection = (type: string) => {
    const newOpen = new Set(openSections)
    if (newOpen.has(type)) {
      newOpen.delete(type)
    } else {
      newOpen.add(type)
    }
    setOpenSections(newOpen)
  }

  // Check if our content has a pattern
  const hasPattern = (pattern: CompetitorPattern): boolean => {
    if (!ourContent) return false
    return checkIfContentHasPattern(ourContent, pattern.pattern_type, pattern.pattern_value)
  }

  const maxFrequency = Math.max(...patterns.map((p) => p.frequency), 1)

  // Get suggestions (high-frequency patterns we don't have)
  const suggestions = ourContent
    ? patterns
        .filter((p) => p.frequency >= 3 && p.pattern_type !== 'competitor_brand' && !hasPattern(p))
        .slice(0, 3)
    : []

  return (
    <div className="space-y-3">
      {PATTERN_TYPE_ORDER.filter((type) => grouped[type]?.length).map((type) => {
        const typePatterns = grouped[type]
        return (
          <Collapsible
            key={type}
            open={openSections.has(type)}
            onOpenChange={() => toggleSection(type)}
          >
            <CollapsibleTrigger className="flex items-center gap-2 w-full hover:bg-muted/50 p-2 rounded-lg transition-colors">
              {openSections.has(type) ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <span className="font-medium text-sm">
                {PATTERN_TYPE_LABELS[type] || type}
              </span>
              <Badge variant="outline" className="ml-auto">
                {typePatterns.length}
              </Badge>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2 space-y-1.5">
              {typePatterns.slice(0, 10).map((pattern, i) => {
                const has = hasPattern(pattern)
                const label = getPatternLabel(pattern.pattern_type, pattern.pattern_value)

                return (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-sm pl-6 py-0.5"
                  >
                    {ourContent && pattern.pattern_type !== 'competitor_brand' && (
                      <span
                        className={has ? 'text-green-600' : 'text-muted-foreground'}
                      >
                        {has ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <X className="h-3 w-3" />
                        )}
                      </span>
                    )}
                    {pattern.pattern_type === 'competitor_brand' && (
                      <span className="w-3" />
                    )}
                    <span
                      className={`flex-1 truncate ${has ? 'text-green-700 font-medium' : ''}`}
                      title={label}
                    >
                      {label}
                    </span>
                    <div className="w-12">
                      <Progress
                        value={(pattern.frequency / maxFrequency) * 100}
                        className="h-1.5"
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-6 text-right">
                      {pattern.frequency}
                    </span>
                  </div>
                )
              })}
            </CollapsibleContent>
          </Collapsible>
        )
      })}

      {/* Suggestions based on missing patterns */}
      {suggestions.length > 0 && (
        <Card className="mt-4 border-blue-200 bg-blue-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2 text-blue-700">
              <Lightbulb className="h-4 w-4" />
              Suggestions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="text-xs space-y-1.5 text-blue-800">
              {suggestions.map((p, i) => (
                <li key={i}>
                  Consider adding:{' '}
                  <strong>{getPatternLabel(p.pattern_type, p.pattern_value)}</strong>
                  <span className="text-blue-600">
                    {' '}
                    ({p.frequency} competitors use this)
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
