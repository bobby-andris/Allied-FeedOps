# Task: Implement Search Query Insights Dashboard

## Objective

Build a search query insights dashboard that pulls actual search terms from Google Ads, identifies high-value queries, and feeds this data into content generation to ensure titles/descriptions match real search behavior.

## Problem Statement

We guess what people search for. We don't use ACTUAL search query data from Google Ads to inform content generation, leading to:
- Titles optimized for assumed keywords, not real queries
- Missing high-intent search terms that drive conversions
- Content that doesn't match how customers actually search
- No visibility into query-to-content alignment

## Solution Overview

Build a search query insights system that:
1. Pulls search terms from Google Ads Shopping campaigns
2. Analyzes which queries drive impressions, clicks, and conversions
3. Identifies gaps (high-volume queries not in our titles)
4. Feeds query data into content generation prompts
5. Tracks query coverage improvement over time

## Prerequisites

- Google Ads API credentials configured
- Google Ads customer ID: 6253381786
- Existing integration: `src/feedops/integrations/google_ads_performance.py`

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/search-insights/page.tsx` - Main search insights page
- `dashboard/src/app/api/search-insights/route.ts` - API for fetching search data
- `dashboard/src/components/search-insights/QueryTable.tsx` - Display queries with metrics
- `dashboard/src/components/search-insights/GapAnalysis.tsx` - Show missing keywords
- `dashboard/src/components/search-insights/TrendChart.tsx` - Query volume trends

### Python Integration
- `src/feedops/integrations/google_ads_search_terms.py` - Search term extraction

### Database
- `supabase/migrations/009_search_query_insights.sql`

## Database Schema

```sql
-- Store search query data from Google Ads
CREATE TABLE search_queries (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  query_text text NOT NULL,
  campaign_id text,
  impressions integer DEFAULT 0,
  clicks integer DEFAULT 0,
  conversions numeric DEFAULT 0,
  cost_micros bigint DEFAULT 0,
  ctr numeric GENERATED ALWAYS AS (
    CASE WHEN impressions > 0 THEN clicks::numeric / impressions ELSE 0 END
  ) STORED,
  cvr numeric GENERATED ALWAYS AS (
    CASE WHEN clicks > 0 THEN conversions / clicks ELSE 0 END
  ) STORED,
  period_start date NOT NULL,
  period_end date NOT NULL,
  fetched_at timestamptz DEFAULT now(),
  UNIQUE(query_text, period_start, period_end)
);

-- Map queries to SKUs they triggered
CREATE TABLE query_sku_mapping (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  query_id uuid REFERENCES search_queries(id),
  master_sku text NOT NULL,
  impressions integer DEFAULT 0,
  clicks integer DEFAULT 0,
  conversions numeric DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  UNIQUE(query_id, master_sku)
);

-- Track keyword inclusion in our content
CREATE TABLE keyword_coverage (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  keyword text NOT NULL,
  in_title boolean DEFAULT false,
  in_description boolean DEFAULT false,
  query_volume integer DEFAULT 0, -- monthly search volume
  updated_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, keyword)
);

