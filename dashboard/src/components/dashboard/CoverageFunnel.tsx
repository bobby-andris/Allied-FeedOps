'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  ChevronDown,
  ChevronRight,
  Package,
  Sparkles,
  CheckCircle,
  SendHorizonal,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react'

// ─── Types ──────────────────────────────────────────────────────────────────

interface ConfirmedSample {
  checked: number
  matched: number
  last_run: string | null
}

interface FunnelData {
  total_catalog: number
  has_generated: number
  approved: number
  published: number
  confirmed_sample: ConfirmedSample | null
}

interface SkuRow {
  master_sku: string
  detail?: string
}

interface SkuListState {
  loading: boolean
  skus: SkuRow[]
  total: number
  offset: number
  hasMore: boolean
}

type StageKey = 'total_catalog' | 'has_generated' | 'approved' | 'published'

interface FunnelStage {
  key: StageKey | 'confirmed'
  label: string
  icon: React.ReactNode
  count: number | null
  isClickable: boolean
}

const PAGE_SIZE = 50

// ─── Utilities ───────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

function calcDropoff(from: number, to: number): { pct: string; delta: string } {
  if (from === 0) return { pct: '—', delta: '—' }
  const delta = from - to
  const pct = ((delta / from) * 100).toFixed(1)
  return {
    pct: `${pct}% drop`,
    delta: `-${formatCount(delta)}`,
  }
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function DropoffIndicator({ from, to }: { from: number; to: number }) {
  const { pct, delta } = calcDropoff(from, to)
  const severity = from > 0 ? (to / from) : 1
  const color =
    severity >= 0.8
      ? 'text-green-600'
      : severity >= 0.5
      ? 'text-yellow-600'
      : 'text-red-500'

  return (
    <div className="flex flex-col items-center py-1 select-none">
      <ChevronDown className={`h-4 w-4 ${color}`} />
      <span className={`text-xs font-medium ${color}`}>
        {delta} ({pct})
      </span>
    </div>
  )
}

function SkuList({
  stageKey,
  initialTotal,
}: {
  stageKey: StageKey
  initialTotal: number
}) {
  const [state, setState] = useState<SkuListState>({
    loading: true,
    skus: [],
    total: initialTotal,
    offset: 0,
    hasMore: false,
  })

  async function loadSkus(offset: number, append = false) {
    setState((prev) => ({ ...prev, loading: true }))
    try {
      const res = await fetch(
        `/api/funnel/skus?stage=${stageKey}&limit=${PAGE_SIZE}&offset=${offset}`
      )
      if (!res.ok) throw new Error('Failed to load SKUs')
      const data = await res.json()
      setState((prev) => ({
        loading: false,
        skus: append ? [...prev.skus, ...data.skus] : data.skus,
        total: data.total,
        offset: offset + data.skus.length,
        hasMore: offset + data.skus.length < data.total,
      }))
    } catch {
      setState((prev) => ({ ...prev, loading: false }))
    }
  }

  useEffect(() => {
    loadSkus(0)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stageKey])

  return (
    <div className="mt-2 border rounded-md bg-muted/30 overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 text-xs font-semibold text-muted-foreground border-b bg-muted/50 flex justify-between">
        <span>
          Showing {state.skus.length} of {formatCount(state.total)} SKUs
        </span>
      </div>

      {/* SKU rows */}
      <div className="max-h-64 overflow-y-auto divide-y">
        {state.loading && state.skus.length === 0 ? (
          <div className="p-3 space-y-2">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-5 w-full" />
            ))}
          </div>
        ) : state.skus.length === 0 ? (
          <p className="px-3 py-4 text-sm text-muted-foreground text-center">
            No SKUs found
          </p>
        ) : (
          state.skus.map((row) => (
            <div
              key={row.master_sku}
              className="px-3 py-1.5 flex items-center justify-between text-sm hover:bg-muted/50 transition-colors"
            >
              <span className="font-mono text-xs font-medium">{row.master_sku}</span>
              {row.detail && (
                <span className="text-xs text-muted-foreground ml-2">{row.detail}</span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Load more */}
      {state.hasMore && (
        <div className="border-t px-3 py-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs w-full"
            onClick={() => loadSkus(state.offset, true)}
            disabled={state.loading}
          >
            {state.loading ? (
              <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
            ) : null}
            Load more ({formatCount(state.total - state.offset)} remaining)
          </Button>
        </div>
      )}
    </div>
  )
}

function FunnelStageCard({
  stage,
  isExpanded,
  onToggle,
}: {
  stage: FunnelStage
  isExpanded: boolean
  onToggle: () => void
}) {
  const isClickable = stage.isClickable && stage.count !== null

  return (
    <div className="flex-1 min-w-0">
      <button
        className={`w-full text-left rounded-lg border px-4 py-3 transition-colors ${
          isClickable
            ? 'cursor-pointer hover:bg-muted/50 hover:border-primary/30'
            : 'cursor-default'
        } ${isExpanded ? 'bg-muted/40 border-primary/30' : 'bg-card'}`}
        onClick={isClickable ? onToggle : undefined}
        disabled={!isClickable}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-muted-foreground shrink-0">{stage.icon}</span>
            <span className="text-sm font-medium truncate">{stage.label}</span>
          </div>
          {isClickable && (
            <span className="shrink-0 text-muted-foreground">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </span>
          )}
        </div>
        <div className="mt-1">
          {stage.count === null ? (
            <span className="text-sm text-muted-foreground italic">Not yet checked</span>
          ) : (
            <span className="text-2xl font-bold tabular-nums">
              {formatCount(stage.count)}
            </span>
          )}
        </div>
      </button>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function CoverageFunnel() {
  const [funnel, setFunnel] = useState<FunnelData | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedStage, setExpandedStage] = useState<StageKey | null>(null)

  useEffect(() => {
    async function fetchFunnel() {
      try {
        const res = await fetch('/api/funnel/summary')
        if (!res.ok) throw new Error('Failed to load funnel data')
        const data = await res.json()
        setFunnel(data.funnel)
        setGeneratedAt(data.generated_at)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }
    fetchFunnel()
  }, [])

  function toggleStage(key: StageKey) {
    setExpandedStage((prev) => (prev === key ? null : key))
  }

  // Build ordered stages for rendering
  const stages: FunnelStage[] = funnel
    ? [
        {
          key: 'total_catalog',
          label: 'Total Catalog',
          icon: <Package className="h-4 w-4" />,
          count: funnel.total_catalog,
          isClickable: true,
        },
        {
          key: 'has_generated',
          label: 'Generated',
          icon: <Sparkles className="h-4 w-4" />,
          count: funnel.has_generated,
          isClickable: true,
        },
        {
          key: 'approved',
          label: 'Approved',
          icon: <CheckCircle className="h-4 w-4" />,
          count: funnel.approved,
          isClickable: true,
        },
        {
          key: 'published',
          label: 'Published',
          icon: <SendHorizonal className="h-4 w-4" />,
          count: funnel.published,
          isClickable: true,
        },
        {
          key: 'confirmed',
          label: 'Confirmed in Sheets',
          icon: <ShieldCheck className="h-4 w-4" />,
          count: funnel.confirmed_sample
            ? funnel.confirmed_sample.matched
            : null,
          isClickable: false,
        },
      ]
    : []

  // Stage pairs for drop-off indicators (between consecutive clickable stages)
  const dropoffPairs: Array<{ from: number; to: number }> = funnel
    ? [
        { from: funnel.total_catalog, to: funnel.has_generated },
        { from: funnel.has_generated, to: funnel.approved },
        { from: funnel.approved, to: funnel.published },
      ]
    : []

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">SKU Coverage Funnel</CardTitle>
          {generatedAt && !loading && (
            <span className="text-xs text-muted-foreground">
              Updated {new Date(generatedAt).toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
              })}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex gap-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex-1">
                <Skeleton className="h-20 w-full rounded-lg" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3">
            <p className="text-sm text-red-700">Failed to load funnel: {error}</p>
          </div>
        ) : funnel ? (
          <div>
            {/* Funnel stages — horizontal on desktop, vertical on mobile */}
            <div className="flex flex-col lg:flex-row lg:items-start gap-0">
              {stages.map((stage, idx) => (
                <div key={stage.key} className="flex flex-col lg:flex-row lg:items-center flex-1 min-w-0">
                  {/* Stage card */}
                  <FunnelStageCard
                    stage={stage}
                    isExpanded={expandedStage === stage.key}
                    onToggle={() =>
                      stage.isClickable && stage.key !== 'confirmed'
                        ? toggleStage(stage.key as StageKey)
                        : undefined
                    }
                  />

                  {/* Drop-off indicator between stages (not after last) */}
                  {idx < stages.length - 1 && dropoffPairs[idx] && (
                    <div className="flex lg:flex-col items-center justify-center px-1 py-1 shrink-0">
                      <DropoffIndicator
                        from={dropoffPairs[idx].from}
                        to={dropoffPairs[idx].to}
                      />
                    </div>
                  )}

                  {/* After last stage, show confirmed_sample note if null */}
                  {idx === stages.length - 1 && stage.count === null && (
                    <div className="hidden" />
                  )}
                </div>
              ))}
            </div>

            {/* Confirmed sample detail */}
            {funnel.confirmed_sample && (
              <div className="mt-3 flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">
                  Spot-check: {funnel.confirmed_sample.matched}/{funnel.confirmed_sample.checked} matched
                </Badge>
                {funnel.confirmed_sample.last_run && (
                  <span className="text-xs text-muted-foreground">
                    Last run:{' '}
                    {new Date(funnel.confirmed_sample.last_run).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                )}
              </div>
            )}

            {!funnel.confirmed_sample && (
              <p className="mt-3 text-xs text-muted-foreground italic">
                Confirmed in Sheets stage: spot-check not yet run (DIAG-04 pending)
              </p>
            )}

            {/* Expandable SKU list */}
            {expandedStage && (
              <div className="mt-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-medium">
                    {stages.find((s) => s.key === expandedStage)?.label} SKUs
                  </span>
                  <Badge variant="outline" className="text-xs">
                    {formatCount(
                      expandedStage === 'total_catalog'
                        ? funnel.total_catalog
                        : expandedStage === 'has_generated'
                        ? funnel.has_generated
                        : expandedStage === 'approved'
                        ? funnel.approved
                        : funnel.published
                    )}{' '}
                    total
                  </Badge>
                </div>
                <SkuList
                  stageKey={expandedStage}
                  initialTotal={
                    expandedStage === 'total_catalog'
                      ? funnel.total_catalog
                      : expandedStage === 'has_generated'
                      ? funnel.has_generated
                      : expandedStage === 'approved'
                      ? funnel.approved
                      : funnel.published
                  }
                />
              </div>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
