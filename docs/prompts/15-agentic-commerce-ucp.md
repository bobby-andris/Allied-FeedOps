# Task: Implement Agentic Commerce (UCP) Integration

## Objective

Implement Shopify's Universal Commerce Protocol (UCP) to make Allied Brass products discoverable by AI agents (ChatGPT, Gemini, Copilot, Perplexity), enabling direct purchases through conversational AI interfaces.

## Problem Statement

AI agents are increasingly used for shopping research and purchases. If our products aren't agent-discoverable, we lose customers to competitors who are. Currently:
- No structured data for AI agent consumption
- Missing from AI shopping recommendations
- No visibility into agent-driven traffic or conversions
- Competitors who enable UCP will capture early traffic

## Solution Overview

Implement Shopify's Universal Commerce Protocol to:
1. Enable Agentic Storefronts in Shopify Plus admin
2. Ensure product data is structured for agent consumption
3. Add agent-friendly metadata following MCP schema
4. Monitor agent traffic and conversions
5. Optimize product data for agent discovery

## Background: What is UCP?

**Universal Commerce Protocol (UCP)** is a new standard announced by Shopify and Google in January 2026 that enables AI agents to:
- Browse products programmatically
- Read detailed product information
- Add items to carts
- Complete purchases on behalf of users

**Key Quote from Tobi Lütke (Shopify CEO):**
> "We're making every Shopify store agent-ready by default. Commerce shouldn't care whether the customer is a human browsing on their phone or an AI assistant helping them shop."

**Google's Involvement:**
- Native shopping rolling out in Google AI Mode and Gemini app
- Agents can compare products, check inventory, and complete purchases
- Early adopters get visibility before the mass rollout

## Prerequisites

- Shopify Plus account (required for Agentic Storefronts)
- Shopify Admin API access
- Existing product data in Shopify

## Files to Create

### Dashboard Components
- `dashboard/src/app/(dashboard)/agents/page.tsx` - Agent commerce dashboard
- `dashboard/src/app/api/agents/status/route.ts` - UCP status check
- `dashboard/src/app/api/agents/traffic/route.ts` - Agent traffic metrics
- `dashboard/src/components/agents/AgentTrafficChart.tsx` - Visualize agent visits
- `dashboard/src/components/agents/ProductReadiness.tsx` - Check product data quality

### Documentation
- `docs/ucp-setup-guide.md` - Shopify Plus admin configuration

### Database
- `supabase/migrations/011_agent_commerce_tracking.sql`

## Database Schema

```sql
-- Track agent traffic and conversions
CREATE TABLE agent_sessions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id text UNIQUE NOT NULL,
  agent_type text, -- 'chatgpt', 'gemini', 'copilot', 'perplexity', 'unknown'
  user_agent text,
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  products_viewed integer DEFAULT 0,
  products_added_to_cart integer DEFAULT 0,
  checkout_started boolean DEFAULT false,
  order_completed boolean DEFAULT false,
  order_value numeric
);

-- Track which products agents interact with
CREATE TABLE agent_product_views (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id text REFERENCES agent_sessions(session_id),
  master_sku text NOT NULL,
  shopify_product_id text,
  action text, -- 'view', 'detail_request', 'add_to_cart', 'purchase'
  created_at timestamptz DEFAULT now()
);

-- Product readiness scores for agent discovery
CREATE TABLE product_agent_readiness (
  master_sku text PRIMARY KEY,
  title_quality_score numeric, -- 0-100
  description_quality_score numeric,
  image_quality_score numeric,
  structured_data_complete boolean DEFAULT false,
  metadata_complete boolean DEFAULT false,
  overall_readiness_score numeric GENERATED ALWAYS AS (
    (COALESCE(title_quality_score, 0) +
     COALESCE(description_quality_score, 0) +
     COALESCE(image_quality_score, 0)) / 3 *
    CASE WHEN structured_data_complete AND metadata_complete THEN 1 ELSE 0.7 END
  ) STORED,
  last_checked timestamptz DEFAULT now()
);

-- Daily agent traffic aggregates
CREATE TABLE agent_traffic_daily (
  date date NOT NULL,
  agent_type text NOT NULL,
  sessions integer DEFAULT 0,
  products_viewed integer DEFAULT 0,
  carts_created integer DEFAULT 0,
  orders_completed integer DEFAULT 0,
  revenue numeric DEFAULT 0,
  PRIMARY KEY (date, agent_type)
);

-- Indexes
CREATE INDEX idx_agent_sessions_type ON agent_sessions(agent_type);
CREATE INDEX idx_agent_sessions_date ON agent_sessions(started_at);
CREATE INDEX idx_agent_product_views_sku ON agent_product_views(master_sku);
```