-- Indexes
CREATE INDEX idx_search_queries_impressions ON search_queries(impressions DESC);
CREATE INDEX idx_search_queries_conversions ON search_queries(conversions DESC);
CREATE INDEX idx_keyword_coverage_sku ON keyword_coverage(master_sku);
```

## Google Ads Search Terms Query

### GAQL Query for Search Terms

```sql
SELECT
  search_term_view.search_term,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_micros,
  segments.product_item_id
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.advertising_channel_type = 'SHOPPING'
ORDER BY metrics.impressions DESC
LIMIT 500
```

### Python Implementation

```python
# src/feedops/integrations/google_ads_search_terms.py

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class SearchTermsClient:
    """Fetches search term data from Google Ads Shopping campaigns."""

    def __init__(self):
        self.customer_id = os.getenv('GOOGLE_ADS_CUSTOMER_ID', '6253381786')
        self.client = GoogleAdsClient.load_from_env()

    def fetch_search_terms(
        self,
        days: int = 30,
        limit: int = 500
    ) -> List[Dict]:
        """
        Fetch top search terms from Shopping campaigns.

        Returns list of dicts with:
        - search_term: The actual query text
        - impressions: Number of impressions
        - clicks: Number of clicks
        - conversions: Number of conversions
        - cost_micros: Cost in micros
        - product_item_id: GMC offer ID (if available)
        """
        ga_service = self.client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                segments.product_item_id
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.advertising_channel_type = 'SHOPPING'
            ORDER BY metrics.impressions DESC
            LIMIT {limit}
        """

        results = []
        try:
            response = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query
            )

            for batch in response:
                for row in batch.results:
                    results.append({
                        'search_term': row.search_term_view.search_term,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': row.metrics.conversions,
                        'cost_micros': row.metrics.cost_micros,
                        'product_item_id': row.segments.product_item_id or None
                    })

        except GoogleAdsException as e:
            print(f"Google Ads API error: {e}")
            raise

        return results

    def get_terms_for_sku(
        self,
        master_sku: str,
        shopify_product_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get search terms that triggered ads for a specific SKU.

        Uses the GMC offer ID pattern: shopify_us_{product_id}_{variant_id}
        """
        ga_service = self.client.get_service("GoogleAdsService")

        # Match any variant of this product
        offer_pattern = f"shopify_us_{shopify_product_id}_%"

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.advertising_channel_type = 'SHOPPING'
                AND segments.product_item_id LIKE '{offer_pattern}'
            ORDER BY metrics.impressions DESC
            LIMIT 100
        """

        results = []
        try:
            response = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query
            )

            for batch in response:
                for row in batch.results:
                    results.append({
                        'search_term': row.search_term_view.search_term,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': row.metrics.conversions
                    })

        except GoogleAdsException as e:
            print(f"Google Ads API error: {e}")
            raise

        return results

    def extract_keywords(self, search_terms: List[Dict]) -> List[Dict]:
        """
        Extract unique keywords from search terms weighted by performance.

        Returns list of keywords with aggregate metrics.
        """
        keyword_stats = {}

        for term in search_terms:
            # Tokenize search term
            words = term['search_term'].lower().split()

            for word in words:
                # Skip common stop words
                if word in ['a', 'an', 'the', 'for', 'in', 'on', 'with', 'and', 'or']:
                    continue

                if word not in keyword_stats:
                    keyword_stats[word] = {
                        'keyword': word,
                        'impressions': 0,
                        'clicks': 0,
                        'conversions': 0,
                        'term_count': 0
                    }

                keyword_stats[word]['impressions'] += term['impressions']
                keyword_stats[word]['clicks'] += term['clicks']
                keyword_stats[word]['conversions'] += term['conversions']
                keyword_stats[word]['term_count'] += 1

        # Sort by impressions
        keywords = sorted(
            keyword_stats.values(),
            key=lambda x: x['impressions'],
            reverse=True
        )

        return keywords[:50]  # Top 50 keywords
```

## API Implementation

### GET /api/search-insights

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const sku = searchParams.get('sku')
  const days = parseInt(searchParams.get('days') || '30')

  const supabase = await createClient()

  // Get top search queries
  let query = supabase
    .from('search_queries')
    .select('*')
    .order('impressions', { ascending: false })
    .limit(100)

  const { data: queries } = await query

  // Get keyword coverage for SKU if provided
  let coverage = null
  if (sku) {
    const { data } = await supabase
      .from('keyword_coverage')
      .select('*')
      .eq('master_sku', sku)
      .order('query_volume', { ascending: false })

    coverage = data
  }

  // Calculate summary stats
  const totalImpressions = queries?.reduce((sum, q) => sum + q.impressions, 0) || 0
  const totalClicks = queries?.reduce((sum, q) => sum + q.clicks, 0) || 0
  const totalConversions = queries?.reduce((sum, q) => sum + q.conversions, 0) || 0

  return NextResponse.json({
    queries,
    coverage,
    summary: {
      totalQueries: queries?.length || 0,
      totalImpressions,
      totalClicks,
      totalConversions,
      avgCtr: totalImpressions > 0 ? (totalClicks / totalImpressions * 100).toFixed(2) : 0
    }
  })
}
```

### POST /api/search-insights/sync

```typescript
import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function POST(request: Request) {
  const { days = 30 } = await request.json()

  // This would call the Python service or Cloud Run endpoint
  // For now, return a placeholder response

  // In production, this calls:
  // POST https://feedops-pipeline-xxx.run.app/sync-search-terms

  return NextResponse.json({
    success: true,
    message: `Syncing search terms for last ${days} days`,
    jobId: crypto.randomUUID()
  })
}
```

## UI Components

### QueryTable.tsx

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

interface Query {
  id: string
  query_text: string
  impressions: number
  clicks: number
  conversions: number
  ctr: number
  cvr: number
}

interface QueryTableProps {
  queries: Query[]
  ourKeywords?: string[] // Keywords we have in our titles
}

export function QueryTable({ queries, ourKeywords = [] }: QueryTableProps) {
  const normalizedKeywords = ourKeywords.map(k => k.toLowerCase())

  function hasKeyword(query: string): boolean {
    const words = query.toLowerCase().split(' ')
    return words.some(word => normalizedKeywords.includes(word))
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Search Query</TableHead>
          <TableHead className="text-right">Impressions</TableHead>
          <TableHead className="text-right">Clicks</TableHead>
          <TableHead className="text-right">CTR</TableHead>
          <TableHead className="text-right">Conv.</TableHead>
          <TableHead className="text-center">In Content?</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {queries.map((query) => {
          const covered = hasKeyword(query.query_text)
          return (
            <TableRow key={query.id}>
              <TableCell className="font-medium">
                {query.query_text}
              </TableCell>
              <TableCell className="text-right">
                {query.impressions.toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                {query.clicks.toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                {(query.ctr * 100).toFixed(2)}%
              </TableCell>
              <TableCell className="text-right">
                {query.conversions.toFixed(1)}
              </TableCell>
              <TableCell className="text-center">
                {covered ? (
                  <Badge variant="default">Yes</Badge>
                ) : (
                  <Badge variant="destructive">Gap</Badge>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
```

### GapAnalysis.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'

interface GapAnalysisProps {
  sku: string
  currentTitle: string
  topQueries: Array<{
    query_text: string
    impressions: number
    clicks: number
  }>
}

export function GapAnalysis({ sku, currentTitle, topQueries }: GapAnalysisProps) {
  const titleWords = new Set(currentTitle.toLowerCase().split(/\s+/))

  const gaps = topQueries.filter(q => {
    const queryWords = q.query_text.toLowerCase().split(/\s+/)
    return !queryWords.some(word => titleWords.has(word) && word.length > 3)
  })

  const covered = topQueries.length - gaps.length
  const coveragePercent = (covered / topQueries.length) * 100

  // Calculate opportunity score
  const gapImpressions = gaps.reduce((sum, g) => sum + g.impressions, 0)
  const totalImpressions = topQueries.reduce((sum, q) => sum + q.impressions, 0)
  const opportunityScore = Math.round((gapImpressions / totalImpressions) * 100)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Keyword Gap Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Coverage meter */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Query Coverage</span>
            <span>{coveragePercent.toFixed(0)}%</span>
          </div>
          <Progress value={coveragePercent} />
        </div>

        {/* Opportunity score */}
        <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-600" />
            <span className="font-medium text-yellow-800">
              {opportunityScore}% impression opportunity
            </span>
          </div>
          <p className="text-sm text-yellow-700 mt-1">
            {gapImpressions.toLocaleString()} impressions from uncovered queries
          </p>
        </div>

        {/* Gap list */}
        <div className="space-y-2">
          <h4 className="font-medium text-sm">Missing High-Volume Terms</h4>
          <ul className="space-y-1">
            {gaps.slice(0, 5).map((gap, i) => (
              <li key={i} className="flex justify-between text-sm">
                <span className="text-red-600">"{gap.query_text}"</span>
                <span className="text-muted-foreground">
                  {gap.impressions.toLocaleString()} imp
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Covered keywords */}
        <div className="space-y-2">
          <h4 className="font-medium text-sm flex items-center gap-1">
            <CheckCircle className="h-4 w-4 text-green-600" />
            Covered Terms
          </h4>
          <div className="flex flex-wrap gap-1">
            {topQueries
              .filter(q => !gaps.includes(q))
              .slice(0, 5)
              .map((q, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded"
                >
                  {q.query_text}
                </span>
              ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/search-insights/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { QueryTable } from '@/components/search-insights/QueryTable'
import { GapAnalysis } from '@/components/search-insights/GapAnalysis'
import { RefreshCw, Search, TrendingUp, Eye, MousePointer, Target } from 'lucide-react'

export default function SearchInsightsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [skuFilter, setSkuFilter] = useState('')

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    const url = skuFilter
      ? `/api/search-insights?sku=${skuFilter}`
      : '/api/search-insights'
    const res = await fetch(url)
    const json = await res.json()
    setData(json)
    setLoading(false)
  }

  async function syncData() {
    setSyncing(true)
    await fetch('/api/search-insights/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days: 30 })
    })
    setSyncing(false)
    // Refresh after sync
    setTimeout(fetchData, 3000)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Search Query Insights</h1>
          <p className="text-muted-foreground">
            Analyze actual search terms from Google Ads Shopping campaigns
          </p>
        </div>
        <div className="flex gap-2">
          <div className="flex gap-2">
            <Input
              placeholder="Filter by SKU..."
              value={skuFilter}
              onChange={(e) => setSkuFilter(e.target.value)}
              className="w-40"
            />
            <Button variant="outline" onClick={fetchData}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
          <Button onClick={syncData} disabled={syncing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            Sync Data
          </Button>
        </div>
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
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Total Queries</p>
                    <p className="text-2xl font-bold">{data.summary.totalQueries}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Total Impressions</p>
                    <p className="text-2xl font-bold">
                      {data.summary.totalImpressions.toLocaleString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <MousePointer className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Total Clicks</p>
                    <p className="text-2xl font-bold">
                      {data.summary.totalClicks.toLocaleString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Target className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Avg CTR</p>
                    <p className="text-2xl font-bold">{data.summary.avgCtr}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Content */}
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Query Table */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Top Search Queries</CardTitle>
              </CardHeader>
              <CardContent>
                <QueryTable queries={data.queries || []} />
              </CardContent>
            </Card>

            {/* Insights Panel */}
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Query Insights</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                    <p className="text-sm font-medium text-blue-800">
                      Top Converting Query
                    </p>
                    <p className="text-xs text-blue-700 mt-1">
                      "{data.queries?.[0]?.query_text || 'N/A'}"
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                    <p className="text-sm font-medium text-green-800">
                      Highest CTR Query
                    </p>
                    <p className="text-xs text-green-700 mt-1">
                      {data.queries?.length > 0
                        ? `"${[...data.queries].sort((a, b) => b.ctr - a.ctr)[0]?.query_text}"`
                        : 'N/A'}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Gap Analysis (shown when SKU filtered) */}
              {skuFilter && data.coverage && (
                <GapAnalysis
                  sku={skuFilter}
                  currentTitle="Sample Title" // Would come from generated_content
                  topQueries={data.queries?.slice(0, 20) || []}
                />
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
```

## Integration with Content Generation

Feed search query data into the content generation prompts:

```python
# In src/feedops/pipeline/prompt_builder.py

def build_prompt_with_search_data(sku_data: dict, search_terms: list) -> str:
    """
    Build content generation prompt enhanced with search query data.
    """
    # Extract top keywords from search terms
    top_queries = sorted(search_terms, key=lambda x: x['impressions'], reverse=True)[:10]
    keywords = [q['search_term'] for q in top_queries]

    prompt = f"""
Generate a product title and description for this bathroom fixture.

PRODUCT DATA:
{json.dumps(sku_data, indent=2)}

ACTUAL SEARCH QUERIES (from Google Ads - customers searched these terms):
{', '.join(keywords)}

REQUIREMENTS:
1. Include the most relevant search terms naturally in the title
2. The description should answer the intent behind these queries
3. Prioritize terms with higher search volume
4. Don't keyword-stuff - content must read naturally

The search data shows how real customers search for this product.
Match their language and intent.
"""
    return prompt
```

## Success Criteria

1. [ ] Search terms sync from Google Ads API
2. [ ] Query table displays with metrics
3. [ ] Gap analysis identifies uncovered keywords
4. [ ] SKU filtering works correctly
5. [ ] Search data feeds into content generation
6. [ ] Coverage tracking shows improvement over time
7. [ ] Manual sync button triggers data refresh

## Future Enhancements

- Auto-sync search terms weekly
- Trend analysis (rising/falling queries)
- Competitor query analysis (what queries trigger competitor ads?)
- Query clustering by intent
- Automated content suggestions based on gaps
