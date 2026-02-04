# Task: Implement Search Query Insights Dashboard

## Objective

Build a search query insights dashboard that pulls actual search terms from Google Ads, identifies high-value queries, and feeds this data into content generation to ensure titles/descriptions match real search behavior.

## Problem Statement

We guess what people search for. We don't use ACTUAL search query data from Google Ads to inform content generation, leading to:
- Titles optimized for assumed keywords, not real queries
- Missing high-intent search terms that drive conversions
- Content that doesn't match how customers actually search
- No visibility into query-to-content alignment

## Critical: Platform-Specific Content Architecture

**IMPORTANT**: Understand how content is served on each platform:

### Google Shopping & Bing Shopping
- **Ads are served at the VARIANT level** (GMC offer ID)
- Each finish variant has its own title and description
- GMC offer ID format: `shopify_us_{shopify_product_id}_{shopify_variant_id}`
- Example: `shopify_us_4545063682180_32128479625348` = SKU 1051, Polished Chrome
- Search queries should be tracked **per variant** because:
  - "antique brass towel bar" may only trigger AB variants
  - "polished chrome bathroom accessories" may only trigger PC variants
  - Finish-specific searches reveal optimization opportunities

### Shopify Storefront
- **Product pages show the MASTER SKU** with all 28 finishes selectable
- Example: https://www.alliedbrass.com/products/p-1 shows all finishes
- Only the master description matters for Shopify SEO
- Variant-level descriptions are NOT used on the storefront

### Dashboard Implication
For Google/Bing views, show:
1. **Aggregate view**: All queries across all variants of a master SKU (identify base search terms)
2. **Variant-specific view**: Queries for a specific finish (identify finish-specific patterns)

For Shopify views, show:
- Only master SKU-level insights (variant breakdown not relevant)

## Solution Overview

Build a search query insights system that:
1. Pulls search terms from Google Ads Shopping campaigns **with variant-level tracking**
2. Maps GMC offer IDs to master SKU + finish variant
3. Provides both aggregate (master SKU) and granular (variant) views
4. Identifies gaps in variant-specific content
5. Feeds query data into content generation prompts

## Prerequisites

- Google Ads API credentials configured
- Google Ads customer ID: 6253381786
- Existing integration: `src/feedops/integrations/google_ads_performance.py`
- `variant_index` table with GMC offer ID mappings

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/search-insights/page.tsx` - Main search insights page
- `dashboard/src/app/api/search-insights/route.ts` - API for fetching search data
- `dashboard/src/components/search-insights/QueryTable.tsx` - Display queries with metrics
- `dashboard/src/components/search-insights/VariantSelector.tsx` - Toggle between aggregate/variant view
- `dashboard/src/components/search-insights/GapAnalysis.tsx` - Show missing keywords
- `dashboard/src/components/search-insights/FinishInsights.tsx` - Finish-specific query patterns

### Python Integration
- `src/feedops/integrations/google_ads_search_terms.py` - Search term extraction with variant mapping

### Database
- `supabase/migrations/009_search_query_insights.sql`

## Database Schema

```sql
-- Store search query data from Google Ads at VARIANT level
CREATE TABLE search_queries (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  query_text text NOT NULL,
  campaign_id text,
  -- Variant-level identification
  gmc_offer_id text, -- e.g., 'shopify_us_4545063682180_32128479625348'
  master_sku text,
  finish text, -- e.g., 'Polished Chrome'
  finish_code text, -- e.g., 'PC'
  shopify_variant_id text,
  -- Metrics
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
  -- Time tracking
  period_start date NOT NULL,
  period_end date NOT NULL,
  fetched_at timestamptz DEFAULT now(),
  UNIQUE(query_text, gmc_offer_id, period_start, period_end)
);

-- Aggregated view: queries per master SKU (across all variants)
CREATE TABLE search_queries_by_master_sku (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  query_text text NOT NULL,
  -- Aggregated metrics across all variants
  total_impressions integer DEFAULT 0,
  total_clicks integer DEFAULT 0,
  total_conversions numeric DEFAULT 0,
  variant_count integer DEFAULT 1, -- how many variants triggered this query
  top_variant_finish text, -- which finish got most impressions for this query
  period_start date NOT NULL,
  period_end date NOT NULL,
  updated_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, query_text, period_start, period_end)
);

