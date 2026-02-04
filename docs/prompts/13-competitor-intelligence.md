# Task: Implement Competitor Intelligence Panel

## Objective

Build a competitor intelligence panel that scrapes competitor product titles and descriptions, extracts successful patterns, and provides actionable insights to improve Allied Brass content.

## Problem Statement

We write content in a vacuum without knowing:
- What competitors are doing for similar products
- What patterns drive clicks in our category
- How our content compares to top-performing listings
- What keywords competitors use that we're missing

## Solution Overview

Build a competitor intelligence system that:
1. Scrapes competitor listings for similar products (Amazon, Wayfair, Home Depot, Build.com)
2. Stores competitor data in Supabase for analysis
3. Extracts patterns from successful listings
4. Shows side-by-side comparison with our content
5. Suggests specific improvements based on competitor success

## Prerequisites

- Apify MCP is configured ✅ (user confirmed)
- Apify account with scraper actors available
- Supabase tables for storing competitor data

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/competitors/page.tsx` - Main competitors page
- `dashboard/src/app/api/competitors/route.ts` - API for fetching/managing competitor data
- `dashboard/src/app/api/competitors/scrape/route.ts` - Trigger scraping jobs
- `dashboard/src/components/competitors/CompetitorCard.tsx` - Display single competitor
- `dashboard/src/components/competitors/PatternAnalysis.tsx` - Show extracted patterns
- `dashboard/src/components/competitors/ComparisonView.tsx` - Side-by-side comparison

### Python Integration
- `src/feedops/integrations/apify_scraper.py` - Enhanced Apify integration

### Database
- `supabase/migrations/008_competitor_intelligence.sql`

## Database Schema

```sql
-- Competitor listings storage
CREATE TABLE competitor_listings (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source text NOT NULL, -- 'amazon', 'wayfair', 'homedepot', 'build'
  source_url text,
  product_category text NOT NULL, -- e.g., 'towel bars', 'grab bars'
  title text NOT NULL,
  description text,
  price numeric,
  rating numeric,
  review_count integer,
  brand text,
  position integer, -- rank in search results
  scraped_at timestamptz DEFAULT now(),
  keywords_extracted text[], -- extracted keywords
  UNIQUE(source, source_url)
);

-- Pattern analysis results
CREATE TABLE competitor_patterns (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  category text NOT NULL,
  pattern_type text NOT NULL, -- 'title_structure', 'keyword', 'benefit', 'trust_signal'
  pattern_value text NOT NULL,
  frequency integer DEFAULT 1,
  avg_position numeric, -- average search position of listings with this pattern
  sources text[], -- which competitors use this
  updated_at timestamptz DEFAULT now(),
  UNIQUE(category, pattern_type, pattern_value)
);

-- Link competitor data to our SKUs for comparison
CREATE TABLE sku_competitor_mapping (
  master_sku text NOT NULL,
  competitor_listing_id uuid REFERENCES competitor_listings(id),
  similarity_score numeric, -- how similar is this competitor product
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (master_sku, competitor_listing_id)
);

-- Indexes
CREATE INDEX idx_competitor_listings_category ON competitor_listings(product_category);
CREATE INDEX idx_competitor_patterns_category ON competitor_patterns(category);
```

## Apify Scraper Configuration

### Amazon Scraper Actor

```javascript
// Apify actor input for Amazon product search
{
  "searchTerms": ["brass towel bar bathroom", "brass grab bar", "brass soap dispenser"],
  "maxResults": 20,
  "includeDescription": true,
  "proxyConfiguration": {
    "useApifyProxy": true
  }
}
```

### Wayfair Scraper Actor

```javascript
{
  "startUrls": [
    "https://www.wayfair.com/home-improvement/sb0/towel-bars-c215273.html",
    "https://www.wayfair.com/home-improvement/sb0/grab-bars-c215269.html"
  ],
  "maxProducts": 20
}
```

## API Implementation

### GET /api/competitors

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const category = searchParams.get('category')
  const sku = searchParams.get('sku')

  const supabase = await createClient()

  // Get competitor listings for category
  let query = supabase
    .from('competitor_listings')
    .select('*')
    .order('position', { ascending: true })
    .limit(20)

  if (category) {
    query = query.eq('product_category', category)
  }

  const { data: listings } = await query

  // Get patterns for category
  const { data: patterns } = await supabase
    .from('competitor_patterns')
    .select('*')
    .eq('category', category || 'all')
    .order('frequency', { ascending: false })
    .limit(20)

  // If SKU provided, get our content for comparison
  let ourContent = null
  if (sku) {
    const { data } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', sku)
      .eq('is_current', true)

    ourContent = data
  }

  return NextResponse.json({
    listings,
    patterns,
    ourContent,
    lastScraped: listings?.[0]?.scraped_at
  })
}
```

