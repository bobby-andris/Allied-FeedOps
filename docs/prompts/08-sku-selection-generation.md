# Task: Implement Strategic SKU Selection & Content Generation

## Objective
Build a feature that allows users to strategically select SKUs for optimization based on Google Ads performance data, then generate titles, descriptions, and images for those SKUs.

## Business Strategy

### The Problem with Random Selection
- **Best sellers are too risky**: If we optimize top performers and the new content underperforms, we tank revenue
- **Worst performers won't show signal**: Products that don't sell regardless of content won't prove optimization works
- **We need a controlled experiment**: Select SKUs that will demonstrate impact while managing risk

### The Strategic Selection Approach

Based on the pilot batch strategy (see `dashboard_data/lifestyle-eval/reports/pilot-selection-report-detailed.md`):

| Tier | Criteria | Purpose | % of Batch |
|------|----------|---------|------------|
| **Tier 1** | High conversion rate, low-medium traffic | Risk-managed winners - prove we don't hurt good converters | 20% |
| **Tier 2** | Mid-pack performance (median CTR, median CVR) | Primary test bed - largest sample for statistical significance | 50% |
| **Tier 3** | High traffic, low conversion | Largest upside potential - most to gain | 20% |
| **Fill** | Category diversity | Ensure coverage across product types | 10% |

### Exclusion Rules
- **Top 5% revenue SKUs**: Never auto-select (e.g., CL-55, FR-23, TD-23)
- **Already optimized**: Skip SKUs that already have approved content
- **Out of stock**: Skip products with no inventory
- **Discontinued**: Skip products marked as discontinued

## Files to Create

1. `dashboard/src/app/api/sku-selection/route.ts` - SKU scoring and selection API
2. `dashboard/src/app/api/sku-selection/generate/route.ts` - Trigger generation for selected SKUs
3. `dashboard/src/app/(dashboard)/generate/page.tsx` - NEW page for SKU selection UI
4. `dashboard/src/components/generate/SkuSelectionWizard.tsx` - Multi-step wizard
5. `dashboard/src/components/generate/SkuPerformanceTable.tsx` - Preview table
6. `dashboard/src/components/generate/TierDistributionChart.tsx` - Visual tier breakdown
7. `dashboard/src/lib/sku-scoring.ts` - Scoring algorithm

## Requirements

### 1. SKU Performance Data API (`/api/sku-selection`)

Fetch and score all master SKUs based on Google Ads data.

```typescript
GET /api/sku-selection?count=20&excludeOptimized=true

Response:
{
  recommended: [
    {
      master_sku: "1052",
      product_name: "Soap Dispensers",
      category: "Bath Accessories",
      tier: "tier2",
      score: 72,
      metrics: {
        impressions_30d: 15000,
        clicks_30d: 320,
        ctr: 2.13,
        conversions_30d: 12,
        cvr: 3.75,
        revenue_30d: 890,
        cost_30d: 125
      },
      variant_count: 8,
      already_optimized: false
    },
    // ... more SKUs
  ],
  distribution: {
    tier1: 4,
    tier2: 10,
    tier3: 4,
    fill: 2
  },
  excluded: {
    top_revenue: ["CL-55", "FR-23"],
    already_optimized: ["1051"],
    out_of_stock: []
  },
  total_eligible: 156
}
```

### 2. Scoring Algorithm (`/lib/sku-scoring.ts`)