-- Track keyword coverage at VARIANT level for Google/Bing
CREATE TABLE keyword_coverage_variant (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  finish text NOT NULL,
  finish_code text,
  gmc_offer_id text,
  keyword text NOT NULL,
  in_title boolean DEFAULT false,
  in_description boolean DEFAULT false,
  query_volume integer DEFAULT 0,
  updated_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, finish, keyword)
);

-- Track keyword coverage at MASTER SKU level for Shopify
CREATE TABLE keyword_coverage_master (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  keyword text NOT NULL,
  in_title boolean DEFAULT false,
  in_description boolean DEFAULT false,
  query_volume integer DEFAULT 0,
  updated_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, keyword)
);

-- Finish-specific search patterns (e.g., "antique brass" queries)
CREATE TABLE finish_search_patterns (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  finish text NOT NULL,
  finish_code text NOT NULL,
  pattern_keyword text NOT NULL, -- e.g., 'antique brass', 'chrome', 'gold'
  total_impressions integer DEFAULT 0,
  total_clicks integer DEFAULT 0,
  category text, -- e.g., 'towel bars', 'grab bars'
  updated_at timestamptz DEFAULT now(),
  UNIQUE(finish_code, pattern_keyword, category)
);

-- Indexes
CREATE INDEX idx_search_queries_gmc ON search_queries(gmc_offer_id);
CREATE INDEX idx_search_queries_master_sku ON search_queries(master_sku);
CREATE INDEX idx_search_queries_finish ON search_queries(finish_code);
CREATE INDEX idx_search_queries_impressions ON search_queries(impressions DESC);
CREATE INDEX idx_search_queries_by_master_sku ON search_queries_by_master_sku(master_sku);
CREATE INDEX idx_keyword_coverage_variant_sku ON keyword_coverage_variant(master_sku, finish);
```

## Google Ads Search Terms Query

### GAQL Query for Search Terms (with Variant Tracking)

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
LIMIT 1000
```

**Key**: `segments.product_item_id` contains the GMC offer ID which maps to a specific variant.

### Python Implementation

