# Task: Implement Keyword Gap Analysis Dashboard

## Objective

Build a keyword gap analysis tool that systematically identifies which SKUs are missing important keywords, prioritizes optimization work by opportunity size, and provides specific keyword recommendations.

## Problem Statement

We don't systematically identify keyword gaps, leading to:
- Ad-hoc optimization decisions based on gut feeling
- No visibility into which SKUs have the biggest opportunity
- Titles that miss high-volume search terms
- Inefficient use of optimization resources

## Solution Overview

Build a keyword gap analyzer that:
1. Compares our titles to actual search queries from Google Ads
2. Identifies SKUs where high-volume queries aren't in titles
3. Prioritizes optimization by opportunity size (impressions × gap)
4. Shows specific keywords to add per SKU
5. Tracks gap closure progress over time

## Prerequisites

- Google Ads search term data (from Prompt 14)
- Generated content stored in Supabase
- Existing title/description data for SKUs

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/keyword-gaps/page.tsx` - Main keyword gap page
- `dashboard/src/app/api/keyword-gaps/route.ts` - Gap analysis API
- `dashboard/src/components/keyword-gaps/GapTable.tsx` - SKU gap prioritization table
- `dashboard/src/components/keyword-gaps/KeywordSuggestions.tsx` - Keyword recommendations
- `dashboard/src/components/keyword-gaps/OpportunityChart.tsx` - Visual opportunity sizing

### Scoring Logic
- `dashboard/src/lib/keyword-analysis.ts` - Gap detection and scoring

### Database
- `supabase/migrations/010_keyword_gap_tracking.sql`

## Database Schema

```sql
-- Track keyword gaps per SKU
CREATE TABLE keyword_gaps (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  keyword text NOT NULL,
  monthly_volume integer DEFAULT 0, -- estimated search volume
  our_impressions integer DEFAULT 0, -- impressions we got for this keyword
  in_title boolean DEFAULT false,
  in_description boolean DEFAULT false,
  gap_score numeric GENERATED ALWAYS AS (
    CASE
      WHEN in_title THEN 0
      WHEN in_description THEN monthly_volume * 0.3
      ELSE monthly_volume
    END
  ) STORED,
  updated_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, keyword)
);

-- SKU-level opportunity scores
CREATE TABLE sku_opportunity_scores (
  master_sku text PRIMARY KEY,
  total_gap_score numeric DEFAULT 0,
  keywords_missing integer DEFAULT 0,
  keywords_covered integer DEFAULT 0,
  coverage_percent numeric DEFAULT 0,
  estimated_ctr_lift numeric DEFAULT 0,
  priority_rank integer,
  last_calculated timestamptz DEFAULT now()
);

-- Track gap closure over time
CREATE TABLE gap_closure_history (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  snapshot_date date NOT NULL,
  total_gap_score numeric,
  keywords_missing integer,
  coverage_percent numeric,
  UNIQUE(master_sku, snapshot_date)
);

-- Indexes
CREATE INDEX idx_keyword_gaps_sku ON keyword_gaps(master_sku);
CREATE INDEX idx_keyword_gaps_score ON keyword_gaps(gap_score DESC);
CREATE INDEX idx_sku_opportunity_rank ON sku_opportunity_scores(priority_rank);
```

## Gap Scoring Algorithm

```typescript
// dashboard/src/lib/keyword-analysis.ts

export interface KeywordGap {
  keyword: string
  monthlyVolume: number
  ourImpressions: number
  inTitle: boolean
  inDescription: boolean
  gapScore: number
  priority: 'high' | 'medium' | 'low'
}

export interface SkuOpportunity {
  masterSku: string
  currentTitle: string
  totalGapScore: number
  keywordsMissing: number
  keywordsCovered: number
  coveragePercent: number
  estimatedCtrLift: number
  priorityRank: number
  topGaps: KeywordGap[]
}

/**
 * Calculate keyword gap score for a single keyword.
 *
 * Score factors:
 * - Monthly search volume (primary weight)
 * - Position in our content (title > description > nowhere)
 * - Our impression share for this keyword
 */
