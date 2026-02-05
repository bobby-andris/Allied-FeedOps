'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Search,
  TrendingUp,
  ExternalLink,
  AlertTriangle,
  Eye,
  MousePointer,
} from 'lucide-react'
import type { CompetitionLevel } from '@/lib/supabase/types'

interface SearchQuery {
  query_text: string
  total_impressions: number
  total_clicks: number
  avg_monthly_searches: number | null
  competition: CompetitionLevel | null
}

interface SearchInsightsData {
  stats?: {
    totalQueries: number
    totalImpressions: number
    totalClicks: number
  }
  queries?: SearchQuery[]
}

interface SearchInsightsSummaryProps {
  sku: string
  currentTitle?: string
  selectedFinish?: string | null
}

function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return String(value)
}

function CompetitionBadge({ level }: { level: CompetitionLevel | null }) {
  if (!level || level === 'UNSPECIFIED') return null

  const colors: Record<Exclude<CompetitionLevel, 'UNSPECIFIED'>, string> = {
    LOW: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    MEDIUM: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    HIGH: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  }

  return (
    <Badge variant="outline" className={`text-[10px] ${colors[level]}`}>
      {level}
    </Badge>
  )
}

function findGapQueries(
  queries: SearchQuery[],
  title: string | undefined
): SearchQuery[] {
  if (!title || !queries.length) return []

  const titleLower = title.toLowerCase()
  const gaps: SearchQuery[] = []

  for (const q of queries) {
    // Check if any significant word from query is NOT in title
    const words = q.query_text.toLowerCase().split(/\s+/)
    const significantWords = words.filter(
      (w) => w.length > 3 && !['with', 'and', 'the', 'for', 'from'].includes(w)
    )

    // If the query has high volume and key words are missing from title
    const hasHighVolume = (q.avg_monthly_searches ?? 0) >= 500 || q.total_impressions >= 100
    const missingWords = significantWords.filter((w) => !titleLower.includes(w))

    if (hasHighVolume && missingWords.length > 0 && missingWords.length === significantWords.length) {
      gaps.push(q)
    }
  }

  // Return top 3 gap queries sorted by volume
  return gaps
    .sort((a, b) => (b.avg_monthly_searches ?? 0) - (a.avg_monthly_searches ?? 0))
    .slice(0, 3)
}

export function SearchInsightsSummary({
  sku,
  currentTitle,
  selectedFinish,
}: SearchInsightsSummaryProps) {
  const [data, setData] = useState<SearchInsightsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)

      try {
        const params = new URLSearchParams({
          platform: 'google',
          view: 'aggregate',
          sku,
        })

        if (selectedFinish) {
          params.set('finish', selectedFinish)
        }

        const res = await fetch(`/api/search-insights?${params}`)

        if (!res.ok) {
          throw new Error('Failed to fetch search insights')
        }

        const json = await res.json()
        setData(json)
      } catch (err) {
        console.error('Error fetching search insights:', err)
        setError('Failed to load search insights')
      } finally {
        setLoading(false)
      }
    }

    if (sku) {
      fetchData()
    }
  }, [sku, selectedFinish])

  // Loading state
  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Insights
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
        </CardContent>
      </Card>
    )
  }

  // Error or no data state
  if (error || !data?.queries || data.queries.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Insights
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {error || 'No search data available for this SKU.'}
          </p>
          <Button variant="link" size="sm" asChild className="px-0 mt-2">
            <Link href={`/search-insights?sku=${sku}`}>
              Sync data on Search Insights page
              <ExternalLink className="h-3 w-3 ml-1" />
            </Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  const queries = data.queries.slice(0, 5)
  const gapQueries = findGapQueries(data.queries, currentTitle)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Insights
          </CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/search-insights?sku=${sku}`}>
              <TrendingUp className="h-4 w-4 mr-1" />
              Full Analysis
              <ExternalLink className="h-3 w-3 ml-1" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Stats row */}
        {data.stats && (
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Eye className="h-4 w-4" />
              <span>{formatNumber(data.stats.totalImpressions)} impressions</span>
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <MousePointer className="h-4 w-4" />
              <span>{formatNumber(data.stats.totalClicks)} clicks</span>
            </div>
          </div>
        )}

        {/* Gap alert */}
        {gapQueries.length > 0 && (
          <div className="p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 shrink-0" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                  Keyword Gap Detected
                </p>
                <p className="text-xs text-yellow-700 dark:text-yellow-300">
                  High-volume queries not in current title:
                </p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {gapQueries.map((q) => (
                    <Badge
                      key={q.query_text}
                      variant="secondary"
                      className="text-xs bg-yellow-100 dark:bg-yellow-900/40"
                    >
                      {q.query_text}
                      {q.avg_monthly_searches && (
                        <span className="ml-1 opacity-70">
                          ({formatNumber(q.avg_monthly_searches)}/mo)
                        </span>
                      )}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Top queries list */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Top Search Terms
          </p>
          <div className="space-y-1.5">
            {queries.map((q) => (
              <div
                key={q.query_text}
                className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
              >
                <span className="font-mono text-xs truncate flex-1 mr-2">
                  {q.query_text}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  {q.avg_monthly_searches && (
                    <span className="text-xs text-muted-foreground">
                      {formatNumber(q.avg_monthly_searches)}/mo
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {formatNumber(q.total_impressions)} imp
                  </span>
                  <CompetitionBadge level={q.competition} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