## Shopify Plus Configuration

### Step 1: Enable Agentic Storefronts

In Shopify Plus Admin:
1. Go to **Settings** > **Apps and sales channels**
2. Click **Develop apps** > **Agentic Storefronts** (Beta)
3. Enable "Allow AI agents to browse and purchase"
4. Configure allowed agent types:
   - [x] Google Gemini / Google AI Mode
   - [x] OpenAI ChatGPT
   - [x] Microsoft Copilot
   - [x] Perplexity
   - [x] Other verified agents

### Step 2: Configure Product Feed for Agents

Agents consume product data via Shopify's MCP-compatible API. Ensure products have:

**Required Fields:**
- `title` - Clear, descriptive product name
- `description` - Detailed product description
- `price` - Current price with currency
- `availability` - In stock / out of stock
- `images` - High-quality product images

**Enhanced Fields (recommended for better agent discovery):**
- `product_type` - Category (e.g., "Towel Bars")
- `vendor` - Brand name ("Allied Brass")
- `tags` - Searchable keywords
- `variants` - All finish/size options with inventory
- `metafields` - Extended product attributes

### Step 3: Add Agent-Optimized Metafields

```graphql
mutation updateProductMetafields($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      metafields(first: 10) {
        edges {
          node {
            namespace
            key
            value
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}

# Variables
{
  "input": {
    "id": "gid://shopify/Product/4545063682180",
    "metafields": [
      {
        "namespace": "agent_commerce",
        "key": "short_description",
        "value": "24-inch brass towel bar in polished chrome, solid brass construction, wall mount",
        "type": "single_line_text_field"
      },
      {
        "namespace": "agent_commerce",
        "key": "key_features",
        "value": "[\"Solid brass construction\",\"28 finish options\",\"Lifetime warranty\",\"Made in Virginia\"]",
        "type": "json"
      },
      {
        "namespace": "agent_commerce",
        "key": "use_cases",
        "value": "[\"Master bathroom\",\"Guest bathroom\",\"Powder room\"]",
        "type": "json"
      },
      {
        "namespace": "agent_commerce",
        "key": "comparison_points",
        "value": "{\"vs_budget\":\"Unlike hollow brass alternatives, Allied Brass uses solid brass for durability\",\"vs_premium\":\"Same quality as luxury brands at 40% less\"}",
        "type": "json"
      }
    ]
  }
}
```

## API Implementation