export function calculateGapScore(
  keyword: string,
  monthlyVolume: number,
  ourImpressions: number,
  inTitle: boolean,
  inDescription: boolean
): number {
  // If in title, no gap
  if (inTitle) return 0

  // Base score is monthly volume
  let score = monthlyVolume

  // Partial credit if in description (30% gap reduction)
  if (inDescription) {
    score = score * 0.3
  }

  // Bonus for keywords we're already getting impressions for
  // (indicates relevance - we should definitely be in title)
  if (ourImpressions > 0) {
    const impressionBonus = Math.min(ourImpressions / 100, 2) // Cap at 2x
    score = score * (1 + impressionBonus)
  }

  return Math.round(score)
}

/**
 * Analyze all keyword gaps for a SKU.
 */
export function analyzeSkuGaps(
  masterSku: string,
  currentTitle: string,
  currentDescription: string,
  searchQueries: Array<{
    queryText: string
    impressions: number
    clicks: number
  }>
): SkuOpportunity {
  const titleLower = currentTitle.toLowerCase()
  const descLower = currentDescription?.toLowerCase() || ''

  const gaps: KeywordGap[] = []
  let totalGapScore = 0
  let keywordsMissing = 0
  let keywordsCovered = 0

  // Extract keywords from search queries
  const keywordStats = new Map<string, {
    volume: number
    impressions: number
  }>()

  for (const query of searchQueries) {
    const words = query.queryText.toLowerCase().split(/\s+/)
    for (const word of words) {
      // Skip stop words and short words
      if (word.length < 3 || isStopWord(word)) continue

      const existing = keywordStats.get(word) || { volume: 0, impressions: 0 }
      keywordStats.set(word, {
        volume: existing.volume + query.impressions, // Use impressions as volume proxy
        impressions: existing.impressions + query.impressions
      })
    }
  }

  // Analyze each keyword
  for (const [keyword, stats] of keywordStats) {
    const inTitle = titleLower.includes(keyword)
    const inDescription = descLower.includes(keyword)
    const gapScore = calculateGapScore(
      keyword,
      stats.volume,
      stats.impressions,
      inTitle,
      inDescription
    )

    if (inTitle) {
      keywordsCovered++
    } else {
      keywordsMissing++
      totalGapScore += gapScore
    }

    gaps.push({
      keyword,
      monthlyVolume: stats.volume,
      ourImpressions: stats.impressions,
      inTitle,
      inDescription,
      gapScore,
      priority: gapScore > 1000 ? 'high' : gapScore > 500 ? 'medium' : 'low'
    })
  }

  // Sort by gap score
  gaps.sort((a, b) => b.gapScore - a.gapScore)

  const totalKeywords = keywordsCovered + keywordsMissing
  const coveragePercent = totalKeywords > 0
    ? (keywordsCovered / totalKeywords) * 100
    : 0

  // Estimate CTR lift based on gap closure potential
  // Research suggests 10-15% keyword coverage improvement = 5-10% CTR lift
  const estimatedCtrLift = Math.min((100 - coveragePercent) * 0.15, 25)

  return {
    masterSku,
    currentTitle,
    totalGapScore,
    keywordsMissing,
    keywordsCovered,
    coveragePercent,
    estimatedCtrLift,
    priorityRank: 0, // Calculated later across all SKUs
    topGaps: gaps.filter(g => g.gapScore > 0).slice(0, 10)
  }
}

/**
 * Rank SKUs by optimization opportunity.
 */
export function rankOpportunities(
  opportunities: SkuOpportunity[]
): SkuOpportunity[] {
  // Sort by total gap score (highest opportunity first)
  const ranked = [...opportunities].sort((a, b) => b.totalGapScore - a.totalGapScore)

  // Assign ranks
  ranked.forEach((opp, index) => {
    opp.priorityRank = index + 1
  })

  return ranked
}

const STOP_WORDS = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
  'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
  'could', 'should', 'may', 'might', 'must', 'that', 'this', 'these',
  'those', 'it', 'its', 'your', 'our', 'their', 'we', 'you', 'they'
])