### POST /api/competitors/scrape

```typescript
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { category, sources } = await request.json()

  // Trigger Apify actors via MCP
  // This would integrate with the Apify MCP server

  const jobs = []

  for (const source of sources) {
    // Queue scraping job
    jobs.push({
      source,
      category,
      status: 'queued'
    })
  }

  return NextResponse.json({
    success: true,
    jobs,
    message: `Scraping ${sources.length} sources for "${category}"`
  })
}
```

## Pattern Extraction Logic

```typescript
interface ExtractedPattern {
  type: 'title_structure' | 'keyword' | 'benefit' | 'trust_signal'
  value: string
  frequency: number
}

function extractPatterns(listings: CompetitorListing[]): ExtractedPattern[] {
  const patterns: Map<string, ExtractedPattern> = new Map()

  for (const listing of listings) {
    // Title structure patterns
    const titleParts = listing.title.split(/[-,|]/).map(p => p.trim())

    // Check for common structures
    if (titleParts[0].match(/^\d+/)) {
      addPattern(patterns, 'title_structure', 'dimension_first')
    }
    if (listing.title.toLowerCase().includes('modern') ||
        listing.title.toLowerCase().includes('traditional')) {
      addPattern(patterns, 'title_structure', 'style_included')
    }

    // Keyword extraction
    const keywords = extractKeywords(listing.title + ' ' + listing.description)
    for (const kw of keywords) {
      addPattern(patterns, 'keyword', kw)
    }

    // Benefit patterns
    if (listing.description?.toLowerCase().includes('easy install')) {
      addPattern(patterns, 'benefit', 'easy_installation')
    }
    if (listing.description?.toLowerCase().includes('rust')) {
      addPattern(patterns, 'benefit', 'rust_resistant')
    }

    // Trust signals
    if (listing.description?.toLowerCase().includes('warranty')) {
      addPattern(patterns, 'trust_signal', 'warranty_mentioned')
    }
    if (listing.description?.toLowerCase().includes('made in')) {
      addPattern(patterns, 'trust_signal', 'origin_mentioned')
    }
  }

  return Array.from(patterns.values())
    .sort((a, b) => b.frequency - a.frequency)
}

function addPattern(
  patterns: Map<string, ExtractedPattern>,
  type: string,
  value: string
) {
  const key = `${type}:${value}`
  const existing = patterns.get(key)
  if (existing) {
    existing.frequency++
  } else {
    patterns.set(key, { type, value, frequency: 1 })
  }
}
```

## UI Components

### CompetitorCard.tsx

```tsx
interface CompetitorCardProps {
  listing: {
    source: string
    title: string
    description: string
    price: number
    rating: number
    review_count: number
    brand: string
    position: number
  }
}

export function CompetitorCard({ listing }: CompetitorCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <Badge variant="outline">{listing.source}</Badge>
          <span className="text-xs text-muted-foreground">
            #{listing.position}
          </span>
        </div>
        <CardTitle className="text-sm">{listing.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted-foreground line-clamp-3">
          {listing.description}
        </p>
        <div className="flex justify-between text-xs">
          <span>${listing.price}</span>
          <span>★ {listing.rating} ({listing.review_count})</span>
        </div>
      </CardContent>
    </Card>
  )
}
```

### PatternAnalysis.tsx

