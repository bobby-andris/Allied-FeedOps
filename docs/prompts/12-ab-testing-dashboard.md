# Task: Implement A/B Testing & Performance Attribution Dashboard

## Objective

Build a performance attribution dashboard that tracks baseline metrics before optimization, compares post-optimization performance, and proves ROI of the FeedOps content optimization program.

## Problem Statement

We generate optimized content but have no systematic way to prove it works. Without before/after attribution, we can't:
- Justify expanding the optimization program
- Identify what's working vs what's not
- Calculate actual ROI from optimizations
- Make data-driven decisions about content strategy

## Solution Overview

Build an A/B testing and attribution dashboard that:
1. Captures baseline metrics before optimization (CTR, CVR, ROAS)
2. Organizes SKUs into cohorts for controlled testing
3. Tracks post-optimization performance
4. Calculates lift/decline per SKU and aggregate
5. Visualizes performance comparison with statistical significance

## Prerequisites

- Google Ads API access (existing: `src/feedops/integrations/google_ads_performance.py`)
- Performance baselines captured before optimization
- Supabase tables: `performance_baselines`, `performance_snapshots`

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/ab-testing/page.tsx` - Main A/B testing page
- `dashboard/src/app/api/ab-testing/route.ts` - Cohort and performance API
- `dashboard/src/app/api/ab-testing/cohorts/route.ts` - Cohort management
- `dashboard/src/components/ab-testing/CohortCard.tsx` - Display cohort summary
- `dashboard/src/components/ab-testing/PerformanceComparison.tsx` - Before/after comparison
- `dashboard/src/components/ab-testing/LiftChart.tsx` - Visualize lift metrics
- `dashboard/src/components/ab-testing/StatisticalSignificance.tsx` - Show confidence levels

### Database
- `supabase/migrations/007_ab_testing_cohorts.sql`

## Database Schema

```sql
-- Optimization cohorts (groups of SKUs optimized together)
CREATE TABLE optimization_cohorts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name text NOT NULL,
  description text,
  optimization_type text DEFAULT 'title_description', -- 'title_only', 'description_only', 'title_description', 'images'
  start_date date NOT NULL, -- when optimization was published
  baseline_end_date date, -- last day of baseline period
  status text DEFAULT 'active', -- 'active', 'completed', 'paused'
  target_metric text DEFAULT 'ctr', -- primary metric to optimize
  created_at timestamptz DEFAULT now(),
  created_by text
);

-- SKUs in each cohort with their performance data
CREATE TABLE cohort_skus (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  cohort_id uuid REFERENCES optimization_cohorts(id) ON DELETE CASCADE,
  master_sku text NOT NULL,
  -- Baseline metrics (30 days before optimization)
  baseline_impressions integer DEFAULT 0,
  baseline_clicks integer DEFAULT 0,
  baseline_conversions numeric DEFAULT 0,
  baseline_revenue numeric DEFAULT 0,
  baseline_cost numeric DEFAULT 0,
  baseline_ctr numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_impressions > 0
    THEN baseline_clicks::numeric / baseline_impressions
    ELSE 0 END
  ) STORED,
  baseline_cvr numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_clicks > 0
    THEN baseline_conversions / baseline_clicks
    ELSE 0 END
  ) STORED,
  baseline_roas numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_cost > 0
    THEN baseline_revenue / baseline_cost
    ELSE 0 END
  ) STORED,
  -- Post-optimization metrics
  post_impressions integer DEFAULT 0,
  post_clicks integer DEFAULT 0,
  post_conversions numeric DEFAULT 0,
  post_revenue numeric DEFAULT 0,
  post_cost numeric DEFAULT 0,
  post_ctr numeric GENERATED ALWAYS AS (
    CASE WHEN post_impressions > 0
    THEN post_clicks::numeric / post_impressions
    ELSE 0 END
  ) STORED,
  post_cvr numeric GENERATED ALWAYS AS (
    CASE WHEN post_clicks > 0
    THEN post_conversions / post_clicks
    ELSE 0 END
  ) STORED,
  post_roas numeric GENERATED ALWAYS AS (
    CASE WHEN post_cost > 0
    THEN post_revenue / post_cost
    ELSE 0 END
  ) STORED,
  -- Calculated lifts
  ctr_lift_pct numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_ctr > 0
    THEN ((post_ctr - baseline_ctr) / baseline_ctr) * 100
    ELSE 0 END
  ) STORED,
  cvr_lift_pct numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_cvr > 0
    THEN ((post_cvr - baseline_cvr) / baseline_cvr) * 100
    ELSE 0 END
  ) STORED,
  roas_lift_pct numeric GENERATED ALWAYS AS (
    CASE WHEN baseline_roas > 0
    THEN ((post_roas - baseline_roas) / baseline_roas) * 100
    ELSE 0 END
  ) STORED,
  -- Metadata
  last_updated timestamptz DEFAULT now(),
  UNIQUE(cohort_id, master_sku)
);

