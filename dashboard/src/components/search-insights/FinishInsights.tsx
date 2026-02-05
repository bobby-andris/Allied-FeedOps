'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, Search, Eye, MousePointer } from 'lucide-react'

interface FinishData {
  finish: string | null
  finish_code: string | null
  queries: Array<{
    query_text: string
    impressions: number
    clicks: number
  }>
  totalImpressions: number
  totalClicks: number
}

interface FinishInsightsProps {
  byFinish: Record<string, FinishData>
  maxDisplay?: number
}

export function FinishInsights({ byFinish, maxDisplay = 6 }: FinishInsightsProps) {
  const finishes = Object.values(byFinish)
    .filter((f) => f.finish_code)
    .sort((a, b) => b.totalImpressions - a.totalImpressions)

  if (finishes.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      <h3 className="font-semibold flex items-center gap-2">
        <TrendingUp className="h-5 w-5" />
        Queries by Finish Variant
      </h3>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {finishes.slice(0, maxDisplay).map((finish) => {
          const ctr =
            finish.totalImpressions > 0
              ? (finish.totalClicks / finish.totalImpressions) * 100
              : 0

          // Check if any queries contain finish-related keywords
          const finishKeywords = finish.finish
            ?.toLowerCase()
            .split(' ')
            .filter((w) => w.length > 3) || []

          const hasFinishSpecificQueries = finish.queries.some((q) =>
            finishKeywords.some((kw) => q.query_text.toLowerCase().includes(kw))
          )

          return (
            <Card key={finish.finish_code}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span className="truncate">{finish.finish || finish.finish_code}</span>
                  <Badge variant="outline">{finish.finish_code}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-4 text-xs text-muted-foreground mb-3">
                  <span className="flex items-center gap-1">
                    <Eye className="h-3 w-3" />
                    {finish.totalImpressions.toLocaleString()}
                  </span>
                  <span className="flex items-center gap-1">
                    <MousePointer className="h-3 w-3" />
                    {finish.totalClicks.toLocaleString()}
                  </span>
                  <span>{ctr.toFixed(1)}% CTR</span>
                </div>

                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    Top queries:
                  </p>
                  {finish.queries.slice(0, 3).map((q, i) => (
                    <div
                      key={i}
                      className="flex justify-between text-xs gap-2"
                    >
                      <span className="truncate flex-1" title={q.query_text}>
                        {`"${q.query_text}"`}
                      </span>
                      <span className="text-muted-foreground whitespace-nowrap">
                        {q.impressions.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>

                {hasFinishSpecificQueries && (
                  <div className="mt-3 p-2 rounded bg-green-50 dark:bg-green-950 text-xs text-green-700 dark:text-green-300">
                    <Search className="h-3 w-3 inline mr-1" />
                    Finish-specific queries detected
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {finishes.length > maxDisplay && (
        <p className="text-sm text-muted-foreground text-center">
          Showing top {maxDisplay} of {finishes.length} finishes with query data
        </p>
      )}
    </div>
  )
}
