'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'

interface QueryData {
  query_text: string
  impressions?: number
  total_impressions?: number
  avg_monthly_searches?: number | null
  competition?: string | null
}

interface GapAnalysisProps {
  queries: QueryData[]
  currentTitle?: string
  currentDescription?: string
}

export function GapAnalysis({
  queries,
  currentTitle,
  currentDescription,
}: GapAnalysisProps) {
  if (!currentTitle) {
    return null
  }

  // Parse title and description words
  const titleWords = new Set(
    currentTitle
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length > 3)
  )

  const descriptionWords = currentDescription
    ? new Set(
        currentDescription
          .toLowerCase()
          .split(/\s+/)
          .filter((w) => w.length > 3)
      )
    : new Set<string>()

  // Analyze each query for gaps
  const analysis = queries.map((q) => {
    const queryWords = q.query_text.toLowerCase().split(/\s+/)
    const significantWords = queryWords.filter((w) => w.length > 3)

    const inTitle = significantWords.some((w) => titleWords.has(w))
    const inDescription = significantWords.some((w) => descriptionWords.has(w))
    const impressions = q.total_impressions ?? q.impressions ?? 0

    return {
      query: q.query_text,
      impressions,
      searchVolume: q.avg_monthly_searches || 0,
      competition: q.competition,
      inTitle,
      inDescription,
      isGap: !inTitle,
      priority:
        !inTitle && impressions > 100
          ? 'high'
          : !inTitle && impressions > 10
          ? 'medium'
          : 'low',
    }
  })

  // Calculate coverage stats
  const totalQueries = analysis.length
  const coveredInTitle = analysis.filter((a) => a.inTitle).length
  const coveredInDesc = analysis.filter((a) => !a.inTitle && a.inDescription).length
  const gaps = analysis.filter((a) => a.isGap)
  const highPriorityGaps = gaps.filter((g) => g.priority === 'high')

  const coveragePercent = totalQueries > 0 ? (coveredInTitle / totalQueries) * 100 : 0

  // Sort gaps by impressions
  const sortedGaps = gaps.sort((a, b) => b.impressions - a.impressions).slice(0, 10)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Keyword Coverage Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Coverage Summary */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Title Coverage</span>
            <span className="font-medium">{coveragePercent.toFixed(0)}%</span>
          </div>
          <Progress value={coveragePercent} className="h-2" />
          <div className="flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3 text-green-500" />
              {coveredInTitle} in title
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3 text-blue-500" />
              {coveredInDesc} in description only
            </span>
            <span className="flex items-center gap-1">
              <AlertTriangle className="h-3 w-3 text-red-500" />
              {gaps.length} gaps
            </span>
          </div>
        </div>

        {/* High Priority Gaps */}
        {highPriorityGaps.length > 0 && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 dark:bg-red-950 dark:border-red-900">
            <p className="text-sm font-medium text-red-800 dark:text-red-200 mb-2">
              {highPriorityGaps.length} High-Priority Gaps (100+ impressions)
            </p>
            <div className="flex flex-wrap gap-2">
              {highPriorityGaps.slice(0, 5).map((gap, i) => (
                <Badge key={i} variant="destructive" className="text-xs">
                  {gap.query}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Gap List */}
        {sortedGaps.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Top Missing Keywords</p>
            <div className="space-y-1">
              {sortedGaps.map((gap, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <Badge
                      variant={
                        gap.priority === 'high'
                          ? 'destructive'
                          : gap.priority === 'medium'
                          ? 'default'
                          : 'secondary'
                      }
                      className="text-xs shrink-0"
                    >
                      {gap.priority === 'high'
                        ? 'High'
                        : gap.priority === 'medium'
                        ? 'Med'
                        : 'Low'}
                    </Badge>
                    <span className="truncate" title={gap.query}>
                      {`"${gap.query}"`}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                    <span>{gap.impressions.toLocaleString()} imp</span>
                    {gap.searchVolume > 0 && (
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {gap.searchVolume.toLocaleString()}/mo
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No Gaps Message */}
        {gaps.length === 0 && (
          <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950 text-center">
            <CheckCircle className="h-8 w-8 text-green-500 mx-auto mb-2" />
            <p className="text-sm font-medium text-green-800 dark:text-green-200">
              Great coverage! All high-volume search terms are in your title.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
