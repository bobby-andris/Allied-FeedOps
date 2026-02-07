'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, Search, AlertTriangle, Check, X } from 'lucide-react'
import { Card } from '@/components/ui/card'

// ============================================================================
// Types
// ============================================================================

export interface SearchQuery {
  query_text: string
  total_impressions: number
  total_clicks: number
  avg_monthly_searches: number | null
  competition: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNSPECIFIED' | null
  competition_index: number | null
}

export interface KeywordGap {
  query: SearchQuery
  missingWords: string[]
  suggestion: string
}

export interface StatusIndicator {
  color: 'green' | 'yellow' | 'red'
  label: string
  count?: number
}

interface SearchInsightsCardProps {
  masterSku: string
  currentTitle?: string
  currentDescription?: string
}

// ============================================================================
// Business Logic - Gap Analysis
// ============================================================================

const STOPWORDS = new Set([
  'with',
  'and',
  'the',
  'for',
  'from',
  'a',
  'an',
  'in',
  'on',
  'at',
  'to',
  'of',
])

export function analyzeKeywordGaps(
  queries: SearchQuery[],
  title: string
): KeywordGap[] {
  if (!title) return []

  const titleLower = title.toLowerCase()
  const gaps: KeywordGap[] = []

  for (const query of queries) {
    const words = query.query_text.toLowerCase().split(/\s+/)
    const significantWords = words.filter(
      (w) => w.length > 3 && !STOPWORDS.has(w)
    )

    const missingWords = significantWords.filter((w) => !titleLower.includes(w))
    const hasHighVolume =
      (query.avg_monthly_searches ?? 0) >= 500 || query.total_impressions >= 100

    // Only flag as gap if ALL significant words are missing and volume is high
    if (
      hasHighVolume &&
      missingWords.length > 0 &&
      missingWords.length === significantWords.length
    ) {
      gaps.push({
        query,
        missingWords,
        suggestion:
          query.avg_monthly_searches && query.avg_monthly_searches > 1000
            ? 'Add to title'
            : 'Consider for description',
      })
    }
  }

  // Return top 3 gaps sorted by volume
  return gaps
    .sort(
      (a, b) =>
        (b.query.avg_monthly_searches ?? 0) - (a.query.avg_monthly_searches ?? 0)
    )
    .slice(0, 3)
}

// ============================================================================
// Business Logic - Status Indicator
// ============================================================================

function checkQueryInTitle(query: SearchQuery, title: string): boolean {
  if (!title) return false

  const titleLower = title.toLowerCase()
  const words = query.query_text.toLowerCase().split(/\s+/)
  const significantWords = words.filter((w) => w.length > 3 && !STOPWORDS.has(w))

  // Returns true if ANY significant word from query is in title
  return significantWords.some((word) => titleLower.includes(word))
}

export function getStatusIndicator(
  gaps: KeywordGap[],
  topQuery: SearchQuery,
  title: string
): StatusIndicator {
  const topQueryInTitle = checkQueryInTitle(topQuery, title)

  // Critical: Top query not in title
  if (!topQueryInTitle) {
    return { color: 'red', label: 'Critical', count: gaps.length }
  }

  // Action required: 4+ keyword gaps
  if (gaps.length >= 4) {
    return { color: 'red', label: 'Action Required', count: gaps.length }
  }

  // Needs attention: 1-3 keyword gaps
  if (gaps.length >= 1) {
    return { color: 'yellow', label: 'Review', count: gaps.length }
  }

  // Optimized: No gaps
  return { color: 'green', label: 'Optimized' }
}

// ============================================================================
// Utilities
// ============================================================================

export function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return String(value)
}

function getMatchStatus(query: SearchQuery, title: string, description?: string): {
  icon: React.ReactNode
  text: string
} {
  const titleLower = title?.toLowerCase() ?? ''
  const descLower = description?.toLowerCase() ?? ''
  const queryLower = query.query_text.toLowerCase()
  const words = queryLower.split(/\s+/).filter((w) => w.length > 3 && !STOPWORDS.has(w))

  const inTitle = words.some((w) => titleLower.includes(w))
  const inDesc = words.some((w) => descLower.includes(w))

  if (inTitle) {
    return {
      icon: <Check className="h-3 w-3 text-[var(--insight-positive)]" />,
      text: 'in title',
    }
  }
  if (inDesc) {
    return {
      icon: <AlertTriangle className="h-3 w-3 text-[var(--insight-warning)]" />,
      text: 'desc only',
    }
  }
  return {
    icon: <X className="h-3 w-3 text-[var(--insight-critical)]" />,
    text: 'missing',
  }
}

// ============================================================================
// UI Component
// ============================================================================