### GET /api/agents/status

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET() {
  const supabase = await createClient()

  // Check UCP configuration status
  // In production, this would query Shopify Admin API
  const ucpEnabled = process.env.SHOPIFY_UCP_ENABLED === 'true'

  // Get agent traffic summary
  const { data: dailyTraffic } = await supabase
    .from('agent_traffic_daily')
    .select('*')
    .gte('date', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
    .order('date', { ascending: false })

  // Get product readiness stats
  const { data: readiness } = await supabase
    .from('product_agent_readiness')
    .select('overall_readiness_score, structured_data_complete, metadata_complete')

  const avgReadiness = readiness?.reduce((sum, r) => sum + (r.overall_readiness_score || 0), 0) / (readiness?.length || 1)
  const structuredComplete = readiness?.filter(r => r.structured_data_complete).length || 0
  const metadataComplete = readiness?.filter(r => r.metadata_complete).length || 0

  return NextResponse.json({
    ucpEnabled,
    configuration: {
      googleGemini: ucpEnabled,
      chatgpt: ucpEnabled,
      copilot: ucpEnabled,
      perplexity: ucpEnabled
    },
    traffic: {
      last7Days: dailyTraffic,
      totalSessions: dailyTraffic?.reduce((sum, d) => sum + d.sessions, 0) || 0,
      totalOrders: dailyTraffic?.reduce((sum, d) => sum + d.orders_completed, 0) || 0,
      totalRevenue: dailyTraffic?.reduce((sum, d) => sum + (d.revenue || 0), 0) || 0
    },
    productReadiness: {
      averageScore: avgReadiness,
      totalProducts: readiness?.length || 0,
      structuredDataComplete: structuredComplete,
      metadataComplete: metadataComplete
    }
  })
}
```

### GET /api/agents/traffic

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const days = parseInt(searchParams.get('days') || '30')

  const supabase = await createClient()

  const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0]

  // Get daily traffic by agent type
  const { data: dailyByAgent } = await supabase
    .from('agent_traffic_daily')
    .select('*')
    .gte('date', startDate)
    .order('date', { ascending: true })

  // Get top products viewed by agents
  const { data: topProducts } = await supabase
    .from('agent_product_views')
    .select('master_sku, action')
    .gte('created_at', startDate)

  // Aggregate product views
  const productCounts = new Map<string, { views: number; carts: number; purchases: number }>()
  for (const view of topProducts || []) {
    const existing = productCounts.get(view.master_sku) || { views: 0, carts: 0, purchases: 0 }
    if (view.action === 'view' || view.action === 'detail_request') existing.views++
    if (view.action === 'add_to_cart') existing.carts++
    if (view.action === 'purchase') existing.purchases++
    productCounts.set(view.master_sku, existing)
  }

  const topProductsList = Array.from(productCounts.entries())
    .map(([sku, counts]) => ({ sku, ...counts }))
    .sort((a, b) => b.views - a.views)
    .slice(0, 10)

  // Calculate conversion funnel
  const totalViews = topProducts?.filter(p => p.action === 'view').length || 0
  const totalCarts = topProducts?.filter(p => p.action === 'add_to_cart').length || 0
  const totalPurchases = topProducts?.filter(p => p.action === 'purchase').length || 0

  return NextResponse.json({
    dailyByAgent,
    topProducts: topProductsList,
    funnel: {
      views: totalViews,
      carts: totalCarts,
      purchases: totalPurchases,
      viewToCartRate: totalViews > 0 ? (totalCarts / totalViews * 100).toFixed(2) : 0,
      cartToPurchaseRate: totalCarts > 0 ? (totalPurchases / totalCarts * 100).toFixed(2) : 0
    }
  })
}
```

### POST /api/agents/check-readiness

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const { skus } = await request.json()

  const supabase = await createClient()
  const results = []

  for (const sku of skus) {
    // Get product data from generated_content
    const { data: content } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', sku)
      .eq('is_current', true)

    const title = content?.find(c => c.content_type === 'title')
    const description = content?.find(c => c.content_type === 'description')

    // Score title quality for agent consumption
    const titleScore = scoreAgentTitle(title?.candidate_content || '')
    const descScore = scoreAgentDescription(description?.candidate_content || '')

    // Check for required metafields (would query Shopify in production)
    const structuredDataComplete = titleScore > 60 && descScore > 60
    const metadataComplete = true // Placeholder

    const readiness = {
      master_sku: sku,
      title_quality_score: titleScore,
      description_quality_score: descScore,
      image_quality_score: 80, // Placeholder - would check image quality
      structured_data_complete: structuredDataComplete,
      metadata_complete: metadataComplete,
      last_checked: new Date().toISOString()
    }

    // Upsert readiness score
    await supabase
      .from('product_agent_readiness')
      .upsert(readiness, { onConflict: 'master_sku' })

    results.push(readiness)
  }

  return NextResponse.json({ results })
}

