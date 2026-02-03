# Task: Enhance Dashboard Overview Page

## Objective

Improve the main dashboard overview page with real statistics, charts, and actionable insights.

## Current State

- Overview page exists at `dashboard/src/app/(dashboard)/page.tsx`
- Shows stats cards with data from `/api/stats`
- Recent activity and quick actions sections exist
- Charts section is placeholder

## Files to Modify/Create

1. `dashboard/src/app/(dashboard)/page.tsx` - Enhance with charts and insights
2. `dashboard/src/app/api/stats/route.ts` - Add more detailed statistics
3. `dashboard/src/components/dashboard/ApprovalChart.tsx` - NEW chart component
4. `dashboard/src/components/dashboard/PlatformBreakdown.tsx` - NEW component
5. `dashboard/src/components/dashboard/RecentActivity.tsx` - Enhance existing

## Requirements

### 1. Enhanced Statistics API (`/api/stats`)

Return more detailed stats:

```typescript
GET /api/stats

Response:
{
  overview: {
    totalSkus: 40,
    pendingReview: 15,
    approved: 22,
    rejected: 3,
    published: 1
  },
  byPlatform: {
    google: { total: 40, approved: 20, pending: 18, rejected: 2 },
    bing: { total: 38, approved: 18, pending: 19, rejected: 1 },
    shopify: { total: 40, approved: 22, pending: 15, rejected: 3 }
  },
  qualityScores: {
    average: 78,
    distribution: [
      { range: '90-100', count: 8 },
      { range: '80-89', count: 15 },
      { range: '70-79', count: 12 },
      { range: '60-69', count: 4 },
      { range: '<60', count: 1 }
    ]
  },
  recentActivity: [
    { type: 'approval', sku: '1051', action: 'approved', user: 'bobby@...', timestamp: '...' },
    { type: 'publish', sku: '1051', platform: 'google', timestamp: '...' },
    // ...
  ],
  trends: {
    approvalsThisWeek: 5,
    approvalsLastWeek: 3,
    publishesThisMonth: 1
  }
}
```

### 2. Approval Progress Chart

Visual representation of approval status:

```tsx
<ApprovalChart
  data={{
    approved: 22,
    pending: 15,
    rejected: 3,
  }}
/>
```

Options:

- Donut/pie chart (using Recharts)
- Progress bar segments
- Stacked bar

### 3. Platform Breakdown

Show approval status per platform:

```tsx
<PlatformBreakdown platforms={stats.byPlatform} />
```

Display as:

- Three columns (Google, Bing, Shopify)
- Mini progress bars for each
- Click to filter review queue by platform

### 4. Quality Score Distribution

Histogram or bar chart showing score distribution:

```tsx
<QualityDistribution data={stats.qualityScores.distribution} />
```

### 5. Recent Activity Feed

Enhanced activity feed with:

- Icons for different action types
- Relative timestamps ("2 hours ago")
- Links to relevant SKUs
- Filter by activity type

### 6. Actionable Insights

Smart suggestions based on data:

```tsx
<InsightsCard>
  <Insight
    type="action"
    message="15 SKUs are ready for review"
    action={{ label: "Review Now", href: "/review" }}
  />
  <Insight
    type="warning"
    message="3 SKUs have low quality scores (<70)"
    action={{ label: "View", href: "/review?filter=low-score" }}
  />
  <Insight
    type="success"
    message="SKU 1051 published 2 days ago - check performance"
    action={{ label: "View Performance", href: "/performance" }}
  />
</InsightsCard>
```

### 7. Quick Actions Enhancement

Make quick action buttons functional:

- "Review Next" → Goes to first pending SKU
- "Create Batch" → Opens batch creation modal
- "View Performance" → Goes to performance page

## Chart Library

Use Recharts (already common in Next.js projects):

```bash
cd dashboard && npm install recharts
```

Example usage:

```tsx
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

const COLORS = ['#22c55e', '#f59e0b', '#ef4444']

<ResponsiveContainer width="100%" height={200}>
  <PieChart>
    <Pie
      data={[
        { name: 'Approved', value: 22 },
        { name: 'Pending', value: 15 },
        { name: 'Rejected', value: 3 }
      ]}
      innerRadius={60}
      outerRadius={80}
      dataKey="value"
    >
      {data.map((entry, index) => (
        <Cell key={index} fill={COLORS[index]} />
      ))}
    </Pie>
  </PieChart>
</ResponsiveContainer>
```

## Success Criteria

1. Dashboard shows real statistics from Supabase
2. Approval progress is visualized (chart or progress bar)
3. Platform breakdown shows per-platform status
4. Quality score distribution is visible
5. Recent activity updates in real-time or near-real-time
6. Insights provide actionable next steps
7. Quick actions work correctly
8. Responsive design for mobile

## Notes

- Consider caching stats to avoid expensive queries on every load
- Use React Query or SWR for data fetching with auto-refresh
- Charts should be responsive
- Consider skeleton loaders for better UX