-- Indexes
CREATE INDEX idx_cohort_skus_cohort ON cohort_skus(cohort_id);
CREATE INDEX idx_cohort_skus_sku ON cohort_skus(master_sku);
CREATE INDEX idx_optimization_cohorts_status ON optimization_cohorts(status);
```

## Statistical Significance Calculation

```typescript
// dashboard/src/lib/statistics.ts

/**
 * Calculate z-score for CTR comparison
 * Uses two-proportion z-test
 */
export function calculateCtrZScore(
  baselineClicks: number,
  baselineImpressions: number,
  postClicks: number,
  postImpressions: number
): number {
  const p1 = baselineClicks / baselineImpressions
  const p2 = postClicks / postImpressions
  const pPooled = (baselineClicks + postClicks) / (baselineImpressions + postImpressions)

  const se = Math.sqrt(
    pPooled * (1 - pPooled) * (1 / baselineImpressions + 1 / postImpressions)
  )

  if (se === 0) return 0
  return (p2 - p1) / se
}

/**
 * Convert z-score to confidence level
 */
export function zScoreToConfidence(zScore: number): number {
  // Approximate conversion using error function
  const absZ = Math.abs(zScore)

  if (absZ >= 2.576) return 99
  if (absZ >= 1.96) return 95
  if (absZ >= 1.645) return 90
  if (absZ >= 1.282) return 80
  return Math.round(50 + absZ * 20) // Linear approximation for lower values
}

/**
 * Determine if result is statistically significant
 */
export function isSignificant(
  zScore: number,
  confidenceThreshold: number = 95
): boolean {
  const confidence = zScoreToConfidence(Math.abs(zScore))
  return confidence >= confidenceThreshold
}

/**
 * Calculate aggregate lift with confidence interval
 */
export function calculateAggregateLift(
  cohortData: Array<{
    baselineClicks: number
    baselineImpressions: number
    postClicks: number
    postImpressions: number
  }>
): {
  lift: number
  confidence: number
  isSignificant: boolean
  direction: 'up' | 'down' | 'flat'
} {
  const totalBaseline = cohortData.reduce((sum, d) => ({
    clicks: sum.clicks + d.baselineClicks,
    impressions: sum.impressions + d.baselineImpressions
  }), { clicks: 0, impressions: 0 })

  const totalPost = cohortData.reduce((sum, d) => ({
    clicks: sum.clicks + d.postClicks,
    impressions: sum.impressions + d.postImpressions
  }), { clicks: 0, impressions: 0 })

  const baselineCtr = totalBaseline.clicks / totalBaseline.impressions
  const postCtr = totalPost.clicks / totalPost.impressions
  const lift = ((postCtr - baselineCtr) / baselineCtr) * 100

  const zScore = calculateCtrZScore(
    totalBaseline.clicks,
    totalBaseline.impressions,
    totalPost.clicks,
    totalPost.impressions
  )

  const confidence = zScoreToConfidence(Math.abs(zScore))

  return {
    lift,
    confidence,
    isSignificant: confidence >= 95,
    direction: lift > 1 ? 'up' : lift < -1 ? 'down' : 'flat'
  }
}
```

## API Implementation

### GET /api/ab-testing

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { calculateAggregateLift } from '@/lib/statistics'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const cohortId = searchParams.get('cohort')

  const supabase = await createClient()

  if (cohortId) {
    // Get specific cohort details
    const { data: cohort } = await supabase
      .from('optimization_cohorts')
      .select('*')
      .eq('id', cohortId)
      .single()

    const { data: skus } = await supabase
      .from('cohort_skus')
      .select('*')
      .eq('cohort_id', cohortId)
      .order('ctr_lift_pct', { ascending: false })

    // Calculate aggregate metrics
    const aggregateLift = calculateAggregateLift(
      (skus || []).map(s => ({
        baselineClicks: s.baseline_clicks,
        baselineImpressions: s.baseline_impressions,
        postClicks: s.post_clicks,
        postImpressions: s.post_impressions
      }))
    )

    return NextResponse.json({
      cohort,
      skus,
      aggregate: aggregateLift
    })
  }

  // Get all cohorts with summary
  const { data: cohorts } = await supabase
    .from('optimization_cohorts')
    .select(`
      *,
      cohort_skus (
        master_sku,
        baseline_impressions,
        baseline_clicks,
        post_impressions,
        post_clicks,
        ctr_lift_pct
      )
    `)
    .order('created_at', { ascending: false })

  // Calculate summary for each cohort
  const cohortsWithSummary = (cohorts || []).map(cohort => {
    const skus = cohort.cohort_skus || []
    const aggregateLift = calculateAggregateLift(
      skus.map((s: any) => ({
        baselineClicks: s.baseline_clicks,
        baselineImpressions: s.baseline_impressions,
        postClicks: s.post_clicks,
        postImpressions: s.post_impressions
      }))
    )

    return {
      ...cohort,
      skuCount: skus.length,
      aggregateLift: aggregateLift.lift,
      confidence: aggregateLift.confidence,
      isSignificant: aggregateLift.isSignificant,
      direction: aggregateLift.direction
    }
  })

  return NextResponse.json({ cohorts: cohortsWithSummary })
}
```

