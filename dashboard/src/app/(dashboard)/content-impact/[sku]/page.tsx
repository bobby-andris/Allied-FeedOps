"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
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
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Info,
  Sparkles,
  AlertCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// ---------------------------------------------------------------------------
// Types
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

interface ImpactScoreDetail {
  metric_name: string
  pre_value: number | null
  post_value: number | null
  control_pre: number | null
  control_post: number | null
  did_lift_pct: number | null
  label: string | null
  confidence: number | null
  sample_size_treated: number
  sample_size_control: number
}

interface ControlSku {
  master_sku: string
  product_category: string | null
  avg_ctr: number | null
  avg_cvr: number | null
}

interface PublishHistoryEntry {
  publish_event_id: number
  published_at: string
  prompt_hash: string | null
  content_version: number | null
  impact_tier: ImpactTier
  impact_label: string
}

interface DetailData {
  publish_event_id: number
  master_sku: string
  platform: string
  published_at: string
  prompt_hash: string | null
  content_version: number | null
  baseline: {
    avg_ctr: number
    avg_cvr: number
    avg_impressions: number
    avg_clicks: number
  } | null
  windows: {
    d7: WindowMetrics | null
    d14: WindowMetrics | null
    d30: WindowMetrics | null
  }
  impact_scores: ImpactScoreDetail[]
  control_skus: ControlSku[]
  publish_history: PublishHistoryEntry[]
}

interface SearchTermDelta {
  search_term: string
  pre_impressions: number
  post_impressions: number
  impression_delta: number
  pre_clicks: number
  post_clicks: number
  click_delta: number
  is_new: boolean
}