```tsx
interface PatternAnalysisProps {
  patterns: Array<{
    pattern_type: string
    pattern_value: string
    frequency: number
    sources: string[]
  }>
  ourContent?: {
    title: string
    description: string
  }
}

export function PatternAnalysis({ patterns, ourContent }: PatternAnalysisProps) {
  // Group patterns by type
  const grouped = patterns.reduce((acc, p) => {
    if (!acc[p.pattern_type]) acc[p.pattern_type] = []
    acc[p.pattern_type].push(p)
    return acc
  }, {} as Record<string, typeof patterns>)

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([type, pats]) => (
        <div key={type}>
          <h4 className="font-medium text-sm mb-2 capitalize">
            {type.replace('_', ' ')}
          </h4>
          <div className="space-y-1">
            {pats.slice(0, 5).map((p, i) => {
              const hasIt = ourContent && checkIfPresent(ourContent, p)
              return (
                <div
                  key={i}
                  className="flex justify-between text-xs"
                >
                  <span className={hasIt ? 'text-green-600' : ''}>
                    {hasIt ? '✓' : '○'} {p.pattern_value}
                  </span>
                  <span className="text-muted-foreground">
                    {p.frequency} listings
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
```

### ComparisonView.tsx

```tsx
export function ComparisonView({
  ourContent,
  topCompetitor
}: {
  ourContent: { title: string; description: string }
  topCompetitor: { title: string; description: string; source: string }
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Allied Brass</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="font-medium text-sm">{ourContent.title}</p>
          <p className="text-xs text-muted-foreground mt-2">
            {ourContent.description?.slice(0, 200)}...
          </p>
          <div className="mt-2 text-xs">
            <Badge variant="outline">{ourContent.title.length} chars</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            Top Competitor ({topCompetitor.source})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="font-medium text-sm">{topCompetitor.title}</p>
          <p className="text-xs text-muted-foreground mt-2">
            {topCompetitor.description?.slice(0, 200)}...
          </p>
          <div className="mt-2 text-xs">
            <Badge variant="outline">{topCompetitor.title.length} chars</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/competitors/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { CompetitorCard } from '@/components/competitors/CompetitorCard'
import { PatternAnalysis } from '@/components/competitors/PatternAnalysis'
import { ComparisonView } from '@/components/competitors/ComparisonView'
import { RefreshCw } from 'lucide-react'

const CATEGORIES = [
  'towel bars',
  'grab bars',
  'soap dispensers',
  'toilet paper holders',
  'robe hooks',
  'shower caddies',
  'mirrors'
]

export default function CompetitorsPage() {
  const [category, setCategory] = useState('towel bars')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [scraping, setScraping] = useState(false)

  useEffect(() => {
    fetchData()
  }, [category])

  async function fetchData() {
    setLoading(true)
    const res = await fetch(`/api/competitors?category=${encodeURIComponent(category)}`)
    const json = await res.json()
    setData(json)
    setLoading(false)
  }

  async function triggerScrape() {
    setScraping(true)
    await fetch('/api/competitors/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category,
        sources: ['amazon', 'wayfair', 'homedepot']
      })
    })
    setScraping(false)
    // Refresh data after a delay
    setTimeout(fetchData, 5000)
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Competitor Intelligence</h1>
          <p className="text-muted-foreground">
            Analyze competitor listings and extract winning patterns
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map(cat => (
                <SelectItem key={cat} value={cat}>{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={triggerScrape} disabled={scraping}>
            <RefreshCw className={`h-4 w-4 mr-2 ${scraping ? 'animate-spin' : ''}`} />
            Refresh Data
          </Button>
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : data ? (
        <div className="grid grid-cols-3 gap-6">
          {/* Pattern Analysis */}
          <Card className="col-span-1">
            <CardHeader>
              <CardTitle>Winning Patterns</CardTitle>
            </CardHeader>
            <CardContent>
              <PatternAnalysis patterns={data.patterns || []} />
            </CardContent>
          </Card>

          {/* Competitor Listings */}
          <div className="col-span-2 space-y-4">
            <h3 className="font-medium">Top Competitor Listings</h3>
            <div className="grid grid-cols-2 gap-4">
              {(data.listings || []).slice(0, 6).map((listing: any) => (
                <CompetitorCard key={listing.id} listing={listing} />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
```

## Success Criteria

1. [ ] Scraping works for at least 2 competitor sources
2. [ ] Competitor data stored in Supabase
3. [ ] Pattern extraction identifies at least 5 pattern types
4. [ ] Side-by-side comparison view works
5. [ ] Actionable suggestions generated from patterns
6. [ ] Data refreshes on demand
7. [ ] Category filtering works

## Future Enhancements

- Auto-refresh competitor data weekly
- Track pattern changes over time
- Link patterns to our performance data (do pattern-aligned titles perform better?)
- AI-powered pattern analysis for more nuanced insights