### POST /api/ab-testing/cohorts

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const {
    name,
    description,
    optimizationType,
    skus,
    baselineEndDate
  } = await request.json()

  const supabase = await createClient()

  // Create cohort
  const { data: cohort, error: cohortError } = await supabase
    .from('optimization_cohorts')
    .insert({
      name,
      description,
      optimization_type: optimizationType,
      start_date: new Date().toISOString().split('T')[0],
      baseline_end_date: baselineEndDate,
      status: 'active'
    })
    .select()
    .single()

  if (cohortError) {
    return NextResponse.json({ error: cohortError.message }, { status: 400 })
  }

  // Add SKUs with baseline metrics
  const skuInserts = []
  for (const sku of skus) {
    // Get baseline from performance_baselines
    const { data: baseline } = await supabase
      .from('performance_baselines')
      .select('*')
      .eq('master_sku', sku)
      .eq('platform', 'google')
      .single()

    skuInserts.push({
      cohort_id: cohort.id,
      master_sku: sku,
      baseline_impressions: baseline?.impressions || 0,
      baseline_clicks: baseline?.clicks || 0,
      baseline_conversions: baseline?.conversions || 0,
      baseline_revenue: baseline?.revenue || 0,
      baseline_cost: baseline?.cost || 0
    })
  }

  const { error: skuError } = await supabase
    .from('cohort_skus')
    .insert(skuInserts)

  if (skuError) {
    return NextResponse.json({ error: skuError.message }, { status: 400 })
  }

  return NextResponse.json({
    success: true,
    cohort,
    skusAdded: skuInserts.length
  })
}
```

### POST /api/ab-testing/sync

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { cohortId } = await request.json()

  const supabase = await createClient()

  // Get cohort and SKUs
  const { data: cohort } = await supabase
    .from('optimization_cohorts')
    .select('*')
    .eq('id', cohortId)
    .single()

  if (!cohort) {
    return NextResponse.json({ error: 'Cohort not found' }, { status: 404 })
  }

  const { data: skus } = await supabase
    .from('cohort_skus')
    .select('master_sku')
    .eq('cohort_id', cohortId)

  // Fetch current performance from snapshots
  // In production, this would call Google Ads API
  for (const sku of skus || []) {
    const { data: snapshot } = await supabase
      .from('performance_snapshots')
      .select('*')
      .eq('master_sku', sku.master_sku)
      .eq('platform', 'google')
      .gte('snapshot_date', cohort.start_date)
      .order('snapshot_date', { ascending: false })
      .limit(1)
      .single()

    if (snapshot) {
      await supabase
        .from('cohort_skus')
        .update({
          post_impressions: snapshot.impressions,
          post_clicks: snapshot.clicks,
          post_conversions: snapshot.conversions,
          post_revenue: snapshot.conversions * 50, // Placeholder - would use actual revenue
          post_cost: snapshot.cost,
          last_updated: new Date().toISOString()
        })
        .eq('cohort_id', cohortId)
        .eq('master_sku', sku.master_sku)
    }
  }

  return NextResponse.json({ success: true, synced: skus?.length || 0 })
}
```

## UI Components