export function SearchInsightsCard({
  masterSku,
  currentTitle,
  currentDescription,
}: SearchInsightsCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [queries, setQueries] = useState<SearchQuery[]>([])
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
          sku: masterSku,
        })

        const res = await fetch(`/api/search-insights?${params}`)

        if (!res.ok) {
          throw new Error('Failed to fetch search insights')
        }

        const json = await res.json()
        setQueries(json.queries || [])
      } catch (err) {
        console.error('Error fetching search insights:', err)
        setError('Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    if (masterSku) {
      fetchData()
    }
  }, [masterSku])

  if (loading) {
    return (
      <Card className="overflow-hidden border border-gray-200">
        <div className="p-4">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Loading Search Insights...
            </span>
          </div>
        </div>
      </Card>
    )
  }

  if (error || queries.length === 0) {
    return (
      <Card className="overflow-hidden border border-gray-200">
        <div className="p-4">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Search Insights
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {error || 'No search data available'}
          </p>
        </div>
      </Card>
    )
  }

  const topQuery = queries[0]
  const gaps = analyzeKeywordGaps(queries, currentTitle || '')
  const status = getStatusIndicator(gaps, topQuery, currentTitle || '')
  const topQueries = queries.slice(0, 5)

  const statusColors = {
    green: 'bg-[var(--insight-positive)]',
    yellow: 'bg-[var(--insight-warning)]',
    red: 'bg-[var(--insight-critical)]',
  }

  return (
    <Card className="overflow-hidden border border-gray-200 search-insights-card">
      <style jsx>{`
        .search-insights-card {
          --insight-positive: #10b981;
          --insight-warning: #f59e0b;
          --insight-critical: #ef4444;
          --insight-neutral: #6b7280;
        }

        .query-mono {
          font-family: 'IBM Plex Mono', 'Courier New', monospace;
          font-size: 0.813rem;
          line-height: 1.4;
        }

        .data-table {
          font-variant-numeric: tabular-nums;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          animation: ${status.color === 'red' || status.color === 'yellow'
            ? 'pulse 2s ease-in-out infinite'
            : 'none'};
        }

        @keyframes pulse {
          0%,
          100% {
            opacity: 1;
          }
          50% {
            opacity: 0.6;
          }
        }

        .expand-section {
          animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .gap-section {
          animation-delay: 100ms;
        }
      `}</style>

      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <Search className="h-4 w-4 text-gray-500" />
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Search Insights
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Status indicator */}
          {status.count !== undefined && status.count > 0 && (
            <div className="flex items-center gap-1.5">
              <div
                className={`status-dot ${statusColors[status.color]}`}
                title={status.label}
              />
              <span className="text-xs text-gray-600 font-medium">
                {status.count} {status.count === 1 ? 'gap' : 'gaps'}
              </span>
            </div>
          )}

          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              isExpanded ? 'rotate-180' : ''
            }`}
          />
        </div>
      </div>

      {/* Collapsed preview */}
      {!isExpanded && (
        <div className="px-3 pb-3 border-t border-gray-100">
          <div className="flex items-center justify-between pt-2">
            <span className="query-mono text-gray-700 truncate flex-1 mr-4">
              &ldquo;{topQuery.query_text}&rdquo;
            </span>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-gray-500 data-table">
                {formatNumber(topQuery.avg_monthly_searches ?? topQuery.total_impressions)}
                /mo
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1 mt-1 text-xs text-gray-500">
            {getMatchStatus(topQuery, currentTitle || '', currentDescription).icon}
            <span>{getMatchStatus(topQuery, currentTitle || '', currentDescription).text}</span>
          </div>
        </div>
      )}

      {/* Expanded view */}
      {isExpanded && (
        <div className="border-t border-gray-100">
          {/* Top Queries Section */}
          <div className="p-3 expand-section">
            <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Top Queries
            </div>
            <div className="space-y-1">
              {topQueries.map((q, idx) => {
                const match = getMatchStatus(q, currentTitle || '', currentDescription)
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-1.5 px-2 rounded bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <span className="query-mono text-gray-800 truncate flex-1 mr-3">
                      {q.query_text}
                    </span>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs text-gray-600 data-table">
                        {formatNumber(q.avg_monthly_searches ?? q.total_impressions)}/mo
                      </span>
                      <div className="flex items-center gap-1">
                        {match.icon}
                        <span className="text-[10px] text-gray-500">{match.text}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Keyword Gaps Section */}
          {gaps.length > 0 && (
            <div className="p-3 bg-yellow-50 border-t border-yellow-100 expand-section gap-section">
              <div className="text-[10px] font-semibold text-yellow-800 uppercase tracking-wider mb-2">
                Keyword Gaps (high volume, not in content)
              </div>
              <div className="space-y-2">
                {gaps.map((gap, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 p-2 rounded bg-white border border-yellow-200"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-yellow-600 mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="query-mono text-yellow-900 font-medium">
                          &ldquo;{gap.query.query_text}&rdquo;
                        </span>
                        <span className="text-[10px] text-yellow-700 data-table shrink-0">
                          {formatNumber(
                            gap.query.avg_monthly_searches ?? gap.query.total_impressions
                          )}
                          /mo
                        </span>
                      </div>
                      <div className="text-[10px] text-yellow-700 mt-0.5">
                        {gap.suggestion}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
