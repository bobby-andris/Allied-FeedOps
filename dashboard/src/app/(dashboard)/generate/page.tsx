'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Sparkles, Info, ChevronDown, ArrowLeft, ArrowRight, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'

interface ScoredSku {
  master_sku: string
  product_name?: string
  category?: string
  tier: 'tier1' | 'tier2' | 'tier3' | 'fill'
  score: number
  impressions: number
  clicks: number
  conversions: number
  ctr: number
  cvr: number
  variant_count?: number
  tierReason?: string
}

interface SelectionResult {
  recommended: ScoredSku[]
  distribution: { tier1: number; tier2: number; tier3: number; fill: number }
  excluded: {
    top_revenue: string[]
    already_optimized: string[]
    insufficient_data: string[]
  }
  total_eligible: number
  google_ads_configured: boolean
}

type Step = 'configure' | 'review' | 'confirm' | 'progress'

export default function GeneratePage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>('configure')

  // Configuration state
  const [count, setCount] = useState(20)
  const [excludeOptimized, setExcludeOptimized] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Selection state
  const [data, setData] = useState<SelectionResult | null>(null)
  const [selectedSkus, setSelectedSkus] = useState<Set<string>>(new Set())

  // Generation options
  const [generateTitles, setGenerateTitles] = useState(true)
  const [generateDescriptions, setGenerateDescriptions] = useState(true)
  const [generateImages, setGenerateImages] = useState(false)
  const [platforms, setPlatforms] = useState({
    google: true,
    bing: false,
    shopify: true,
  })

  // Job state
  const [generating, setGenerating] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)

  const fetchRecommendations = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `/api/sku-selection?count=${count}&excludeOptimized=${excludeOptimized}`
      )
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error || 'Failed to fetch recommendations')
      }
      const result: SelectionResult = await res.json()
      setData(result)
      setSelectedSkus(new Set(result.recommended.map((s) => s.master_sku)))
      setStep('review')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const startGeneration = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch('/api/sku-selection/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skus: Array.from(selectedSkus),
          options: {
            titles: generateTitles,
            descriptions: generateDescriptions,
            images: generateImages,
            platforms: Object.entries(platforms)
              .filter(([, v]) => v)
              .map(([k]) => k),
          },
        }),
      })

      const result = await res.json()

      if (!res.ok) {
        throw new Error(result.error || 'Failed to start generation')
      }

      if (result.success) {
        setJobId(result.job_id)
        setStep('progress')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setGenerating(false)
    }
  }

  const toggleSku = (sku: string) => {
    const newSelected = new Set(selectedSkus)
    if (newSelected.has(sku)) {
      newSelected.delete(sku)
    } else {
      newSelected.add(sku)
    }
    setSelectedSkus(newSelected)
  }

  const toggleAll = () => {
    if (selectedSkus.size === data?.recommended.length) {
      setSelectedSkus(new Set())
    } else {
      setSelectedSkus(new Set(data?.recommended.map((s) => s.master_sku) || []))
    }
  }

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'tier1':
        return 'bg-blue-100 text-blue-800'
      case 'tier2':
        return 'bg-green-100 text-green-800'
      case 'tier3':
        return 'bg-orange-100 text-orange-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6 p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Generate Content</h1>
        <p className="text-muted-foreground">
          Select SKUs for AI-powered title, description, and image generation
        </p>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Step 1: Configure */}
      {step === 'configure' && (
        <Card>
          <CardHeader>
            <CardTitle>Configure Selection</CardTitle>
            <CardDescription>
              Choose how many SKUs to optimize based on strategic tier distribution
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="count">Number of SKUs to optimize</Label>
              <Input
                id="count"
                type="number"
                min={5}
                max={50}
                value={count}
                onChange={(e) => setCount(parseInt(e.target.value) || 20)}
                className="w-32"
              />
              <p className="text-sm text-muted-foreground">
                Recommended: 20-40 SKUs for statistically significant results
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="exclude"
                checked={excludeOptimized}
                onCheckedChange={(checked) =>
                  setExcludeOptimized(checked as boolean)
                }
              />
              <Label htmlFor="exclude">Exclude already optimized SKUs</Label>
            </div>

            <div className="bg-muted/50 p-4 rounded-lg space-y-2">
              <div className="flex items-center gap-2 font-medium">
                <Info className="h-4 w-4" />
                Tier Distribution Strategy
              </div>
              <p className="text-sm text-muted-foreground">
                SKUs are selected using a strategic mix to balance risk and
                opportunity:
              </p>
              <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1">
                <li>
                  <strong>Tier 1 (20%):</strong> High conversion, low traffic -
                  risk-managed winners
                </li>
                <li>
                  <strong>Tier 2 (50%):</strong> Mid-pack performance - primary
                  test bed
                </li>
                <li>
                  <strong>Tier 3 (20%):</strong> High traffic, low conversion -
                  largest upside
                </li>
                <li>
                  <strong>Fill (10%):</strong> Category diversity completion
                </li>
              </ul>
            </div>

            <Button onClick={fetchRecommendations} disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Loading...
                </>
              ) : (
                'Get Recommendations'
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Review */}
      {step === 'review' && data && (
        <Card>
          <CardHeader>
            <CardTitle>Recommended SKUs</CardTitle>
            <CardDescription>
              {data.google_ads_configured
                ? 'Based on Google Ads performance data (last 30 days)'
                : 'Using sample data - configure Google Ads for real metrics'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Distribution summary */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-blue-50 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-blue-600">
                  {data.distribution.tier1}
                </p>
                <p className="text-xs text-blue-600">Tier 1</p>
              </div>
              <div className="bg-green-50 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-green-600">
                  {data.distribution.tier2}
                </p>
                <p className="text-xs text-green-600">Tier 2</p>
              </div>
              <div className="bg-orange-50 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-orange-600">
                  {data.distribution.tier3}
                </p>
                <p className="text-xs text-orange-600">Tier 3</p>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-600">
                  {data.distribution.fill}
                </p>
                <p className="text-xs text-gray-600">Fill</p>
              </div>
            </div>

            {/* SKU Table */}
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="p-2 text-left w-8">
                      <Checkbox
                        checked={selectedSkus.size === data.recommended.length}
                        onCheckedChange={toggleAll}
                      />
                    </th>
                    <th className="p-2 text-left">SKU</th>
                    <th className="p-2 text-left">Category</th>
                    <th className="p-2 text-left">Tier</th>
                    <th className="p-2 text-right">Score</th>
                    <th className="p-2 text-right">CTR</th>
                    <th className="p-2 text-right">CVR</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recommended.map((sku) => (
                    <tr
                      key={sku.master_sku}
                      className="border-t hover:bg-muted/50"
                    >
                      <td className="p-2">
                        <Checkbox
                          checked={selectedSkus.has(sku.master_sku)}
                          onCheckedChange={() => toggleSku(sku.master_sku)}
                        />
                      </td>
                      <td className="p-2">
                        <div className="font-medium">{sku.master_sku}</div>
                        {sku.product_name && (
                          <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                            {sku.product_name}
                          </div>
                        )}
                      </td>
                      <td className="p-2 text-muted-foreground">
                        {sku.category || '-'}
                      </td>
                      <td className="p-2">
                        <Badge className={getTierColor(sku.tier)}>
                          {sku.tier}
                        </Badge>
                      </td>
                      <td className="p-2 text-right font-medium">{sku.score}</td>
                      <td className="p-2 text-right">{sku.ctr.toFixed(2)}%</td>
                      <td className="p-2 text-right">{sku.cvr.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Excluded info */}
            <Collapsible>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
                <ChevronDown className="h-4 w-4" />
                Excluded SKUs (
                {data.excluded.top_revenue.length +
                  data.excluded.already_optimized.length +
                  data.excluded.insufficient_data.length}
                )
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-2 text-sm text-muted-foreground space-y-1">
                {data.excluded.top_revenue.length > 0 && (
                  <p>
                    <strong>Top revenue (protected):</strong>{' '}
                    {data.excluded.top_revenue.slice(0, 5).join(', ')}
                    {data.excluded.top_revenue.length > 5 &&
                      ` +${data.excluded.top_revenue.length - 5} more`}
                  </p>
                )}
                {data.excluded.already_optimized.length > 0 && (
                  <p>
                    <strong>Already optimized:</strong>{' '}
                    {data.excluded.already_optimized.slice(0, 5).join(', ')}
                    {data.excluded.already_optimized.length > 5 &&
                      ` +${data.excluded.already_optimized.length - 5} more`}
                  </p>
                )}
                {data.excluded.insufficient_data.length > 0 && (
                  <p>
                    <strong>Insufficient data:</strong>{' '}
                    {data.excluded.insufficient_data.slice(0, 5).join(', ')}
                    {data.excluded.insufficient_data.length > 5 &&
                      ` +${data.excluded.insufficient_data.length - 5} more`}
                  </p>
                )}
              </CollapsibleContent>
            </Collapsible>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep('configure')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Button
                onClick={() => setStep('confirm')}
                disabled={selectedSkus.size === 0}
              >
                Continue with {selectedSkus.size} SKUs
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Confirm */}
      {step === 'confirm' && data && (
        <Card>
          <CardHeader>
            <CardTitle>Confirm Generation</CardTitle>
            <CardDescription>
              Review options before starting content generation
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-muted p-4 rounded-lg text-center">
                <p className="text-3xl font-bold">{selectedSkus.size}</p>
                <p className="text-sm text-muted-foreground">SKUs Selected</p>
              </div>
              <div className="bg-muted p-4 rounded-lg text-center">
                <p className="text-3xl font-bold">
                  {data.recommended
                    .filter((s) => selectedSkus.has(s.master_sku))
                    .reduce((sum, s) => sum + (s.variant_count || 1), 0)}
                </p>
                <p className="text-sm text-muted-foreground">Est. Variants</p>
              </div>
              <div className="bg-muted p-4 rounded-lg text-center">
                <p className="text-3xl font-bold">{selectedSkus.size * 2}</p>
                <p className="text-sm text-muted-foreground">Est. Minutes</p>
              </div>
            </div>

            {/* Content options */}
            <div className="space-y-2">
              <Label>Content to generate</Label>
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="titles"
                    checked={generateTitles}
                    onCheckedChange={(c) => setGenerateTitles(c as boolean)}
                  />
                  <Label htmlFor="titles" className="font-normal">
                    Titles
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="descriptions"
                    checked={generateDescriptions}
                    onCheckedChange={(c) =>
                      setGenerateDescriptions(c as boolean)
                    }
                  />
                  <Label htmlFor="descriptions" className="font-normal">
                    Descriptions
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="images"
                    checked={generateImages}
                    onCheckedChange={(c) => setGenerateImages(c as boolean)}
                  />
                  <Label htmlFor="images" className="font-normal">
                    Lifestyle Images
                  </Label>
                </div>
              </div>
            </div>

            {/* Platform options */}
            <div className="space-y-2">
              <Label>Platforms</Label>
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="google"
                    checked={platforms.google}
                    onCheckedChange={(c) =>
                      setPlatforms((p) => ({ ...p, google: c as boolean }))
                    }
                  />
                  <Label htmlFor="google" className="font-normal">
                    Google
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="bing"
                    checked={platforms.bing}
                    onCheckedChange={(c) =>
                      setPlatforms((p) => ({ ...p, bing: c as boolean }))
                    }
                  />
                  <Label htmlFor="bing" className="font-normal">
                    Bing
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="shopify"
                    checked={platforms.shopify}
                    onCheckedChange={(c) =>
                      setPlatforms((p) => ({ ...p, shopify: c as boolean }))
                    }
                  />
                  <Label htmlFor="shopify" className="font-normal">
                    Shopify
                  </Label>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep('review')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Button
                onClick={startGeneration}
                disabled={
                  generating ||
                  selectedSkus.size === 0 ||
                  (!generateTitles &&
                    !generateDescriptions &&
                    !generateImages) ||
                  (!platforms.google && !platforms.bing && !platforms.shopify)
                }
                className="flex-1"
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Generate Content for {selectedSkus.size} SKUs
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Progress */}
      {step === 'progress' && jobId && (
        <Card>
          <CardHeader>
            <CardTitle>Generation In Progress</CardTitle>
            <CardDescription>Job ID: {jobId}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Processing {selectedSkus.size} SKUs...</span>
                <span className="text-muted-foreground">Job queued</span>
              </div>
              <Progress value={0} className="h-2" />
            </div>

            <div className="bg-muted/50 p-4 rounded-lg">
              <p className="text-sm text-muted-foreground">
                Content generation has been queued. This process runs in the
                background. You can check the status in the Review Queue once
                processing begins.
              </p>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => router.push('/')}>
                Back to Dashboard
              </Button>
              <Button onClick={() => router.push('/review')}>
                Go to Review Queue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
