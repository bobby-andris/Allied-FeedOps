'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Sparkles, Info, ChevronDown, ArrowLeft, ArrowRight, Loader2, Clock, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
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

interface JobStatus {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'partial' | 'failed'
  total_skus: number
  completed_skus: number
  failed_skus: number
  skus: Array<{
    master_sku: string
    status: string
    error_message?: string
  }>
}

interface PastJob {
  id: string
  status: string
  total_skus: number
  completed_skus: number
  failed_skus: number
  options: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  skus: string[]
}

type Step = 'configure' | 'review' | 'confirm' | 'progress'

function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge className="bg-green-100 text-green-800"><CheckCircle2 className="h-3 w-3 mr-1" />Completed</Badge>
    case 'processing':
      return <Badge className="bg-blue-100 text-blue-800"><Loader2 className="h-3 w-3 mr-1 animate-spin" />Processing</Badge>
    case 'queued':
      return <Badge className="bg-yellow-100 text-yellow-800"><Clock className="h-3 w-3 mr-1" />Queued</Badge>
    case 'partial':
      return <Badge className="bg-orange-100 text-orange-800"><AlertCircle className="h-3 w-3 mr-1" />Partial</Badge>
    case 'failed':
      return <Badge className="bg-red-100 text-red-800"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return '-'
  const start = new Date(startedAt).getTime()
  const end = completedAt ? new Date(completedAt).getTime() : Date.now()
  const seconds = Math.round((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds}s`
}

export default function GeneratePage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('generate')
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
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)

  // Past jobs state
  const [pastJobs, setPastJobs] = useState<PastJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(false)

  // Poll for job status when in progress
  useEffect(() => {
    if (step !== 'progress' || !jobId) return

    const pollStatus = async () => {
      try {
        const res = await fetch(`/api/sku-selection/jobs/${jobId}`)
        if (res.ok) {
          const status: JobStatus = await res.json()
          setJobStatus(status)
        }
      } catch {
        // Silently retry on next interval
      }
    }

    // Poll immediately, then every 5 seconds
    pollStatus()
    const interval = setInterval(pollStatus, 5000)

    return () => clearInterval(interval)
  }, [step, jobId])

  const fetchPastJobs = useCallback(async () => {
    setLoadingJobs(true)
    try {
      const res = await fetch('/api/sku-selection/jobs')
      if (res.ok) {
        const data = await res.json()
        setPastJobs(data.jobs || [])
      }
    } catch {
      // Silently fail
    } finally {
      setLoadingJobs(false)
    }
  }, [])

  // Load past jobs when switching to that tab
  useEffect(() => {
    if (activeTab === 'past-jobs') {
      fetchPastJobs()
    }
  }, [activeTab, fetchPastJobs])

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
        setJobStatus(null)
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

  const progressPercent = jobStatus
    ? Math.round(((jobStatus.completed_skus + jobStatus.failed_skus) / Math.max(jobStatus.total_skus, 1)) * 100)
    : 0

  const isJobDone = jobStatus?.status === 'completed' || jobStatus?.status === 'partial' || jobStatus?.status === 'failed'

  return (
    <div className="space-y-6 p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Generate Content</h1>
        <p className="text-muted-foreground">
          Select SKUs for AI-powered title, description, and image generation
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="generate">Generate</TabsTrigger>
          <TabsTrigger value="past-jobs">Past Jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="generate" className="space-y-6 mt-4">
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
                <CardTitle>
                  {isJobDone ? 'Generation Complete' : 'Generation In Progress'}
                </CardTitle>
                <CardDescription>Job ID: {jobId.slice(0, 8)}...</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>
                      {jobStatus
                        ? `${jobStatus.completed_skus} of ${jobStatus.total_skus} SKUs completed`
                        : `Processing ${selectedSkus.size} SKUs...`}
                      {jobStatus && jobStatus.failed_skus > 0 && (
                        <span className="text-red-600 ml-2">
                          ({jobStatus.failed_skus} failed)
                        </span>
                      )}
                    </span>
                    <span className="text-muted-foreground">
                      {jobStatus ? getStatusBadge(jobStatus.status) : <Badge variant="secondary">Connecting...</Badge>}
                    </span>
                  </div>
                  <Progress value={progressPercent} className="h-2" />
                </div>

                {/* SKU-level status */}
                {jobStatus && jobStatus.skus.length > 0 && (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-muted">
                        <tr>
                          <th className="p-2 text-left">SKU</th>
                          <th className="p-2 text-left">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobStatus.skus.map((sku) => (
                          <tr key={sku.master_sku} className="border-t">
                            <td className="p-2 font-medium">{sku.master_sku}</td>
                            <td className="p-2">
                              {getStatusBadge(sku.status)}
                              {sku.error_message && (
                                <span className="text-xs text-red-600 ml-2">
                                  {sku.error_message}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {isJobDone && jobStatus?.status === 'completed' && (
                  <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
                    <p className="text-sm text-green-800">
                      Content generation complete. SKUs are now ready for review.
                    </p>
                  </div>
                )}

                {isJobDone && jobStatus?.status === 'failed' && (
                  <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
                    <p className="text-sm text-red-800">
                      Generation failed. Check the error details above and try again.
                    </p>
                  </div>
                )}

                {!isJobDone && (
                  <div className="bg-muted/50 p-4 rounded-lg">
                    <p className="text-sm text-muted-foreground">
                      Content generation is running in the background. This page
                      auto-refreshes every 5 seconds.
                    </p>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setStep('configure')
                      setJobId(null)
                      setJobStatus(null)
                    }}
                  >
                    Generate More
                  </Button>
                  <Button onClick={() => router.push('/review')}>
                    Go to Review Queue
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="past-jobs" className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Past Generation Jobs</CardTitle>
                  <CardDescription>
                    History of content generation jobs
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchPastJobs}
                  disabled={loadingJobs}
                >
                  {loadingJobs ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingJobs && pastJobs.length === 0 ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Loading jobs...
                </div>
              ) : pastJobs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No generation jobs found. Start a new generation from the Generate tab.
                </div>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="p-3 text-left">Job</th>
                        <th className="p-3 text-left">SKUs</th>
                        <th className="p-3 text-left">Status</th>
                        <th className="p-3 text-left">Progress</th>
                        <th className="p-3 text-left">Created</th>
                        <th className="p-3 text-left">Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pastJobs.map((job) => (
                        <tr key={job.id} className="border-t hover:bg-muted/50">
                          <td className="p-3">
                            <span className="font-mono text-xs">{job.id.slice(0, 8)}</span>
                          </td>
                          <td className="p-3">
                            <div className="font-medium">{job.skus.join(', ') || `${job.total_skus} SKUs`}</div>
                          </td>
                          <td className="p-3">
                            {getStatusBadge(job.status)}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {job.completed_skus}/{job.total_skus}
                            {job.failed_skus > 0 && (
                              <span className="text-red-600 ml-1">
                                ({job.failed_skus} failed)
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {formatDate(job.created_at)}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {formatDuration(job.started_at, job.completed_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