```python
# src/feedops/integrations/google_ads_search_terms.py

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from feedops.db import get_supabase_client

class SearchTermsClient:
    """Fetches search term data from Google Ads Shopping campaigns with variant-level tracking."""

    def __init__(self):
        self.customer_id = os.getenv('GOOGLE_ADS_CUSTOMER_ID', '6253381786')
        self.client = GoogleAdsClient.load_from_env()
        self.supabase = get_supabase_client()
        self._variant_cache = {}  # Cache GMC ID -> variant info

    def parse_gmc_offer_id(self, offer_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse GMC offer ID to extract Shopify product and variant IDs.

        Format: shopify_us_{product_id}_{variant_id}
        Example: shopify_us_4545063682180_32128479625348

        Returns: (shopify_product_id, shopify_variant_id)
        """
        if not offer_id:
            return None, None

        match = re.match(r'shopify_us_(\d+)_(\d+)', offer_id)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def get_variant_info(self, gmc_offer_id: str) -> Dict:
        """
        Look up variant info from variant_index table.

        Returns dict with: master_sku, finish, finish_code, shopify_variant_id
        """
        if gmc_offer_id in self._variant_cache:
            return self._variant_cache[gmc_offer_id]

        result = self.supabase.table('variant_index') \
            .select('master_sku, finish, finish_code, shopify_variant_id') \
            .eq('gmc_offer_id', gmc_offer_id) \
            .limit(1) \
            .execute()

        if result.data:
            info = result.data[0]
            self._variant_cache[gmc_offer_id] = info
            return info

        # Fallback: try to find by shopify_variant_id
        _, variant_id = self.parse_gmc_offer_id(gmc_offer_id)
        if variant_id:
            result = self.supabase.table('variant_index') \
                .select('master_sku, finish, finish_code, shopify_variant_id') \
                .eq('shopify_variant_id', variant_id) \
                .limit(1) \
                .execute()

            if result.data:
                info = result.data[0]
                self._variant_cache[gmc_offer_id] = info
                return info

        return {'master_sku': None, 'finish': None, 'finish_code': None, 'shopify_variant_id': None}

    def fetch_search_terms(
        self,
        days: int = 30,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch search terms from Shopping campaigns WITH variant-level tracking.

        Returns list of dicts with:
        - search_term: The actual query text
        - impressions, clicks, conversions, cost_micros: Metrics
        - gmc_offer_id: The GMC offer ID (variant identifier)
        - master_sku, finish, finish_code: Variant info from variant_index
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
                    gmc_offer_id = row.segments.product_item_id or None
                    variant_info = self.get_variant_info(gmc_offer_id) if gmc_offer_id else {}

                    results.append({
                        'search_term': row.search_term_view.search_term,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': row.metrics.conversions,
                        'cost_micros': row.metrics.cost_micros,
                        'gmc_offer_id': gmc_offer_id,
                        'master_sku': variant_info.get('master_sku'),
                        'finish': variant_info.get('finish'),
                        'finish_code': variant_info.get('finish_code'),
                        'shopify_variant_id': variant_info.get('shopify_variant_id')
                    })

        except GoogleAdsException as e:
            print(f"Google Ads API error: {e}")
            raise

        return results

    def get_terms_for_master_sku(
        self,
        master_sku: str,
        shopify_product_id: str,
        days: int = 30
    ) -> Dict:
        """
        Get search terms for all variants of a master SKU.

        Returns:
        - aggregate: All queries combined across variants
        - by_variant: Queries broken down by finish variant
        """
        ga_service = self.client.get_service("GoogleAdsService")

        # Match any variant of this product
        offer_pattern = f"shopify_us_{shopify_product_id}_%"

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                segments.product_item_id
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.advertising_channel_type = 'SHOPPING'
                AND segments.product_item_id LIKE '{offer_pattern}'
            ORDER BY metrics.impressions DESC
            LIMIT 500
        """

        aggregate = {}  # query_text -> aggregated metrics
        by_variant = {}  # finish_code -> {query_text -> metrics}

        try:
            response = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query
            )

            for batch in response:
                for row in batch.results:
                    search_term = row.search_term_view.search_term
                    gmc_offer_id = row.segments.product_item_id
                    variant_info = self.get_variant_info(gmc_offer_id)
                    finish_code = variant_info.get('finish_code', 'UNKNOWN')

                    # Aggregate across all variants
                    if search_term not in aggregate:
                        aggregate[search_term] = {
                            'search_term': search_term,
                            'impressions': 0,
                            'clicks': 0,
                            'conversions': 0,
                            'variants': set()
                        }
                    aggregate[search_term]['impressions'] += row.metrics.impressions
                    aggregate[search_term]['clicks'] += row.metrics.clicks
                    aggregate[search_term]['conversions'] += row.metrics.conversions
                    aggregate[search_term]['variants'].add(finish_code)

                    # Track by variant
                    if finish_code not in by_variant:
                        by_variant[finish_code] = {}
                    if search_term not in by_variant[finish_code]:
                        by_variant[finish_code][search_term] = {
                            'search_term': search_term,
                            'impressions': 0,
                            'clicks': 0,
                            'conversions': 0,
                            'finish': variant_info.get('finish'),
                            'finish_code': finish_code
                        }
                    by_variant[finish_code][search_term]['impressions'] += row.metrics.impressions
                    by_variant[finish_code][search_term]['clicks'] += row.metrics.clicks
                    by_variant[finish_code][search_term]['conversions'] += row.metrics.conversions

        except GoogleAdsException as e:
            print(f"Google Ads API error: {e}")
            raise

        # Convert aggregate variants set to count
        for query in aggregate.values():
            query['variant_count'] = len(query['variants'])
            del query['variants']

        # Sort by impressions
        aggregate_list = sorted(aggregate.values(), key=lambda x: x['impressions'], reverse=True)

        by_variant_sorted = {}
        for finish_code, queries in by_variant.items():
            by_variant_sorted[finish_code] = sorted(
                queries.values(),
                key=lambda x: x['impressions'],
                reverse=True
            )

        return {
            'aggregate': aggregate_list,
            'by_variant': by_variant_sorted
        }

    def get_terms_for_specific_variant(
        self,
        gmc_offer_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get search terms for a SPECIFIC variant only.

        Use this to see what queries trigger a specific finish variant.
        """
        ga_service = self.client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.advertising_channel_type = 'SHOPPING'
                AND segments.product_item_id = '{gmc_offer_id}'
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

    def identify_finish_specific_queries(
        self,
        master_sku_data: Dict
    ) -> Dict[str, List[str]]:
        """
        Identify queries that are specific to certain finishes.

        Example:
        - "antique brass towel bar" -> likely only triggers AB variants
        - "chrome bathroom accessories" -> likely only triggers PC/SCH variants

        Returns: {finish_code: [queries that primarily trigger this finish]}
        """
        by_variant = master_sku_data.get('by_variant', {})
        aggregate = {q['search_term']: q for q in master_sku_data.get('aggregate', [])}

        finish_specific = {}

        for finish_code, queries in by_variant.items():
            finish_specific[finish_code] = []

            for query_data in queries:
                search_term = query_data['search_term']
                variant_impressions = query_data['impressions']

                # Check if this query is disproportionately associated with this finish
                total_impressions = aggregate.get(search_term, {}).get('impressions', 0)

                if total_impressions > 0:
                    share = variant_impressions / total_impressions
                    # If this finish gets >60% of impressions for this query, it's finish-specific
                    if share > 0.6:
                        finish_specific[finish_code].append({
                            'query': search_term,
                            'share': share,
                            'impressions': variant_impressions
                        })

        return finish_specific
```