### CohortCard.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TrendingUp, TrendingDown, Minus, ArrowRight } from 'lucide-react'
import Link from 'next/link'

interface CohortCardProps {
  cohort: {
    id: string
    name: string
    description: string
    status: string
    skuCount: number
    aggregateLift: number
    confidence: number
    isSignificant: boolean
    direction: 'up' | 'down' | 'flat'
    start_date: string
  }
}

export function CohortCard({ cohort }: CohortCardProps) {
  const TrendIcon = cohort.direction === 'up'
    ? TrendingUp
    : cohort.direction === 'down'
    ? TrendingDown
    : Minus

  const liftColor = cohort.direction === 'up'
    ? 'text-green-600'
    : cohort.direction === 'down'
    ? 'text-red-600'
    : 'text-gray-600'

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-lg">{cohort.name}</CardTitle>
            <p className="text-sm text-muted-foreground">{cohort.description}</p>
          </div>
          <Badge variant={cohort.status === 'active' ? 'default' : 'secondary'}>
            {cohort.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Lift Metric */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendIcon className={`h-5 w-5 ${liftColor}`} />
            <span className={`text-2xl font-bold ${liftColor}`}>
              {cohort.aggregateLift > 0 ? '+' : ''}
              {cohort.aggregateLift.toFixed(1)}%
            </span>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium">
              {cohort.confidence}% confidence
            </p>
            {cohort.isSignificant ? (
              <Badge variant="default" className="mt-1">Significant</Badge>
            ) : (
              <Badge variant="outline" className="mt-1">Not Significant</Badge>
            )}
          </div>
        </div>

        {/* Meta */}
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{cohort.skuCount} SKUs</span>
          <span>Started {new Date(cohort.start_date).toLocaleDateString()}</span>
        </div>

        {/* Action */}
        <Button variant="outline" className="w-full" asChild>
          <Link href={`/ab-testing/${cohort.id}`}>
            View Details <ArrowRight className="h-4 w-4 ml-2" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
```

### PerformanceComparison.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface SkuPerformance {
  master_sku: string
  baseline_impressions: number
  baseline_clicks: number
  baseline_ctr: number
  baseline_cvr: number
  post_impressions: number
  post_clicks: number
  post_ctr: number
  post_cvr: number
  ctr_lift_pct: number
  cvr_lift_pct: number
}

interface PerformanceComparisonProps {
  skus: SkuPerformance[]
}

export function PerformanceComparison({ skus }: PerformanceComparisonProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>SKU Performance Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead className="text-right">Baseline CTR</TableHead>
              <TableHead className="text-right">Current CTR</TableHead>
              <TableHead className="text-right">CTR Lift</TableHead>
              <TableHead className="text-right">Baseline CVR</TableHead>
              <TableHead className="text-right">Current CVR</TableHead>
              <TableHead className="text-right">CVR Lift</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {skus.map((sku) => (
              <TableRow key={sku.master_sku}>
                <TableCell className="font-medium">{sku.master_sku}</TableCell>
                <TableCell className="text-right">
                  {(sku.baseline_ctr * 100).toFixed(2)}%
                </TableCell>
                <TableCell className="text-right">
                  {(sku.post_ctr * 100).toFixed(2)}%
                </TableCell>
                <TableCell className="text-right">
                  <LiftBadge lift={sku.ctr_lift_pct} />
                </TableCell>
                <TableCell className="text-right">
                  {(sku.baseline_cvr * 100).toFixed(2)}%
                </TableCell>
                <TableCell className="text-right">
                  {(sku.post_cvr * 100).toFixed(2)}%
                </TableCell>
                <TableCell className="text-right">
                  <LiftBadge lift={sku.cvr_lift_pct} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function LiftBadge({ lift }: { lift: number }) {
  const isUp = lift > 1
  const isDown = lift < -1
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus
  const color = isUp ? 'text-green-600' : isDown ? 'text-red-600' : 'text-gray-600'

  return (
    <span className={`flex items-center justify-end gap-1 ${color}`}>
      <Icon className="h-3 w-3" />
      {lift > 0 ? '+' : ''}{lift.toFixed(1)}%
    </span>
  )
}
```

### LiftChart.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts'

interface LiftChartProps {
  data: Array<{
    sku: string
    ctrLift: number
    cvrLift: number
  }>
}

export function LiftChart({ data }: LiftChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>CTR Lift by SKU</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" domain={['dataMin - 5', 'dataMax + 5']} />
            <YAxis type="category" dataKey="sku" width={60} />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}%`, 'CTR Lift']}
            />
            <ReferenceLine x={0} stroke="#666" />
            <Bar
              dataKey="ctrLift"
              fill="#10b981"
              // Conditional coloring
              label={({ value }) => value > 0 ? value.toFixed(1) : ''}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/ab-testing/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CohortCard } from '@/components/ab-testing/CohortCard'
import { Plus, RefreshCw, TrendingUp, Target, BarChart3 } from 'lucide-react'

export default function ABTestingPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    const res = await fetch('/api/ab-testing')
    const json = await res.json()
    setData(json)
    setLoading(false)
  }

  // Calculate overall program metrics
  const programMetrics = {
    totalCohorts: data?.cohorts?.length || 0,
    activeCohorts: data?.cohorts?.filter((c: any) => c.status === 'active').length || 0,
    totalSkus: data?.cohorts?.reduce((sum: number, c: any) => sum + c.skuCount, 0) || 0,
    avgLift: data?.cohorts?.length > 0
      ? data.cohorts.reduce((sum: number, c: any) => sum + c.aggregateLift, 0) / data.cohorts.length
      : 0,
    significantWins: data?.cohorts?.filter((c: any) =>
      c.isSignificant && c.direction === 'up'
    ).length || 0
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">A/B Testing & Attribution</h1>
          <p className="text-muted-foreground">
            Track optimization performance and prove ROI
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Cohort
          </Button>
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          {/* Program Summary */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Target className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Active Cohorts</p>
                    <p className="text-2xl font-bold">
                      {programMetrics.activeCohorts} / {programMetrics.totalCohorts}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">SKUs Tested</p>
                    <p className="text-2xl font-bold">{programMetrics.totalSkus}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <div>
                    <p className="text-sm text-muted-foreground">Avg CTR Lift</p>
                    <p className="text-2xl font-bold text-green-600">
                      {programMetrics.avgLift > 0 ? '+' : ''}
                      {programMetrics.avgLift.toFixed(1)}%
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
                    <p className="text-sm text-muted-foreground">Significant Wins</p>
                    <p className="text-2xl font-bold text-blue-600">
                      {programMetrics.significantWins}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* ROI Calculator */}
          {programMetrics.avgLift > 0 && (
            <Card className="bg-green-50 border-green-200">
              <CardContent className="pt-6">
                <h3 className="font-medium text-green-800">Estimated Program ROI</h3>
                <p className="text-sm text-green-700 mt-1">
                  Based on {programMetrics.avgLift.toFixed(1)}% average CTR lift across{' '}
                  {programMetrics.totalSkus} SKUs:
                </p>
                <div className="mt-3 grid gap-4 md:grid-cols-3">
                  <div>
                    <p className="text-2xl font-bold text-green-800">
                      +{Math.round(programMetrics.avgLift * programMetrics.totalSkus * 10)}
                    </p>
                    <p className="text-sm text-green-700">Additional clicks/month (est.)</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-800">
                      ${Math.round(programMetrics.avgLift * programMetrics.totalSkus * 5)}
                    </p>
                    <p className="text-sm text-green-700">Incremental revenue/month (est.)</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-800">
                      {Math.round(programMetrics.avgLift * 12)}%
                    </p>
                    <p className="text-sm text-green-700">Annual efficiency gain (est.)</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Cohort List */}
          <div>
            <h2 className="text-lg font-semibold mb-4">Optimization Cohorts</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {(data?.cohorts || []).map((cohort: any) => (
                <CohortCard key={cohort.id} cohort={cohort} />
              ))}
              {(data?.cohorts || []).length === 0 && (
                <Card className="col-span-full">
                  <CardContent className="pt-6 text-center">
                    <p className="text-muted-foreground">
                      No cohorts yet. Create your first cohort to start tracking performance.
                    </p>
                    <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Cohort
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

## Success Criteria

1. [ ] Cohort creation with baseline metrics capture
2. [ ] Post-optimization metrics sync from Google Ads
3. [ ] Lift calculation with statistical significance
4. [ ] Aggregate program ROI estimation
5. [ ] Per-SKU performance comparison table
6. [ ] Visual lift charts
7. [ ] Confidence level indicators

## Future Enhancements

- Control group tracking (non-optimized SKUs for comparison)
- Revenue attribution at SKU level
- Seasonal adjustment factors
- Auto-cohort creation on publish
- Export reports for stakeholders
- Multi-platform lift comparison (Google vs Bing)