```typescript
interface SkuMetrics {
  master_sku: string
  impressions: number
  clicks: number
  conversions: number
  revenue: number
  cost: number
}

interface ScoredSku extends SkuMetrics {
  ctr: number
  cvr: number
  roas: number
  tier: 'tier1' | 'tier2' | 'tier3' | 'fill'
  score: number // 0-100, higher = better candidate for optimization
}

function scoreSkus(skus: SkuMetrics[]): ScoredSku[] {
  // 1. Calculate derived metrics
  const withMetrics = skus.map(sku => ({
    ...sku,
    ctr: sku.clicks / sku.impressions * 100,
    cvr: sku.conversions / sku.clicks * 100,
    roas: sku.revenue / sku.cost
  }))

  // 2. Calculate percentiles
  const ctrPercentiles = calculatePercentiles(withMetrics.map(s => s.ctr))
  const cvrPercentiles = calculatePercentiles(withMetrics.map(s => s.cvr))
  const revenuePercentiles = calculatePercentiles(withMetrics.map(s => s.revenue))
  const impressionPercentiles = calculatePercentiles(withMetrics.map(s => s.impressions))

  // 3. Assign tiers and scores
  return withMetrics.map(sku => {
    const ctrPct = getPercentile(sku.ctr, ctrPercentiles)
    const cvrPct = getPercentile(sku.cvr, cvrPercentiles)
    const revPct = getPercentile(sku.revenue, revenuePercentiles)
    const impPct = getPercentile(sku.impressions, impressionPercentiles)

    // Tier assignment
    let tier: Tier
    if (revPct >= 95) {
      tier = 'excluded' // Top 5% revenue - too risky
    } else if (cvrPct >= 70 && impPct <= 50) {
      tier = 'tier1' // High conversion, low traffic
    } else if (impPct >= 70 && cvrPct <= 30) {
      tier = 'tier3' // High traffic, low conversion
    } else {
      tier = 'tier2' // Mid-pack
    }

    // Score: Higher for better optimization candidates
    // Ideal: Medium traffic, medium conversion, room for improvement
    const score = calculateOptimizationScore(sku, ctrPct, cvrPct, impPct)

    return { ...sku, tier, score }
  })
}

function calculateOptimizationScore(sku, ctrPct, cvrPct, impPct): number {
  // Penalize extremes, reward middle ground
  const trafficScore = 100 - Math.abs(impPct - 50) * 2 // Best at 50th percentile
  const conversionScore = 100 - Math.abs(cvrPct - 50) * 2
  
  // Bonus for having enough data (statistical significance)
  const dataBonus = Math.min(sku.clicks / 100, 20) // Up to 20 points for 100+ clicks
  
  // Slight bonus for higher impressions (more visible impact)
  const visibilityBonus = Math.min(impPct / 5, 10) // Up to 10 points
  
  return Math.round((trafficScore + conversionScore) / 2 + dataBonus + visibilityBonus)
}
```

### 3. Google Ads Data Aggregation

Query Google Ads to get performance by master SKU (aggregate all variants):

```sql
SELECT
  -- Extract master SKU from offer ID pattern: shopify_us_{product_id}_{variant_id}
  segments.product_item_id,
  SUM(metrics.impressions) as impressions,
  SUM(metrics.clicks) as clicks,
  SUM(metrics.conversions) as conversions,
  SUM(metrics.conversions_value) as revenue,
  SUM(metrics.cost_micros) / 1000000 as cost
FROM shopping_performance_view
WHERE segments.date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
GROUP BY segments.product_item_id
HAVING impressions > 100  -- Minimum data threshold
```

Then map `product_item_id` → `master_sku` using `variant_index` table.

### 4. SKU Selection Page (`/generate`)

**Step 1: Configure**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Generate Optimized Content</CardTitle>
    <CardDescription>
      Select SKUs for title, description, and image generation
    </CardDescription>
  </CardHeader>
  <CardContent>
    <div className="space-y-4">
      <div>
        <Label>Number of SKUs to optimize</Label>
        <Input 
          type="number" 
          min={5} 
          max={50} 
          value={count}
          onChange={e => setCount(e.target.value)}
        />
        <p className="text-sm text-muted-foreground mt-1">
          Recommended: 20-40 SKUs for statistically significant results
        </p>
      </div>
      
      <div className="flex items-center gap-2">
        <Checkbox 
          checked={excludeOptimized}
          onCheckedChange={setExcludeOptimized}
        />
        <Label>Exclude already optimized SKUs</Label>
      </div>

      <Button onClick={fetchRecommendations}>
        Get Recommendations
      </Button>
    </div>
  </CardContent>
</Card>
```

**Step 2: Review Selection**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Recommended SKUs</CardTitle>
    <CardDescription>
      Based on Google Ads performance data (last 30 days)
    </CardDescription>
  </CardHeader>
  <CardContent>
    {/* Tier distribution visualization */}
    <TierDistributionChart distribution={data.distribution} />
    
    {/* Selection table */}
    <SkuPerformanceTable 
      skus={data.recommended}
      selected={selectedSkus}
      onSelectionChange={setSelectedSkus}
    />
    
    {/* Excluded SKUs info */}
    <Collapsible>
      <CollapsibleTrigger>
        Excluded SKUs ({data.excluded.top_revenue.length + data.excluded.already_optimized.length})
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="text-sm text-muted-foreground">
          <p><strong>Top revenue (protected):</strong> {data.excluded.top_revenue.join(', ')}</p>
          <p><strong>Already optimized:</strong> {data.excluded.already_optimized.join(', ')}</p>
        </div>
      </CollapsibleContent>
    </Collapsible>
  </CardContent>
</Card>
```