## API Implementation

### GET /api/search-insights

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const masterSku = searchParams.get('sku')
  const finishCode = searchParams.get('finish') // Optional: filter to specific variant
  const platform = searchParams.get('platform') || 'google' // 'google', 'bing', 'shopify'
  const viewType = searchParams.get('view') || 'aggregate' // 'aggregate' or 'variant'

  const supabase = await createClient()

  // For Shopify, only show master SKU level data
  if (platform === 'shopify') {
    const { data: queries } = await supabase
      .from('search_queries_by_master_sku')
      .select('*')
      .eq('master_sku', masterSku)
      .order('total_impressions', { ascending: false })
      .limit(100)

    return NextResponse.json({
      platform: 'shopify',
      viewType: 'master',
      queries,
      note: 'Shopify uses master SKU descriptions - variant breakdown not applicable'
    })
  }

  // For Google/Bing, support both aggregate and variant views
  if (viewType === 'aggregate' && masterSku) {
    // Aggregate view: all variants combined
    const { data: queries } = await supabase
      .from('search_queries_by_master_sku')
      .select('*')
      .eq('master_sku', masterSku)
      .order('total_impressions', { ascending: false })
      .limit(100)

    // Get variant breakdown summary
    const { data: variantSummary } = await supabase
      .from('search_queries')
      .select('finish_code, finish')
      .eq('master_sku', masterSku)
      .limit(1000)

    // Count unique finishes
    const finishCounts = variantSummary?.reduce((acc, q) => {
      if (q.finish_code) {
        acc[q.finish_code] = (acc[q.finish_code] || 0) + 1
      }
      return acc
    }, {} as Record<string, number>)

    return NextResponse.json({
      platform,
      viewType: 'aggregate',
      masterSku,
      queries,
      variantBreakdown: finishCounts,
      note: 'Aggregate view shows all queries across all finish variants'
    })
  }

  if (viewType === 'variant' && masterSku) {
    // Variant-specific view
    let query = supabase
      .from('search_queries')
      .select('*')
      .eq('master_sku', masterSku)
      .order('impressions', { ascending: false })
      .limit(200)

    if (finishCode) {
      query = query.eq('finish_code', finishCode)
    }

    const { data: queries } = await query

    // Group by finish for UI
    const byFinish = queries?.reduce((acc, q) => {
      const finish = q.finish_code || 'UNKNOWN'
      if (!acc[finish]) {
        acc[finish] = {
          finish: q.finish,
          finish_code: q.finish_code,
          queries: [],
          totalImpressions: 0,
          totalClicks: 0
        }
      }
      acc[finish].queries.push(q)
      acc[finish].totalImpressions += q.impressions
      acc[finish].totalClicks += q.clicks
      return acc
    }, {} as Record<string, any>)

    return NextResponse.json({
      platform,
      viewType: 'variant',
      masterSku,
      selectedFinish: finishCode,
      byFinish,
      note: finishCode
        ? `Showing queries that triggered the ${finishCode} variant specifically`
        : 'Showing queries broken down by finish variant'
    })
  }

  // Default: top queries across all SKUs
  const { data: queries } = await supabase
    .from('search_queries')
    .select('*')
    .order('impressions', { ascending: false })
    .limit(100)

  return NextResponse.json({
    platform,
    viewType: 'all',
    queries
  })
}
```

## UI Components

### VariantSelector.tsx

```tsx
'use client'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