interface SearchTermsData {
  gained: SearchTermDelta[]
  lost: SearchTermDelta[]
  pre_snapshot_date: string | null
  post_snapshot_date: string | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCtr(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function formatDelta(delta: number): string {
  const pct = delta * 100
  const sign = pct >= 0 ? "+" : ""
  return `${sign}${pct.toFixed(2)}%`
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function formatDateTime(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function tierColor(tier: ImpactTier): string {
  switch (tier) {
    case "strong_improvement":
      return "bg-green-100 text-green-800 border-green-300"
    case "moderate_improvement":
      return "border-green-500 text-green-700"
    case "no_change":
      return "bg-gray-100 text-gray-700 border-gray-300"
    case "moderate_decline":
      return "border-orange-500 text-orange-700"
    case "decline":
      return "bg-red-100 text-red-800 border-red-300"
    case "insufficient_data":
      return "bg-gray-50 text-gray-500 border-gray-200"
  }
}

function tierLabel(tier: ImpactTier): string {
  switch (tier) {
    case "strong_improvement":
      return "Strong Improvement"
    case "moderate_improvement":
      return "Moderate Improvement"
    case "no_change":
      return "No Significant Change"
    case "moderate_decline":
      return "Moderate Decline"
    case "decline":
      return "Decline"
    case "insufficient_data":
      return "Insufficient Data"
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ImpactSummaryCard({ data }: { data: DetailData }) {
  const ctrScore = data.impact_scores.find((s) => s.metric_name === "ctr")
  const cvrScore = data.impact_scores.find((s) => s.metric_name === "cvr")

  // Determine tier from CTR score (primary)
  let tier: ImpactTier = "insufficient_data"
  if (ctrScore) {
    if (
      ctrScore.sample_size_treated < 7 ||
      ctrScore.sample_size_control < 7 ||
      ctrScore.did_lift_pct === null
    ) {
      tier = "insufficient_data"
    } else if (ctrScore.did_lift_pct >= 10) {
      tier = "strong_improvement"
    } else if (ctrScore.did_lift_pct >= 3) {
      tier = "moderate_improvement"
    } else if (ctrScore.did_lift_pct <= -10) {
      tier = "decline"
    } else if (ctrScore.did_lift_pct <= -3) {
      tier = "moderate_decline"
    } else {
      tier = "no_change"
    }
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-6">
          <Badge className={`text-lg px-4 py-2 ${tierColor(tier)}`}>
            {tierLabel(tier)}
          </Badge>
          <div className="flex gap-8">
            <div className="text-center">
              <div className="text-sm text-muted-foreground">CTR Lift</div>
              <div className="text-2xl font-bold">
                {ctrScore?.did_lift_pct !== null && ctrScore?.did_lift_pct !== undefined
                  ? `${ctrScore.did_lift_pct >= 0 ? "+" : ""}${ctrScore.did_lift_pct.toFixed(1)}%`
                  : "--"}
              </div>
            </div>
            <div className="text-center">
              <div className="text-sm text-muted-foreground">CVR Lift</div>
              <div className="text-2xl font-bold">
                {cvrScore?.did_lift_pct !== null && cvrScore?.did_lift_pct !== undefined
                  ? `${cvrScore.did_lift_pct >= 0 ? "+" : ""}${cvrScore.did_lift_pct.toFixed(1)}%`
                  : "--"}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function PerformanceWindowsCard({ data }: { data: DetailData }) {
  const windows = [
    { label: "7-day", metrics: data.windows.d7 },
    { label: "14-day", metrics: data.windows.d14 },
    { label: "30-day", metrics: data.windows.d30 },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance Windows</CardTitle>
        <CardDescription>
          Baseline vs post-publish metrics at different intervals
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {windows.map(({ label, metrics }) => (
            <div key={label} className="space-y-3 p-4 rounded-lg border">
              <h4 className="font-semibold text-center">{label}</h4>

              {!metrics ? (
                <p className="text-center text-sm text-gray-400">No data</p>
              ) : !metrics.available ? (
                <p className="text-center text-sm text-gray-400 italic">
                  Pending ({metrics.pending_days}d)
                </p>
              ) : (
                <>
                  {/* CTR */}
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">
                      CTR
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        Baseline:{" "}
                        {data.baseline
                          ? formatCtr(data.baseline.avg_ctr)
                          : (
                              <Badge
                                variant="outline"
                                className="border-yellow-500 text-yellow-700 text-xs"
                              >
                                <AlertTriangle className="h-3 w-3 mr-1" />
                                No baseline
                              </Badge>
                            )}
                      </span>
                      <span className="font-medium">
                        {formatCtr(metrics.avg_ctr ?? 0)}
                      </span>
                    </div>
                    {metrics.ctr_delta !== undefined && (
                      <div
                        className={`text-sm font-medium flex items-center gap-1 ${
                          metrics.ctr_delta > 0
                            ? "text-green-600"
                            : metrics.ctr_delta < 0
                              ? "text-red-600"
                              : "text-gray-400"
                        }`}
                      >
                        {metrics.ctr_delta > 0 ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : metrics.ctr_delta < 0 ? (
                          <ArrowDown className="h-3 w-3" />
                        ) : null}
                        {formatDelta(metrics.ctr_delta)}
                      </div>
                    )}
                  </div>

                  {/* CVR */}
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">
                      CVR
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        Baseline:{" "}
                        {data.baseline
                          ? formatCtr(data.baseline.avg_cvr)
                          : "--"}
                      </span>
                      <span className="font-medium">
                        {formatCtr(metrics.avg_cvr ?? 0)}
                      </span>
                    </div>
                    {metrics.cvr_delta !== undefined && (
                      <div
                        className={`text-sm font-medium flex items-center gap-1 ${
                          metrics.cvr_delta > 0
                            ? "text-green-600"
                            : metrics.cvr_delta < 0
                              ? "text-red-600"
                              : "text-gray-400"
                        }`}
                      >
                        {metrics.cvr_delta > 0 ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : metrics.cvr_delta < 0 ? (
                          <ArrowDown className="h-3 w-3" />
                        ) : null}
                        {formatDelta(metrics.cvr_delta)}
                      </div>
                    )}
                  </div>

                  <div className="text-xs text-muted-foreground text-center">
                    {metrics.data_points} data point
                    {metrics.data_points !== 1 ? "s" : ""}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function SearchTermsCard({
  searchData,
}: {
  searchData: SearchTermsData | null
}) {
  const [showAllGained, setShowAllGained] = useState(false)
  const [showAllLost, setShowAllLost] = useState(false)

  if (!searchData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Search Terms</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Info className="h-4 w-4" />
            <span>Loading search term data...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (
    searchData.gained.length === 0 &&
    searchData.lost.length === 0
  ) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Search Terms</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground py-4">
            <Info className="h-4 w-4" />
            <span>
              No search term snapshots available for this publish event
            </span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const gainedToShow = showAllGained
    ? searchData.gained
    : searchData.gained.slice(0, 10)
  const lostToShow = showAllLost
    ? searchData.lost
    : searchData.lost.slice(0, 10)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search Terms</CardTitle>
        <CardDescription>
          Terms gained and lost after publish
          {searchData.pre_snapshot_date && searchData.post_snapshot_date && (
            <span className="ml-2 text-xs">
              (comparing {formatDate(searchData.pre_snapshot_date)} vs{" "}
              {formatDate(searchData.post_snapshot_date)})
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Terms Gained */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-4 w-4 text-green-600" />
              <h4 className="font-semibold text-green-700">
                Terms Gained ({searchData.gained.length})
              </h4>
            </div>
            {searchData.gained.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No gained terms
              </p>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Term</TableHead>
                      <TableHead className="text-right">Impr.</TableHead>
                      <TableHead className="text-right">Clicks</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gainedToShow.map((term) => (
                      <TableRow key={term.search_term}>
                        <TableCell className="text-sm">
                          <span className="flex items-center gap-1.5">
                            {term.search_term}
                            {term.is_new && (
                              <Badge className="bg-blue-100 text-blue-800 border-blue-300 text-xs px-1.5 py-0">
                                <Sparkles className="h-3 w-3 mr-0.5" />
                                New
                              </Badge>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="text-right text-green-600 font-medium">
                          +{term.impression_delta}
                        </TableCell>
                        <TableCell className="text-right text-green-600 font-medium">
                          +{term.click_delta}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {searchData.gained.length > 10 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => setShowAllGained(!showAllGained)}
                  >
                    {showAllGained
                      ? "Show top 10"
                      : `Show all (${searchData.gained.length})`}
                  </Button>
                )}
              </>
            )}
          </div>

          {/* Terms Lost */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingDown className="h-4 w-4 text-red-600" />
              <h4 className="font-semibold text-red-700">
                Terms Lost ({searchData.lost.length})
              </h4>
            </div>
            {searchData.lost.length === 0 ? (
              <p className="text-sm text-muted-foreground">No lost terms</p>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Term</TableHead>
                      <TableHead className="text-right">Impr.</TableHead>
                      <TableHead className="text-right">Clicks</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lostToShow.map((term) => (
                      <TableRow key={term.search_term}>
                        <TableCell className="text-sm">
                          {term.search_term}
                        </TableCell>
                        <TableCell className="text-right text-red-600 font-medium">
                          {term.impression_delta}
                        </TableCell>
                        <TableCell className="text-right text-red-600 font-medium">
                          {term.click_delta}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {searchData.lost.length > 10 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => setShowAllLost(!showAllLost)}
                  >
                    {showAllLost
                      ? "Show top 10"
                      : `Show all (${searchData.lost.length})`}
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function ControlCohortSection({ data }: { data: DetailData }) {
  const [open, setOpen] = useState(false)

  const ctrScore = data.impact_scores.find((s) => s.metric_name === "ctr")

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="cursor-pointer" onClick={() => setOpen(!open)}>
          <CollapsibleTrigger asChild>
            <div className="flex items-center justify-between w-full">
              <CardTitle className="text-base flex items-center gap-2">
                {open ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Methodology: Diff-in-Diff Control Cohort
              </CardTitle>
              <Badge variant="outline" className="text-xs">
                {data.control_skus.length} control SKU
                {data.control_skus.length !== 1 ? "s" : ""}
              </Badge>
            </div>
          </CollapsibleTrigger>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="space-y-4">
            {data.control_skus.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No control cohort data available
              </p>
            ) : (
              <>
                {/* Methodology explanation */}
                <div className="bg-muted/50 rounded-lg p-4 text-sm space-y-2">
                  <p>
                    <strong>Difference-in-Differences (DiD)</strong> compares
                    the change in metrics for the treated SKU against a control
                    group of similar, unpublished SKUs. This isolates the
                    effect of content changes from market-wide trends.
                  </p>
                  <p className="text-muted-foreground">
                    Lift = (Treated Post - Treated Pre) - (Control Post -
                    Control Pre)
                  </p>
                </div>

                {/* Raw numbers */}
                {ctrScore && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div className="p-3 rounded border">
                      <div className="text-xs text-muted-foreground">
                        Treated Pre
                      </div>
                      <div className="font-mono font-medium">
                        {ctrScore.pre_value !== null
                          ? formatCtr(ctrScore.pre_value)
                          : "--"}
                      </div>
                    </div>
                    <div className="p-3 rounded border">
                      <div className="text-xs text-muted-foreground">
                        Treated Post
                      </div>
                      <div className="font-mono font-medium">
                        {ctrScore.post_value !== null
                          ? formatCtr(ctrScore.post_value)
                          : "--"}
                      </div>
                    </div>
                    <div className="p-3 rounded border">
                      <div className="text-xs text-muted-foreground">
                        Control Pre
                      </div>
                      <div className="font-mono font-medium">
                        {ctrScore.control_pre !== null
                          ? formatCtr(ctrScore.control_pre)
                          : "--"}
                      </div>
                    </div>
                    <div className="p-3 rounded border">
                      <div className="text-xs text-muted-foreground">
                        Control Post
                      </div>
                      <div className="font-mono font-medium">
                        {ctrScore.control_post !== null
                          ? formatCtr(ctrScore.control_post)
                          : "--"}
                      </div>
                    </div>
                  </div>
                )}

                {/* Control SKU table */}
                <div>
                  <h5 className="text-sm font-medium mb-2">
                    Control SKUs Used
                  </h5>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead className="text-right">Avg CTR</TableHead>
                        <TableHead className="text-right">Avg CVR</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.control_skus.map((cs) => (
                        <TableRow key={cs.master_sku}>
                          <TableCell className="font-mono text-sm">
                            {cs.master_sku}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {cs.product_category ?? "--"}
                          </TableCell>
                          <TableCell className="text-right">
                            {cs.avg_ctr !== null
                              ? formatCtr(cs.avg_ctr)
                              : "--"}
                          </TableCell>
                          <TableCell className="text-right">
                            {cs.avg_cvr !== null
                              ? formatCtr(cs.avg_cvr)
                              : "--"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

function PublishHistorySection({
  data,
  currentEventId,
}: {
  data: DetailData
  currentEventId: number
}) {
  const [open, setOpen] = useState(false)
  const router = useRouter()

  // Only show if there are multiple publish events
  if (data.publish_history.length <= 1) {
    return null
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="cursor-pointer" onClick={() => setOpen(!open)}>
          <CollapsibleTrigger asChild>
            <div className="flex items-center justify-between w-full">
              <CardTitle className="text-base flex items-center gap-2">
                {open ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Publish History ({data.publish_history.length} events)
              </CardTitle>
            </div>
          </CollapsibleTrigger>
        </CardHeader>
        <CollapsibleContent>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Published</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Impact</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.publish_history.map((entry) => (
                  <TableRow
                    key={entry.publish_event_id}
                    className={
                      entry.publish_event_id === currentEventId
                        ? "bg-muted/50"
                        : "cursor-pointer hover:bg-muted/30"
                    }
                    onClick={() => {
                      if (entry.publish_event_id !== currentEventId) {
                        router.push(
                          `/content-impact/${encodeURIComponent(data.master_sku)}?event_id=${entry.publish_event_id}`
                        )
                      }
                    }}
                  >
                    <TableCell className="text-sm">
                      {formatDateTime(entry.published_at)}
                    </TableCell>
                    <TableCell>
                      {entry.prompt_hash ? (
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {entry.prompt_hash.slice(0, 8)}
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
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={`text-xs ${tierColor(entry.impact_tier)}`}
                      >
                        {entry.impact_label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {entry.publish_event_id === currentEventId && (
                        <Badge variant="secondary" className="text-xs">
                          Current
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-16 w-full" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ContentImpactDetailPage() {
  const routeParams = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()

  const sku = routeParams.sku as string
  const eventId = searchParams.get("event_id")

  const [detail, setDetail] = useState<DetailData | null>(null)
  const [searchTerms, setSearchTerms] = useState<SearchTermsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const detailUrl = eventId
        ? `/api/content-impact/${encodeURIComponent(sku)}?event_id=${eventId}`
        : `/api/content-impact/${encodeURIComponent(sku)}`

      const detailRes = await fetch(detailUrl)
      if (!detailRes.ok) {
        const body = await detailRes.json().catch(() => ({}))
        throw new Error(body.error || `HTTP ${detailRes.status}`)
      }
      const detailData: DetailData = await detailRes.json()
      setDetail(detailData)

      // Fetch search terms in parallel (needs event_id from detail response)
      const termsRes = await fetch(
        `/api/content-impact/${encodeURIComponent(sku)}/search-terms?event_id=${detailData.publish_event_id}`
      )
      if (termsRes.ok) {
        const termsData: SearchTermsData = await termsRes.json()
        setSearchTerms(termsData)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }, [sku, eventId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/content-impact")}
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Content Impact
        </Button>
        <DetailSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/content-impact")}
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Content Impact
        </Button>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="flex items-center gap-2">
            {error}
            <Button variant="outline" size="sm" onClick={fetchData}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!detail) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/content-impact")}
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Content Impact
      </Button>

      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-mono">
            {detail.master_sku}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <PlatformBadge
              platform={detail.platform as "google" | "bing" | "shopify"}
            />
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-sm text-muted-foreground">
                    Published {formatDate(detail.published_at)}
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{formatDateTime(detail.published_at)}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {detail.prompt_hash ? (
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                {detail.prompt_hash.slice(0, 8)}
              </code>
            ) : (
              <Badge variant="secondary" className="text-gray-500 text-xs">
                Legacy
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Impact Summary */}
      <ImpactSummaryCard data={detail} />

      {/* Performance Windows */}
      <PerformanceWindowsCard data={detail} />

      {/* Search Terms */}
      <SearchTermsCard searchData={searchTerms} />

      {/* Control Cohort */}
      <ControlCohortSection data={detail} />

      {/* Publish History (only for re-published SKUs) */}
      <PublishHistorySection
        data={detail}
        currentEventId={detail.publish_event_id}
      />
    </div>
  )
}