function isStopWord(word: string): boolean {
  return STOP_WORDS.has(word)
}
```

## API Implementation

### GET /api/keyword-gaps

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const sku = searchParams.get('sku')
  const limit = parseInt(searchParams.get('limit') || '20')

  const supabase = await createClient()

  if (sku) {
    // Get gaps for specific SKU
    const { data: gaps } = await supabase
      .from('keyword_gaps')
      .select('*')
      .eq('master_sku', sku)
      .order('gap_score', { ascending: false })
      .limit(20)

    const { data: opportunity } = await supabase
      .from('sku_opportunity_scores')
      .select('*')
      .eq('master_sku', sku)
      .single()

    return NextResponse.json({ gaps, opportunity })
  }

  // Get all SKU opportunities ranked
  const { data: opportunities } = await supabase
    .from('sku_opportunity_scores')
    .select('*')
    .order('priority_rank', { ascending: true })
    .limit(limit)

  // Get summary stats
  const { data: stats } = await supabase
    .from('sku_opportunity_scores')
    .select('total_gap_score, keywords_missing, coverage_percent')

  const summary = {
    totalSkus: stats?.length || 0,
    avgCoverage: stats?.reduce((sum, s) => sum + (s.coverage_percent || 0), 0) / (stats?.length || 1),
    totalGapScore: stats?.reduce((sum, s) => sum + (s.total_gap_score || 0), 0),
    totalKeywordsMissing: stats?.reduce((sum, s) => sum + (s.keywords_missing || 0), 0)
  }

  return NextResponse.json({ opportunities, summary })
}
```

### POST /api/keyword-gaps/analyze

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { analyzeSkuGaps, rankOpportunities } from '@/lib/keyword-analysis'

export async function POST(request: Request) {
  const { skus } = await request.json()

  const supabase = await createClient()
  const opportunities = []

  for (const sku of skus) {
    // Get current content
    const { data: content } = await supabase
      .from('generated_content')
      .select('candidate_content, content_type')
      .eq('master_sku', sku)
      .eq('is_current', true)
      .eq('platform', 'google')

    const title = content?.find(c => c.content_type === 'title')?.candidate_content || ''
    const description = content?.find(c => c.content_type === 'description')?.candidate_content || ''

    // Get search queries for this SKU
    const { data: queries } = await supabase
      .from('query_sku_mapping')
      .select(`
        search_queries (
          query_text,
          impressions,
          clicks
        )
      `)
      .eq('master_sku', sku)

    const queryData = queries?.map(q => ({
      queryText: q.search_queries?.query_text || '',
      impressions: q.search_queries?.impressions || 0,
      clicks: q.search_queries?.clicks || 0
    })) || []

    const opportunity = analyzeSkuGaps(sku, title, description, queryData)
    opportunities.push(opportunity)

    // Save gaps to database
    for (const gap of opportunity.topGaps) {
      await supabase
        .from('keyword_gaps')
        .upsert({
          master_sku: sku,
          keyword: gap.keyword,
          monthly_volume: gap.monthlyVolume,
          our_impressions: gap.ourImpressions,
          in_title: gap.inTitle,
          in_description: gap.inDescription
        }, {
          onConflict: 'master_sku,keyword'
        })
    }
  }

  // Rank opportunities
  const ranked = rankOpportunities(opportunities)

  // Save opportunity scores
  for (const opp of ranked) {
    await supabase
      .from('sku_opportunity_scores')
      .upsert({
        master_sku: opp.masterSku,
        total_gap_score: opp.totalGapScore,
        keywords_missing: opp.keywordsMissing,
        keywords_covered: opp.keywordsCovered,
        coverage_percent: opp.coveragePercent,
        estimated_ctr_lift: opp.estimatedCtrLift,
        priority_rank: opp.priorityRank,
        last_calculated: new Date().toISOString()
      }, {
        onConflict: 'master_sku'
      })
  }

  return NextResponse.json({
    success: true,
    analyzed: skus.length,
    topOpportunities: ranked.slice(0, 5)
  })
}
```

## UI Components

### GapTable.tsx

```tsx
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
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ArrowRight, TrendingUp } from 'lucide-react'
import Link from 'next/link'

interface Opportunity {
  master_sku: string
  total_gap_score: number
  keywords_missing: number
  keywords_covered: number
  coverage_percent: number
  estimated_ctr_lift: number
  priority_rank: number
}

interface GapTableProps {
  opportunities: Opportunity[]
}