interface VariantSelectorProps {
  platform: 'google' | 'bing' | 'shopify'
  viewType: 'aggregate' | 'variant'
  selectedFinish: string | null
  availableFinishes: Array<{ finish: string; finish_code: string; count: number }>
  onViewTypeChange: (view: 'aggregate' | 'variant') => void
  onFinishChange: (finishCode: string | null) => void
}

export function VariantSelector({
  platform,
  viewType,
  selectedFinish,
  availableFinishes,
  onViewTypeChange,
  onFinishChange
}: VariantSelectorProps) {
  // Shopify doesn't need variant selection
  if (platform === 'shopify') {
    return (
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
        <p className="text-sm text-blue-800">
          <strong>Shopify:</strong> Product pages show the master description with all 28 finishes selectable.
          Variant-level breakdown is not applicable.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
        <p className="text-sm text-amber-800">
          <strong>Google/Bing:</strong> Ads are served at the variant level. Each finish has its own
          title/description in the GMC feed.
        </p>
      </div>

      <div className="flex gap-4 items-center">
        <Tabs value={viewType} onValueChange={(v) => onViewTypeChange(v as any)}>
          <TabsList>
            <TabsTrigger value="aggregate">
              All Variants (Aggregate)
            </TabsTrigger>
            <TabsTrigger value="variant">
              By Finish Variant
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {viewType === 'variant' && (
          <Select
            value={selectedFinish || 'all'}
            onValueChange={(v) => onFinishChange(v === 'all' ? null : v)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All finishes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All finishes</SelectItem>
              {availableFinishes.map((f) => (
                <SelectItem key={f.finish_code} value={f.finish_code}>
                  {f.finish} ({f.count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}
```

### FinishInsights.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, Search } from 'lucide-react'

interface FinishData {
  finish: string
  finish_code: string
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
}

export function FinishInsights({ byFinish }: FinishInsightsProps) {
  const finishes = Object.values(byFinish).sort(
    (a, b) => b.totalImpressions - a.totalImpressions
  )

  return (
    <div className="space-y-4">
      <h3 className="font-semibold flex items-center gap-2">
        <TrendingUp className="h-5 w-5" />
        Queries by Finish Variant
      </h3>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {finishes.slice(0, 6).map((finish) => (
          <Card key={finish.finish_code}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span>{finish.finish}</span>
                <Badge variant="outline">{finish.finish_code}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-muted-foreground mb-2">
                {finish.totalImpressions.toLocaleString()} impressions •{' '}
                {finish.totalClicks.toLocaleString()} clicks
              </div>

              <div className="space-y-1">
                <p className="text-xs font-medium">Top queries:</p>
                {finish.queries.slice(0, 3).map((q, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="truncate flex-1 mr-2">"{q.query_text}"</span>
                    <span className="text-muted-foreground">
                      {q.impressions.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>

              {/* Identify finish-specific keywords */}
              {finish.queries.some(q =>
                q.query_text.toLowerCase().includes(finish.finish.toLowerCase().split(' ')[0])
              ) && (
                <div className="mt-2 p-2 rounded bg-green-50 text-xs text-green-700">
                  <Search className="h-3 w-3 inline mr-1" />
                  Finish-specific queries detected
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

### QueryTable.tsx (Updated)

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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface Query {
  id: string
  query_text: string
  impressions: number
  clicks: number
  conversions: number
  ctr: number
  cvr: number
  // Variant info (for Google/Bing)
  finish?: string
  finish_code?: string
  variant_count?: number // How many variants this query triggered
}

interface QueryTableProps {
  queries: Query[]
  viewType: 'aggregate' | 'variant' | 'shopify'
  ourKeywords?: string[]
  variantTitle?: string // The variant-specific title to check against
}

export function QueryTable({
  queries,
  viewType,
  ourKeywords = [],
  variantTitle
}: QueryTableProps) {
  const normalizedKeywords = ourKeywords.map(k => k.toLowerCase())
  const titleWords = variantTitle
    ? new Set(variantTitle.toLowerCase().split(/\s+/))
    : new Set()

  function hasKeyword(query: string): boolean {
    const words = query.toLowerCase().split(' ')
    if (variantTitle) {
      return words.some(word => titleWords.has(word) && word.length > 3)
    }
    return words.some(word => normalizedKeywords.includes(word))
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Search Query</TableHead>
          {viewType === 'variant' && <TableHead>Finish</TableHead>}
          {viewType === 'aggregate' && <TableHead>Variants</TableHead>}
          <TableHead className="text-right">Impressions</TableHead>
          <TableHead className="text-right">Clicks</TableHead>
          <TableHead className="text-right">CTR</TableHead>
          <TableHead className="text-center">In Title?</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {queries.map((query, idx) => {
          const covered = hasKeyword(query.query_text)
          return (
            <TableRow key={query.id || idx}>
              <TableCell className="font-medium max-w-xs truncate">
                {query.query_text}
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
                      This query triggered {query.variant_count || 1} different finish variants
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
              )}
              <TableCell className="text-right">
                {query.impressions.toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                {query.clicks.toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                {((query.ctr || 0) * 100).toFixed(2)}%
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

## Main Page (Updated)

```tsx
// dashboard/src/app/(dashboard)/search-insights/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { QueryTable } from '@/components/search-insights/QueryTable'
import { VariantSelector } from '@/components/search-insights/VariantSelector'
import { FinishInsights } from '@/components/search-insights/FinishInsights'
import { RefreshCw, Search, TrendingUp, Eye, MousePointer, Target } from 'lucide-react'

export default function SearchInsightsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [skuFilter, setSkuFilter] = useState('')
  const [platform, setPlatform] = useState<'google' | 'bing' | 'shopify'>('google')
  const [viewType, setViewType] = useState<'aggregate' | 'variant'>('aggregate')
  const [selectedFinish, setSelectedFinish] = useState<string | null>(null)

  useEffect(() => {
    if (skuFilter) {
      fetchData()
    }
  }, [skuFilter, platform, viewType, selectedFinish])

  async function fetchData() {
    setLoading(true)
    const params = new URLSearchParams({
      platform,
      view: viewType,
      ...(skuFilter && { sku: skuFilter }),
      ...(selectedFinish && { finish: selectedFinish })
    })

    const res = await fetch(`/api/search-insights?${params}`)
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
    setTimeout(fetchData, 3000)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Search Query Insights</h1>
          <p className="text-muted-foreground">
            Analyze search terms by platform and variant
          </p>
        </div>
        <Button onClick={syncData} disabled={syncing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
          Sync Data
        </Button>
      </div>

      {/* Platform & SKU Selection */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex gap-4 items-center">
            <Tabs value={platform} onValueChange={(v) => setPlatform(v as any)}>
              <TabsList>
                <TabsTrigger value="google">Google Shopping</TabsTrigger>
                <TabsTrigger value="bing">Bing Shopping</TabsTrigger>
                <TabsTrigger value="shopify">Shopify</TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex gap-2">
              <Input
                placeholder="Enter Master SKU..."
                value={skuFilter}
                onChange={(e) => setSkuFilter(e.target.value)}
                className="w-40"
              />
              <Button onClick={fetchData} disabled={!skuFilter}>
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
            </div>
          </div>

          {/* Platform-specific view selector */}
          {skuFilter && (
            <VariantSelector
              platform={platform}
              viewType={viewType}
              selectedFinish={selectedFinish}
              availableFinishes={data?.variantBreakdown
                ? Object.entries(data.variantBreakdown).map(([code, count]) => ({
                    finish_code: code,
                    finish: code, // Would lookup full name
                    count: count as number
                  }))
                : []
              }
              onViewTypeChange={setViewType}
              onFinishChange={setSelectedFinish}
            />
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {loading ? (
        <div>Loading...</div>
      ) : data ? (
        <div className="space-y-6">
          {/* Info banner */}
          {data.note && (
            <div className="p-3 rounded-lg bg-muted">
              <p className="text-sm text-muted-foreground">{data.note}</p>
            </div>
          )}

          {/* Variant insights (Google/Bing only) */}
          {platform !== 'shopify' && viewType === 'variant' && data.byFinish && (
            <FinishInsights byFinish={data.byFinish} />
          )}

          {/* Query table */}
          <Card>
            <CardHeader>
              <CardTitle>
                {viewType === 'aggregate'
                  ? 'Top Search Queries (All Variants)'
                  : selectedFinish
                  ? `Queries for ${selectedFinish} Variant`
                  : 'Queries by Variant'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <QueryTable
                queries={data.queries || []}
                viewType={platform === 'shopify' ? 'shopify' : viewType}
              />
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            Enter a Master SKU to view search query insights
          </CardContent>
        </Card>
      )}
    </div>
  )
}
```

## Integration with Content Generation

When generating variant-specific content for Google/Bing:

```python
def build_variant_prompt_with_search_data(
    sku_data: dict,
    finish: str,
    aggregate_queries: list,
    variant_specific_queries: list
) -> str:
    """
    Build content generation prompt for a SPECIFIC VARIANT.

    Uses both aggregate queries (common to all variants) and
    variant-specific queries (unique to this finish).
    """
    # Combine queries, prioritizing variant-specific ones
    variant_keywords = [q['search_term'] for q in variant_specific_queries[:5]]
    base_keywords = [q['search_term'] for q in aggregate_queries[:5]]

    prompt = f"""
Generate a product title and description for this bathroom fixture variant.

PRODUCT DATA:
{json.dumps(sku_data, indent=2)}

FINISH VARIANT: {finish}

IMPORTANT: This content is for the Google Merchant Center feed.
Each finish variant has its own title and description in GMC.

SEARCH QUERIES - VARIANT SPECIFIC (people searching for this finish):
{', '.join(variant_keywords)}

SEARCH QUERIES - BASE TERMS (common across all finishes):
{', '.join(base_keywords)}

REQUIREMENTS:
1. The title MUST include the finish name naturally
2. Include variant-specific search terms when relevant
3. Include base terms that apply to all variants
4. The description should address why someone would choose this specific finish
5. Don't keyword-stuff - content must read naturally

Example good title for Antique Brass variant:
"24-Inch Antique Brass Towel Bar - Solid Brass Wall Mount Bathroom Fixture"

NOT:
"24-Inch Towel Bar - Solid Brass" (missing finish in title)
"""
    return prompt
```

## Success Criteria

1. [ ] Search terms tracked at variant level (GMC offer ID)
2. [ ] Aggregate view shows all queries across variants
3. [ ] Variant view shows finish-specific queries
4. [ ] Platform selector shows appropriate views (Shopify = master only)
5. [ ] Finish-specific search patterns identified
6. [ ] Gap analysis works at variant level for Google/Bing
7. [ ] Integration with content generation includes variant context

## Future Enhancements

- Compare query patterns between finishes (e.g., "Does Antique Brass get more 'vintage' searches?")
- Identify underperforming variants based on query data
- Suggest finish-specific keyword additions
- Track query trends by variant over time
- Auto-generate variant-specific title variations
