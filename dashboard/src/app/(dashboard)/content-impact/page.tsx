"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  ArrowUp,
  ArrowDown,
  AlertCircle,
  Clock,
  AlertTriangle,
} from "lucide-react"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// ---------------------------------------------------------------------------
// Types (mirrors API response)
// ---------------------------------------------------------------------------

type ImpactTier =
  | "strong_improvement"
  | "moderate_improvement"
  | "no_change"
  | "moderate_decline"
  | "decline"
  | "insufficient_data"

interface WindowMetrics {
  available: boolean
  avg_ctr?: number
  avg_cvr?: number
  ctr_delta?: number
  cvr_delta?: number
  data_points?: number
  pending_days?: number
}

interface ContentImpactRow {
  publish_event_id: number
  master_sku: string
  platform: string
  published_at: string
  prompt_hash: string | null
  has_baseline: boolean
  baseline: { avg_ctr: number; avg_cvr: number } | null
  windows: {
    d7: WindowMetrics | null
    d14: WindowMetrics | null
    d30: WindowMetrics | null
  }
  impact: {
    tier: ImpactTier
    label: string
    color: string
    ctr_lift: number | null
    cvr_lift: number | null
  }
  is_latest_publish: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeDate(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "1 day ago"
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 14) return "1 week ago"
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 60) return "1 month ago"
  return `${Math.floor(diffDays / 30)} months ago`
}

function formatExactDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatCtr(value: number): string {
  // CTR values are 0-1, display as percentage
  return `${(value * 100).toFixed(2)}%`
}

function formatDelta(delta: number): string {
  const pct = delta * 100
  const sign = pct >= 0 ? "+" : ""
  return `${sign}${pct.toFixed(2)}%`
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ImpactScoreBadge({ tier, label }: { tier: ImpactTier; label: string }) {
  switch (tier) {
    case "strong_improvement":
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 border-green-300">
          {label}
        </Badge>
      )
    case "moderate_improvement":
      return (
        <Badge
          variant="outline"
          className="border-green-500 text-green-700"
        >
          {label}
        </Badge>
      )
    case "no_change":
      return <Badge variant="secondary">{label}</Badge>
    case "moderate_decline":
      return (
        <Badge
          variant="outline"
          className="border-orange-500 text-orange-700"
        >
          {label}
        </Badge>
      )
    case "decline":
      return <Badge variant="destructive">{label}</Badge>
    case "insufficient_data":
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="secondary" className="text-gray-500">
                {label}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>Need at least 7 days of data for both treated and control SKUs</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    default:
      return <Badge variant="secondary">{label}</Badge>
  }
}

function WindowCell({ metrics }: { metrics: WindowMetrics | null }) {
  if (!metrics) {
    return <span className="text-gray-400">--</span>
  }

  if (!metrics.available) {
    return (
      <span className="text-gray-400 italic text-xs">
        Pending ({metrics.pending_days}d)
      </span>
    )
  }

  return <span>{formatCtr(metrics.avg_ctr ?? 0)}</span>
}

function DeltaCell({ row }: { row: ContentImpactRow }) {
  // Use the best available window delta (30d > 14d > 7d)
  const bestWindow = row.windows.d30?.available
    ? row.windows.d30
    : row.windows.d14?.available
      ? row.windows.d14
      : row.windows.d7?.available
        ? row.windows.d7
        : null

  if (!bestWindow || bestWindow.ctr_delta === undefined) {
    return <span className="text-gray-400">--</span>
  }

  const delta = bestWindow.ctr_delta
  if (delta > 0) {
    return (
      <span className="text-green-600 flex items-center gap-1">
        <ArrowUp className="h-3 w-3" />
        {formatDelta(delta)}
      </span>
    )
  }
  if (delta < 0) {
    return (
      <span className="text-red-600 flex items-center gap-1">
        <ArrowDown className="h-3 w-3" />
        {formatDelta(delta)}
      </span>
    )
  }
  return <span className="text-gray-400">{formatDelta(delta)}</span>
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function TableSkeleton() {
  return (
    <div className="space-y-3 p-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ContentImpactPage() {
  const router = useRouter()
  const [data, setData] = useState<ContentImpactRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [latestOnly, setLatestOnly] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        const res = await fetch("/api/content-impact")
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.error || `HTTP ${res.status}`)
        }
        const rows: ContentImpactRow[] = await res.json()
        setData(rows)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error")
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const filteredData = latestOnly
    ? data.filter((r) => r.is_latest_publish)
    : data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Content Impact</h1>
        <p className="text-muted-foreground">
          See how published content changes affected search performance
        </p>
      </div>

      {/* Error state */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Published SKU Impact</CardTitle>
              <CardDescription>
                Baseline vs post-publish CTR at 7, 14, and 30-day windows
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="latest-only"
                checked={latestOnly}
                onCheckedChange={setLatestOnly}
              />
              <Label htmlFor="latest-only" className="text-sm">
                Latest only
              </Label>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton />
          ) : filteredData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Clock className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">No published SKUs found</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Publish content to see impact data.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Published</TableHead>
                    <TableHead className="text-right">Baseline CTR</TableHead>
                    <TableHead className="text-right">7d CTR</TableHead>
                    <TableHead className="text-right">14d CTR</TableHead>
                    <TableHead className="text-right">30d CTR</TableHead>
                    <TableHead className="text-right">CTR Delta</TableHead>
                    <TableHead>Impact</TableHead>
                    <TableHead>Version</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredData.map((row) => (
                    <TableRow
                      key={row.publish_event_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() =>
                        router.push(
                          `/content-impact/${encodeURIComponent(row.master_sku)}?event_id=${row.publish_event_id}`
                        )
                      }
                    >
                      {/* SKU */}
                      <TableCell className="font-mono text-sm">
                        {row.master_sku}
                      </TableCell>

                      {/* Platform */}
                      <TableCell>
                        <PlatformBadge platform={row.platform as "google" | "bing" | "shopify"} />
                      </TableCell>

                      {/* Published date */}
                      <TableCell>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-sm">
                                {formatRelativeDate(row.published_at)}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>{formatExactDate(row.published_at)}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </TableCell>

                      {/* Baseline CTR */}
                      <TableCell className="text-right">
                        {row.has_baseline && row.baseline ? (
                          formatCtr(row.baseline.avg_ctr)
                        ) : (
                          <Badge
                            variant="outline"
                            className="border-yellow-500 text-yellow-700 text-xs"
                          >
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            No baseline
                          </Badge>
                        )}
                      </TableCell>

                      {/* 7d CTR */}
                      <TableCell className="text-right">
                        <WindowCell metrics={row.windows.d7} />
                      </TableCell>

                      {/* 14d CTR */}
                      <TableCell className="text-right">
                        <WindowCell metrics={row.windows.d14} />
                      </TableCell>

                      {/* 30d CTR */}
                      <TableCell className="text-right">
                        <WindowCell metrics={row.windows.d30} />
                      </TableCell>

                      {/* CTR Delta */}
                      <TableCell className="text-right">
                        <DeltaCell row={row} />
                      </TableCell>

                      {/* Impact */}
                      <TableCell>
                        <ImpactScoreBadge
                          tier={row.impact.tier}
                          label={row.impact.label}
                        />
                      </TableCell>

                      {/* Version */}
                      <TableCell>
                        {row.prompt_hash ? (
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {row.prompt_hash.slice(0, 8)}
                          </code>
                        ) : (
                          <Badge
                            variant="secondary"
                            className="text-gray-500 text-xs"
                          >
                            Legacy
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