export function GapTable({ opportunities }: GapTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead>SKU</TableHead>
          <TableHead className="text-right">Gap Score</TableHead>
          <TableHead className="text-right">Missing</TableHead>
          <TableHead>Coverage</TableHead>
          <TableHead className="text-right">Est. CTR Lift</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {opportunities.map((opp) => (
          <TableRow key={opp.master_sku}>
            <TableCell className="font-medium">
              <Badge variant={opp.priority_rank <= 5 ? 'destructive' : 'secondary'}>
                {opp.priority_rank}
              </Badge>
            </TableCell>
            <TableCell>{opp.master_sku}</TableCell>
            <TableCell className="text-right font-mono">
              {opp.total_gap_score.toLocaleString()}
            </TableCell>
            <TableCell className="text-right">
              <span className="text-red-600">{opp.keywords_missing}</span>
              {' / '}
              <span className="text-green-600">{opp.keywords_covered}</span>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Progress value={opp.coverage_percent} className="w-20 h-2" />
                <span className="text-xs text-muted-foreground">
                  {opp.coverage_percent.toFixed(0)}%
                </span>
              </div>
            </TableCell>
            <TableCell className="text-right">
              <span className="flex items-center justify-end gap-1 text-green-600">
                <TrendingUp className="h-3 w-3" />
                +{opp.estimated_ctr_lift.toFixed(0)}%
              </span>
            </TableCell>
            <TableCell>
              <Button variant="ghost" size="sm" asChild>
                <Link href={`/keyword-gaps/${opp.master_sku}`}>
                  Details <ArrowRight className="h-3 w-3 ml-1" />
                </Link>
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

### KeywordSuggestions.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Check, Copy, Plus } from 'lucide-react'
import { useState } from 'react'

interface KeywordGap {
  keyword: string
  monthly_volume: number
  our_impressions: number
  in_title: boolean
  in_description: boolean
  gap_score: number
}

interface KeywordSuggestionsProps {
  sku: string
  currentTitle: string
  gaps: KeywordGap[]
  onAddKeyword?: (keyword: string) => void
}

export function KeywordSuggestions({
  sku,
  currentTitle,
  gaps,
  onAddKeyword
}: KeywordSuggestionsProps) {
  const [copiedTitle, setCopiedTitle] = useState(false)

  // Generate suggested title with top missing keywords
  const topMissingKeywords = gaps
    .filter(g => !g.in_title && g.gap_score > 0)
    .slice(0, 3)
    .map(g => g.keyword)

  const suggestedTitle = generateSuggestedTitle(currentTitle, topMissingKeywords)

  async function copyTitle() {
    await navigator.clipboard.writeText(suggestedTitle)
    setCopiedTitle(true)
    setTimeout(() => setCopiedTitle(false), 2000)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Keyword Suggestions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current vs Suggested Title */}
        <div className="space-y-2">
          <div className="text-sm">
            <span className="font-medium">Current:</span>
            <p className="text-muted-foreground mt-1">{currentTitle}</p>
          </div>
          <div className="text-sm">
            <span className="font-medium text-green-600">Suggested:</span>
            <p className="mt-1 p-2 bg-green-50 rounded border border-green-200">
              {suggestedTitle}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={copyTitle}
            >
              {copiedTitle ? (
                <Check className="h-3 w-3 mr-1" />
              ) : (
                <Copy className="h-3 w-3 mr-1" />
              )}
              {copiedTitle ? 'Copied!' : 'Copy Title'}
            </Button>
          </div>
        </div>

        {/* Missing keywords list */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Missing High-Value Keywords</h4>
          <div className="space-y-1">
            {gaps
              .filter(g => !g.in_title)
              .slice(0, 8)
              .map((gap, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        gap.gap_score > 1000
                          ? 'destructive'
                          : gap.gap_score > 500
                          ? 'default'
                          : 'secondary'
                      }
                      className="text-xs"
                    >
                      {gap.gap_score > 1000 ? 'High' : gap.gap_score > 500 ? 'Med' : 'Low'}
                    </Badge>
                    <span>"{gap.keyword}"</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {gap.monthly_volume.toLocaleString()} vol
                    </span>
                    {onAddKeyword && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => onAddKeyword(gap.keyword)}
                      >
                        <Plus className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Covered keywords */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-green-600">Covered Keywords</h4>
          <div className="flex flex-wrap gap-1">
            {gaps
              .filter(g => g.in_title)
              .slice(0, 10)
              .map((gap, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {gap.keyword}
                </Badge>
              ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function generateSuggestedTitle(
  currentTitle: string,
  keywordsToAdd: string[]
): string {
  // Simple insertion logic - in production, use LLM for natural integration
  let suggested = currentTitle

  for (const keyword of keywordsToAdd) {
    // Check if keyword is already in title (case-insensitive)
    if (suggested.toLowerCase().includes(keyword.toLowerCase())) {
      continue
    }

    // Try to insert naturally
    // This is simplified - production would use more sophisticated NLP
    if (suggested.includes(' - ')) {
      // Insert before brand name if present
      const parts = suggested.split(' - ')
      parts[0] = `${parts[0]}, ${keyword}`
      suggested = parts.join(' - ')
    } else {
      // Append to end
      suggested = `${suggested} ${keyword}`
    }
  }

  return suggested
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/keyword-gaps/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { GapTable } from '@/components/keyword-gaps/GapTable'
import { RefreshCw, Target, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'

export default function KeywordGapsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    const res = await fetch('/api/keyword-gaps')
    const json = await res.json()
    setData(json)
    setLoading(false)
  }

  async function runAnalysis() {
    setAnalyzing(true)
    // Get all pilot SKUs
    const skuRes = await fetch('/api/skus?status=pilot')
    const { skus } = await skuRes.json()

    await fetch('/api/keyword-gaps/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skus: skus.map((s: any) => s.master_sku) })
    })

    setAnalyzing(false)
    fetchData()
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Keyword Gap Analysis</h1>
          <p className="text-muted-foreground">
            Identify missing keywords and prioritize optimization by opportunity
          </p>
        </div>
        <Button onClick={runAnalysis} disabled={analyzing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${analyzing ? 'animate-spin' : ''}`} />
          {analyzing ? 'Analyzing...' : 'Run Analysis'}
        </Button>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : data ? (
        <>
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Target className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">SKUs Analyzed</p>
                    <p className="text-2xl font-bold">{data.summary.totalSkus}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Coverage</p>
                    <p className="text-2xl font-bold text-green-600">
                      {data.summary.avgCoverage.toFixed(0)}%
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <div>
                    <p className="text-sm text-muted-foreground">Total Gap Score</p>
                    <p className="text-2xl font-bold text-red-600">
                      {data.summary.totalGapScore.toLocaleString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-600" />
                  <div>
                    <p className="text-sm text-muted-foreground">Keywords Missing</p>
                    <p className="text-2xl font-bold text-blue-600">
                      {data.summary.totalKeywordsMissing}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Opportunity Table */}
          <Card>
            <CardHeader>
              <CardTitle>Optimization Priorities</CardTitle>
            </CardHeader>
            <CardContent>
              <GapTable opportunities={data.opportunities || []} />
            </CardContent>
          </Card>

          {/* Insights */}
          <Card>
            <CardHeader>
              <CardTitle>Key Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.opportunities?.[0] && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200">
                  <p className="text-sm font-medium text-red-800">
                    Highest Opportunity: SKU {data.opportunities[0].master_sku}
                  </p>
                  <p className="text-xs text-red-700 mt-1">
                    Gap score: {data.opportunities[0].total_gap_score.toLocaleString()} |
                    Missing {data.opportunities[0].keywords_missing} keywords |
                    Est. +{data.opportunities[0].estimated_ctr_lift.toFixed(0)}% CTR
                  </p>
                </div>
              )}

              {data.summary.avgCoverage < 60 && (
                <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
                  <p className="text-sm font-medium text-yellow-800">
                    Low Overall Coverage
                  </p>
                  <p className="text-xs text-yellow-700 mt-1">
                    Average keyword coverage is {data.summary.avgCoverage.toFixed(0)}%.
                    Target: 75%+
                  </p>
                </div>
              )}

              {data.summary.avgCoverage >= 75 && (
                <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                  <p className="text-sm font-medium text-green-800">
                    Good Keyword Coverage
                  </p>
                  <p className="text-xs text-green-700 mt-1">
                    Average coverage at {data.summary.avgCoverage.toFixed(0)}%.
                    Focus on high-gap SKUs for incremental gains.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
```

## Success Criteria

1. [ ] Gap analysis algorithm correctly identifies missing keywords
2. [ ] SKUs ranked by opportunity score
3. [ ] Keyword suggestions displayed per SKU
4. [ ] Coverage tracking shows improvement over time
5. [ ] Integration with content generation (gaps inform prompts)
6. [ ] Run analysis button processes all pilot SKUs
7. [ ] Export functionality for optimization queue

## Future Enhancements

- Auto-generate title variations with missing keywords
- A/B test keyword-optimized vs original titles
- Competitor keyword comparison
- Seasonal keyword opportunities
- Category-level gap analysis