function scoreAgentTitle(title: string): number {
  let score = 50

  // Length check (agents prefer concise, informative titles)
  if (title.length >= 30 && title.length <= 100) score += 15
  else if (title.length > 100) score -= 10

  // Contains product type
  const productTypes = ['towel bar', 'grab bar', 'soap dispenser', 'toilet paper holder', 'hook']
  if (productTypes.some(type => title.toLowerCase().includes(type))) score += 15

  // Contains brand
  if (title.toLowerCase().includes('allied brass')) score += 10

  // Contains key specs (dimension)
  if (/\d+[\s-]?(inch|in|"|cm|mm)/i.test(title)) score += 10

  return Math.min(100, Math.max(0, score))
}

function scoreAgentDescription(description: string): number {
  let score = 50

  // Length check
  if (description.length >= 200 && description.length <= 800) score += 15
  else if (description.length < 100) score -= 20

  // Contains key information agents look for
  if (description.toLowerCase().includes('material')) score += 5
  if (description.toLowerCase().includes('dimension') || /\d+[\s-]?(inch|in|")/i.test(description)) score += 5
  if (description.toLowerCase().includes('warranty')) score += 5
  if (description.toLowerCase().includes('finish')) score += 5

  // Contains use case language
  if (description.toLowerCase().includes('bathroom') || description.toLowerCase().includes('kitchen')) score += 5

  // Avoids vague marketing language
  const vagueWords = ['amazing', 'incredible', 'best', 'perfect', 'stunning']
  const vagueCount = vagueWords.filter(w => description.toLowerCase().includes(w)).length
  score -= vagueCount * 5

  return Math.min(100, Math.max(0, score))
}
```

## UI Components

### AgentTrafficChart.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

interface DailyTraffic {
  date: string
  agent_type: string
  sessions: number
  orders_completed: number
  revenue: number
}

interface AgentTrafficChartProps {
  data: DailyTraffic[]
}

export function AgentTrafficChart({ data }: AgentTrafficChartProps) {
  // Transform data for chart
  const chartData = data.reduce((acc, item) => {
    const existing = acc.find(d => d.date === item.date)
    if (existing) {
      existing[item.agent_type] = item.sessions
      existing.total = (existing.total || 0) + item.sessions
    } else {
      acc.push({
        date: item.date,
        [item.agent_type]: item.sessions,
        total: item.sessions
      })
    }
    return acc
  }, [] as any[])

  const agentColors: Record<string, string> = {
    gemini: '#4285f4',
    chatgpt: '#10a37f',
    copilot: '#7b68ee',
    perplexity: '#20b2aa',
    unknown: '#888888'
  }

  const agentTypes = [...new Set(data.map(d => d.agent_type))]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Traffic (Sessions)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            {agentTypes.map(agent => (
              <Line
                key={agent}
                type="monotone"
                dataKey={agent}
                name={agent.charAt(0).toUpperCase() + agent.slice(1)}
                stroke={agentColors[agent] || '#888'}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

### ProductReadiness.tsx

```tsx
'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'

interface ReadinessData {
  averageScore: number
  totalProducts: number
  structuredDataComplete: number
  metadataComplete: number
}

interface ProductReadinessProps {
  data: ReadinessData
}

export function ProductReadiness({ data }: ProductReadinessProps) {
  const structuredPercent = (data.structuredDataComplete / data.totalProducts) * 100
  const metadataPercent = (data.metadataComplete / data.totalProducts) * 100

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          Product Readiness
          <Badge variant={data.averageScore >= 80 ? 'default' : data.averageScore >= 60 ? 'secondary' : 'destructive'}>
            {data.averageScore.toFixed(0)}%
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall readiness */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Overall Agent Readiness</span>
            <span>{data.averageScore.toFixed(0)}%</span>
          </div>
          <Progress value={data.averageScore} />
        </div>

        {/* Checklist */}
        <div className="space-y-2">
          <ReadinessCheck
            label="Structured Data"
            complete={structuredPercent >= 80}
            partial={structuredPercent >= 50}
            detail={`${data.structuredDataComplete}/${data.totalProducts} products`}
          />
          <ReadinessCheck
            label="Agent Metadata"
            complete={metadataPercent >= 80}
            partial={metadataPercent >= 50}
            detail={`${data.metadataComplete}/${data.totalProducts} products`}
          />
          <ReadinessCheck
            label="UCP Enabled"
            complete={process.env.NEXT_PUBLIC_SHOPIFY_UCP_ENABLED === 'true'}
            partial={false}
            detail="Shopify Plus configuration"
          />
        </div>

        {/* Recommendations */}
        {data.averageScore < 80 && (
          <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
            <p className="text-sm font-medium text-yellow-800">
              Improve Readiness
            </p>
            <ul className="text-xs text-yellow-700 mt-1 space-y-1">
              {structuredPercent < 80 && (
                <li>• Add structured data to {data.totalProducts - data.structuredDataComplete} products</li>
              )}
              {metadataPercent < 80 && (
                <li>• Add agent metafields to {data.totalProducts - data.metadataComplete} products</li>
              )}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ReadinessCheck({
  label,
  complete,
  partial,
  detail
}: {
  label: string
  complete: boolean
  partial: boolean
  detail: string
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-2">
        {complete ? (
          <CheckCircle className="h-4 w-4 text-green-600" />
        ) : partial ? (
          <AlertCircle className="h-4 w-4 text-yellow-600" />
        ) : (
          <XCircle className="h-4 w-4 text-red-600" />
        )}
        <span>{label}</span>
      </div>
      <span className="text-muted-foreground">{detail}</span>
    </div>
  )
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/agents/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AgentTrafficChart } from '@/components/agents/AgentTrafficChart'
import { ProductReadiness } from '@/components/agents/ProductReadiness'
import { Bot, TrendingUp, ShoppingCart, DollarSign, RefreshCw, ExternalLink } from 'lucide-react'

export default function AgentCommercePage() {
  const [status, setStatus] = useState<any>(null)
  const [traffic, setTraffic] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    const [statusRes, trafficRes] = await Promise.all([
      fetch('/api/agents/status'),
      fetch('/api/agents/traffic?days=30')
    ])
    setStatus(await statusRes.json())
    setTraffic(await trafficRes.json())
    setLoading(false)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6" />
            Agentic Commerce
          </h1>
          <p className="text-muted-foreground">
            Universal Commerce Protocol (UCP) - AI agent discovery and purchases
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button asChild>
            <a
              href="https://admin.shopify.com/store/allied-brass/settings/apps"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              Shopify Settings
            </a>
          </Button>
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          {/* UCP Status Banner */}
          <div className={`p-4 rounded-lg border ${
            status?.ucpEnabled
              ? 'bg-green-50 border-green-200'
              : 'bg-yellow-50 border-yellow-200'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className={`font-medium ${
                  status?.ucpEnabled ? 'text-green-800' : 'text-yellow-800'
                }`}>
                  {status?.ucpEnabled
                    ? 'UCP Enabled - Products are agent-discoverable'
                    : 'UCP Not Enabled - Enable in Shopify Plus admin'}
                </h3>
                <p className={`text-sm mt-1 ${
                  status?.ucpEnabled ? 'text-green-700' : 'text-yellow-700'
                }`}>
                  {status?.ucpEnabled
                    ? 'AI agents (Gemini, ChatGPT, Copilot, Perplexity) can discover and purchase products'
                    : 'Configure Agentic Storefronts in Shopify Plus to enable agent commerce'}
                </p>
              </div>
              <div className="flex gap-2">
                {Object.entries(status?.configuration || {}).map(([agent, enabled]) => (
                  <Badge
                    key={agent}
                    variant={enabled ? 'default' : 'outline'}
                  >
                    {agent}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Agent Sessions (7d)</p>
                    <p className="text-2xl font-bold">
                      {status?.traffic?.totalSessions || 0}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <ShoppingCart className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Agent Orders (7d)</p>
                    <p className="text-2xl font-bold">
                      {status?.traffic?.totalOrders || 0}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">Agent Revenue (7d)</p>
                    <p className="text-2xl font-bold">
                      ${(status?.traffic?.totalRevenue || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">View → Purchase</p>
                    <p className="text-2xl font-bold">
                      {traffic?.funnel?.cartToPurchaseRate || 0}%
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <AgentTrafficChart data={traffic?.dailyByAgent || []} />
            </div>
            <ProductReadiness data={status?.productReadiness || {}} />
          </div>

          {/* Conversion Funnel */}
          <Card>
            <CardHeader>
              <CardTitle>Agent Conversion Funnel</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <FunnelStep
                  label="Product Views"
                  count={traffic?.funnel?.views || 0}
                  rate="100%"
                />
                <div className="h-0.5 flex-1 bg-muted mx-4" />
                <FunnelStep
                  label="Added to Cart"
                  count={traffic?.funnel?.carts || 0}
                  rate={`${traffic?.funnel?.viewToCartRate || 0}%`}
                />
                <div className="h-0.5 flex-1 bg-muted mx-4" />
                <FunnelStep
                  label="Purchases"
                  count={traffic?.funnel?.purchases || 0}
                  rate={`${traffic?.funnel?.cartToPurchaseRate || 0}%`}
                />
              </div>
            </CardContent>
          </Card>

          {/* Top Products */}
          <Card>
            <CardHeader>
              <CardTitle>Top Products by Agent Views</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {(traffic?.topProducts || []).slice(0, 5).map((product: any, i: number) => (
                  <div
                    key={product.sku}
                    className="flex items-center justify-between p-2 rounded bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium w-8">{i + 1}.</span>
                      <span className="font-medium">{product.sku}</span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span>{product.views} views</span>
                      <span className="text-muted-foreground">
                        {product.carts} carts
                      </span>
                      <span className="text-green-600 font-medium">
                        {product.purchases} purchases
                      </span>
                    </div>
                  </div>
                ))}
                {(traffic?.topProducts || []).length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No agent product views recorded yet
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function FunnelStep({
  label,
  count,
  rate
}: {
  label: string
  count: number
  rate: string
}) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold">{count.toLocaleString()}</p>
      <p className="text-sm text-muted-foreground">{label}</p>
      <Badge variant="outline" className="mt-1">{rate}</Badge>
    </div>
  )
}
```

## UCP Setup Guide

Create `docs/ucp-setup-guide.md`:

```markdown
# Universal Commerce Protocol (UCP) Setup Guide

## Overview

UCP enables AI agents to discover and purchase Allied Brass products through conversational interfaces.

## Prerequisites

1. Shopify Plus subscription (required for Agentic Storefronts)
2. Products with complete structured data
3. Inventory management configured

## Step-by-Step Setup

### 1. Enable Agentic Storefronts

1. Log into Shopify Plus Admin
2. Go to Settings > Apps and sales channels
3. Click "Develop apps" or "Agentic Storefronts"
4. Enable "Allow AI agents to browse and purchase"
5. Select which agent types to allow

### 2. Verify Product Data Quality

Run the readiness check in the FeedOps dashboard:
- Go to /agents
- Click "Check Readiness"
- Address any products with scores below 70%

### 3. Add Agent Metafields

For each product, add these metafields via Shopify Admin API:
- `agent_commerce.short_description` - Concise product summary
- `agent_commerce.key_features` - JSON array of features
- `agent_commerce.use_cases` - JSON array of use cases
- `agent_commerce.comparison_points` - JSON comparison data

### 4. Monitor Performance

- Check the /agents dashboard daily initially
- Track agent sessions, conversions, revenue
- Optimize product data based on agent behavior

## Troubleshooting

**Products not appearing in agent results:**
- Verify UCP is enabled
- Check product readiness score
- Ensure inventory is available

**Low conversion from agent traffic:**
- Review agent-specific pricing (if applicable)
- Check checkout flow for agent compatibility
- Verify shipping/availability settings
```

## Success Criteria

1. [ ] UCP configuration documented
2. [ ] Agent traffic tracking implemented
3. [ ] Product readiness scoring works
4. [ ] Dashboard shows agent metrics
5. [ ] Metafield structure defined
6. [ ] Setup guide complete
7. [ ] At least one agent type enabled (if Shopify Plus available)

## Future Enhancements

- Agent-specific pricing experiments
- Automated metafield generation from descriptions
- Agent conversation analysis
- Cross-agent comparison reporting
- Real-time agent activity feed
