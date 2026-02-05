'use client'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { CompetitionLevel } from '@/lib/supabase/types'

interface QueryData {
  id?: string
  query_text: string
  impressions?: number
  clicks?: number
  conversions?: number
  conversion_value?: number
  ctr?: number
  cvr?: number
  // Variant info
  finish?: string | null
  finish_code?: string | null
  variant_count?: number
  // Aggregated fields
  total_impressions?: number
  total_clicks?: number
  total_conversions?: number
  total_conversion_value?: number
  // Keyword Planner metrics
  avg_monthly_searches?: number | null
  competition?: CompetitionLevel | null
  competition_index?: number | null
}

interface QueryTableProps {
  queries: QueryData[]
  viewType: 'aggregate' | 'variant' | 'shopify' | 'all'
  showKeywordMetrics?: boolean
  currentTitle?: string
}

export function QueryTable({
  queries,
  viewType,
  showKeywordMetrics = true,
  currentTitle,
}: QueryTableProps) {
  // Parse title words for gap detection
  const titleWords = currentTitle
    ? new Set(
        currentTitle
          .toLowerCase()
          .split(/\s+/)
          .filter((w) => w.length > 3)
      )
    : new Set<string>()

  function hasKeyword(query: string): boolean {
    if (!currentTitle) return true // No title to compare against
    const queryWords = query.toLowerCase().split(/\s+/)
    return queryWords.some((word) => titleWords.has(word) && word.length > 3)
  }

  function getCompetitionBadge(competition: CompetitionLevel | null | undefined) {
    if (!competition || competition === 'UNSPECIFIED') {
      return <Badge variant="outline">N/A</Badge>
    }

    const variants: Record<CompetitionLevel, 'default' | 'secondary' | 'destructive'> = {
      LOW: 'default',
      MEDIUM: 'secondary',
      HIGH: 'destructive',
      UNSPECIFIED: 'outline' as 'default',
    }

    return <Badge variant={variants[competition]}>{competition}</Badge>
  }

  function formatNumber(num: number | null | undefined): string {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString()
  }

  function formatCurrency(num: number | null | undefined): string {
    if (num === null || num === undefined) return '-'
    return `$${num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`
  }

  function formatPercent(num: number | null | undefined): string {
    if (num === null || num === undefined) return '-'
    return `${(num * 100).toFixed(2)}%`
  }

  // Get impressions/clicks based on view type
  function getImpressions(q: QueryData): number {
    return q.total_impressions ?? q.impressions ?? 0
  }

  function getClicks(q: QueryData): number {
    return q.total_clicks ?? q.clicks ?? 0
  }

  function getConversionValue(q: QueryData): number {
    return q.total_conversion_value ?? q.conversion_value ?? 0
  }

  return (
    <TooltipProvider>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[300px]">Search Query</TableHead>
              {viewType === 'variant' && <TableHead>Finish</TableHead>}
              {viewType === 'aggregate' && <TableHead>Variants</TableHead>}
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
              <TableHead className="text-right">CTR</TableHead>
              <TableHead className="text-right">Conv. Value</TableHead>
              {showKeywordMetrics && (
                <>
                  <TableHead className="text-right">Search Vol.</TableHead>
                  <TableHead>Competition</TableHead>
                </>
              )}
              {currentTitle && <TableHead className="text-center">In Title?</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {queries.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={showKeywordMetrics ? (currentTitle ? 10 : 9) : (currentTitle ? 8 : 7)}
                  className="text-center py-8 text-muted-foreground"
                >
                  No search queries found
                </TableCell>
              </TableRow>
            ) : (
              queries.map((query, idx) => {
                const impressions = getImpressions(query)
                const clicks = getClicks(query)
                const ctr = impressions > 0 ? clicks / impressions : 0
                const covered = hasKeyword(query.query_text)

                return (
                  <TableRow key={query.id || idx}>
                    <TableCell className="font-medium">
                      <div className="max-w-[300px] truncate" title={query.query_text}>
                        {query.query_text}
                      </div>
                    </TableCell>

                    {viewType === 'variant' && (
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {query.finish_code || 'N/A'}
                        </Badge>
                      </TableCell>
                    )}

                    {viewType === 'aggregate' && (
                      <TableCell>
                        <Tooltip>
                          <TooltipTrigger>
                            <Badge variant="secondary">
                              {query.variant_count || 1} variants
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent>
                            This query triggered {query.variant_count || 1} different
                            finish variants
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                    )}

                    <TableCell className="text-right font-mono">
                      {formatNumber(impressions)}
                    </TableCell>

                    <TableCell className="text-right font-mono">
                      {formatNumber(clicks)}
                    </TableCell>

                    <TableCell className="text-right font-mono">
                      {formatPercent(ctr)}
                    </TableCell>

                    <TableCell className="text-right font-mono">
                      {formatCurrency(getConversionValue(query))}
                    </TableCell>

                    {showKeywordMetrics && (
                      <>
                        <TableCell className="text-right font-mono">
                          <SearchVolumeIndicator
                            volume={query.avg_monthly_searches}
                          />
                        </TableCell>
                        <TableCell>
                          {getCompetitionBadge(query.competition)}
                        </TableCell>
                      </>
                    )}

                    {currentTitle && (
                      <TableCell className="text-center">
                        {covered ? (
                          <Badge variant="default" className="bg-green-600">
                            Yes
                          </Badge>
                        ) : (
                          <Badge variant="destructive">Gap</Badge>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  )
}

function SearchVolumeIndicator({ volume }: { volume: number | null | undefined }) {
  if (volume === null || volume === undefined) {
    return <span className="text-muted-foreground">-</span>
  }

  // Color code by volume tier
  let colorClass = 'text-muted-foreground'
  let icon = <Minus className="h-3 w-3 inline mr-1" />

  if (volume >= 1000) {
    colorClass = 'text-green-600 font-medium'
    icon = <TrendingUp className="h-3 w-3 inline mr-1" />
  } else if (volume >= 100) {
    colorClass = 'text-blue-600'
    icon = <Minus className="h-3 w-3 inline mr-1" />
  } else if (volume > 0) {
    colorClass = 'text-muted-foreground'
    icon = <TrendingDown className="h-3 w-3 inline mr-1" />
  }

  return (
    <span className={colorClass}>
      {icon}
      {volume.toLocaleString()}/mo
    </span>
  )
}