**Step 3: Confirm & Generate**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Confirm Generation</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <Stat label="SKUs Selected" value={selectedSkus.length} />
        <Stat label="Est. Variants" value={totalVariants} />
        <Stat label="Est. Time" value={`${selectedSkus.length * 2} min`} />
      </div>
      
      <div className="space-y-2">
        <Label>Content to generate</Label>
        <div className="flex gap-4">
          <Checkbox checked={generateTitles} onChange={setGenerateTitles} label="Titles" />
          <Checkbox checked={generateDescriptions} onChange={setGenerateDescriptions} label="Descriptions" />
          <Checkbox checked={generateImages} onChange={setGenerateImages} label="Lifestyle Images" />
        </div>
      </div>
      
      <div className="space-y-2">
        <Label>Platforms</Label>
        <div className="flex gap-4">
          <Checkbox checked={platforms.google} label="Google" />
          <Checkbox checked={platforms.bing} label="Bing" />
          <Checkbox checked={platforms.shopify} label="Shopify" />
        </div>
      </div>
      
      <Button 
        onClick={startGeneration}
        disabled={selectedSkus.length === 0}
        className="w-full"
      >
        <Sparkles className="h-4 w-4 mr-2" />
        Generate Content for {selectedSkus.length} SKUs
      </Button>
    </div>
  </CardContent>
</Card>
```

### 5. Generation API (`/api/sku-selection/generate`)

```typescript
POST /api/sku-selection/generate
{
  skus: ["1052", "1053", "1054", ...],
  options: {
    titles: true,
    descriptions: true,
    images: false,
    platforms: ["google", "shopify"],
    num_candidates: 3
  }
}

Response:
{
  job_id: "gen-abc123",
  status: "queued",
  total_skus: 20,
  estimated_minutes: 40
}
```

### 6. Generation Progress Tracking

Show real-time progress:
```tsx
<GenerationProgress 
  jobId={jobId}
  onComplete={() => router.push('/review')}
/>

// Polls /api/sku-selection/generate/[jobId] for status
// Shows: "Generating... 12/20 SKUs complete"
```

### 7. Product Catalog Integration

Need to fetch product details for generation prompts. Options:
- Query Supabase if product catalog is there
- Query Shopify API for product details
- Read from `data/Product Catalog.csv` (if accessible from Vercel)

Product info needed for generation:
- Product name
- Category
- Material
- Dimensions
- Features
- Current title/description (baseline)

## Reference Files
- `dashboard_data/lifestyle-eval/reports/pilot-selection-report-detailed.md` - Existing tier strategy
- `data/pilot_sku_selection/` - Previous selection data
- `src/feedops/pipeline/optimize_sku.py` - Python optimization pipeline
- `CLAUDE.md` - SKU selection strategy section

## Environment Variables Used
```
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CUSTOMER_ID=6253381786
GOOGLE_ADS_LOGIN_CUSTOMER_ID=7338022535
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
OPENAI_API_KEY (for content generation)
GEMINI_API_KEY (for image generation)
```

## Database Tables

### New Table: `generation_jobs`
```sql
CREATE TABLE generation_jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  status text DEFAULT 'queued', -- queued, processing, completed, failed
  total_skus integer,
  completed_skus integer DEFAULT 0,
  failed_skus integer DEFAULT 0,
  options jsonb, -- titles, descriptions, images, platforms
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  error_message text
);
```

### New Table: `generation_job_skus`
```sql
CREATE TABLE generation_job_skus (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_id uuid REFERENCES generation_jobs(id),
  master_sku text NOT NULL,
  status text DEFAULT 'pending', -- pending, processing, completed, failed
  error_message text,
  created_at timestamptz DEFAULT now()
);
```

## Success Criteria

1. User can input desired number of SKUs (5-50)
2. System recommends SKUs based on strategic tier distribution
3. User can see why each SKU was selected (tier, metrics)
4. User can modify selection before confirming
5. Top revenue SKUs are protected from selection
6. Already optimized SKUs are excluded by default
7. Generation runs and saves content to Supabase
8. Progress is trackable
9. User is redirected to review queue when complete

## UI/UX Considerations

- Show clear explanation of tier strategy to user
- Visualize tier distribution with chart
- Allow manual override (add/remove specific SKUs)
- Show estimated time based on content types selected
- Provide "Start Small" preset (10 SKUs) for first-time users
- Warning if user selects < 10 SKUs (low statistical power)

## Notes

- First run should default to 20 SKUs as recommended batch size
- Consider daily/weekly limits to prevent excessive API costs
- Generation is async - user doesn't need to wait
- Link to review queue when generation completes
- Consider email notification when large batches complete
