'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { ChevronDown, ChevronUp, RefreshCw, ArrowLeft, AlertCircle, Loader2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import Link from 'next/link'
import { BottleneckBadge } from '@/components/bottleneck/BottleneckBadge'

interface Classification {
  master_sku: string
  classification: string
  confidence: number
  classified_at: string
  is_override: boolean
  override_by: string | null
  override_note: string | null
  evidence: Record<string, unknown> | null
}

interface StatusResponse {
  classifications: Classification[]
  total_count: number
  by_category: Record<string, number>
}

const CATEGORY_ORDER = [
  'coverage_gap',
  'code_path_gap',
  'propagation_failure',
  'query_relevance',
  'auction_bid',
]

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  coverage_gap: 'No generated content exists for these SKUs',
  code_path_gap: 'Content exists but was never published',
  propagation_failure: 'Published but still showing 0 impressions after 7+ days',
  query_relevance: 'Published SKUs with poor keyword coverage in titles',
  auction_bid: 'All other signals clear — likely bid/auction competition',
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString()
}

function OverrideForm({
  masterSku,
  onSuccess,
  onCancel,
}: {
  masterSku: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const [classification, setClassification] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async () => {
    if (!classification) {
      setError('Please select a classification')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(
        `/api/bottleneck/classify?master_sku=${encodeURIComponent(masterSku)}&override_classification=${encodeURIComponent(classification)}&override_note=${encodeURIComponent(note)}&override_by=user`,
        { method: 'POST' }
      )
      if (!res.ok) throw new Error('Override failed')
      onSuccess()
    } catch {
      setError('Failed to save override. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-2 p-3 border rounded bg-muted/20 space-y-3">
      <p className="text-xs font-medium">Override Classification</p>
      <div className="flex gap-2 flex-wrap items-end">
        <div className="flex-1 min-w-[180px]">
          <label className="text-xs text-muted-foreground block mb-1">New Classification</label>
          <select
            className="w-full border rounded px-2 py-1 text-sm"
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
          >
            <option value="">Select...</option>
            <option value="coverage_gap">Coverage Gap</option>
            <option value="code_path_gap">Code Path Gap</option>
            <option value="propagation_failure">Propagation Failure</option>
            <option value="query_relevance">Query Relevance</option>
            <option value="auction_bid">Auction/Bid</option>
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs text-muted-foreground block mb-1">Note (optional)</label>
          <input
            type="text"
            className="w-full border rounded px-2 py-1 text-sm"
            placeholder="Why are you overriding this?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <Button size="sm" onClick={handleSubmit} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save Override'}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}

function CategorySection({
  category,
  items,
  onRefresh,
}: {
  category: string
  items: Classification[]
  onRefresh: () => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [reclassifying, setReclassifying] = useState<string | null>(null)
  const [overriding, setOverriding] = useState<string | null>(null)

  const handleReclassify = async (masterSku: string) => {
    setReclassifying(masterSku)
    try {
      await fetch(`/api/bottleneck/classify?master_sku=${encodeURIComponent(masterSku)}`, { method: 'POST' })
      onRefresh()
    } catch {
      // silent fail — will show stale data
    } finally {
      setReclassifying(null)
    }
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-accent/50 rounded-lg transition-colors">
          <div className="flex items-center gap-3">
            <BottleneckBadge classification={category} />
            <span className="text-sm text-muted-foreground">{CATEGORY_DESCRIPTIONS[category]}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{items.length} SKUs</Badge>
            {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </div>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="px-4 pb-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="text-left py-2 pr-4">SKU</th>
                <th className="text-left py-2 pr-4">Confidence</th>
                <th className="text-left py-2 pr-4">Classified</th>
                <th className="text-left py-2 pr-4">Source</th>
                <th className="text-left py-2 pr-4">Evidence</th>
                <th className="text-left py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.master_sku} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-mono font-medium">{item.master_sku}</td>
                  <td className="py-2 pr-4">{Math.round(item.confidence * 100)}%</td>
                  <td className="py-2 pr-4 text-muted-foreground">{formatDate(item.classified_at)}</td>
                  <td className="py-2 pr-4">
                    {item.is_override ? (
                      <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                        Override{item.override_by ? ` by ${item.override_by}` : ''}
                      </Badge>
                    ) : (
                      <Badge variant="outline">Auto</Badge>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-xs text-muted-foreground max-w-[240px] truncate">
                    {item.evidence
                      ? Object.entries(item.evidence)
                          .filter(([, v]) => v !== null && v !== false)
                          .map(([k, v]) => `${k}: ${v}`)
                          .slice(0, 2)
                          .join(' • ')
                      : '—'}
                    {item.override_note && (
                      <span className="italic ml-1">{item.override_note}</span>
                    )}
                  </td>
                  <td className="py-2">
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleReclassify(item.master_sku)}
                        disabled={reclassifying === item.master_sku}
                      >
                        {reclassifying === item.master_sku ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          'Reclassify'
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setOverriding(overriding === item.master_sku ? null : item.master_sku)}
                      >
                        Override
                      </Button>
                    </div>
                    {overriding === item.master_sku && (
                      <OverrideForm
                        masterSku={item.master_sku}
                        onSuccess={() => {
                          setOverriding(null)
                          onRefresh()
                        }}
                        onCancel={() => setOverriding(null)}
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export default function BottleneckPage() {
  const [data, setData] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [reclassifyingAll, setReclassifyingAll] = useState(false)
  const [reclassifyResult, setReclassifyResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/bottleneck/status?limit=500')
      if (!res.ok) throw new Error('Failed to fetch bottleneck status')
      const json = await res.json()
      setData(json)
    } catch {
      setError('Failed to load bottleneck classifications. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleReclassifyAll = async () => {
    setReclassifyingAll(true)
    setReclassifyResult(null)
    try {
      const res = await fetch('/api/bottleneck/classify?batch=true', { method: 'POST' })
      if (!res.ok) throw new Error('Batch reclassify failed')
      const json = await res.json()
      setReclassifyResult(
        `Reclassified ${json.results?.length ?? 0} SKUs successfully`
      )
      await fetchData()
    } catch {
      setReclassifyResult('Batch reclassify failed. Please try again.')
    } finally {
      setReclassifyingAll(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // Group classifications by category
  const byCategory: Record<string, Classification[]> = {}
  if (data) {
    for (const item of data.classifications) {
      if (!byCategory[item.classification]) byCategory[item.classification] = []
      byCategory[item.classification].push(item)
    }
  }

  const totalClassified = data?.total_count ?? 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href="/monitoring"
              className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Monitoring
            </Link>
          </div>
          <h1 className="text-3xl font-bold">Bottleneck Diagnostics</h1>
          <p className="text-muted-foreground mt-1">
            SKUs grouped by root cause classification — identify what&apos;s blocking each SKU from performing
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" onClick={fetchData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={handleReclassifyAll} disabled={reclassifyingAll || loading}>
            {reclassifyingAll ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Reclassify All
          </Button>
        </div>
      </div>

      {reclassifyResult && (
        <Alert>
          <AlertDescription>{reclassifyResult}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Summary bar */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {CATEGORY_ORDER.map((cat) => (
            <Skeleton key={cat} className="h-24 w-full" />
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {CATEGORY_ORDER.map((cat) => {
            const count = data.by_category[cat] ?? 0
            const pct = totalClassified > 0 ? Math.round((count / totalClassified) * 100) : 0
            return (
              <Card key={cat} className="text-center">
                <CardContent className="pt-4 pb-3 px-3">
                  <div className="text-2xl font-bold mb-1">{count}</div>
                  <BottleneckBadge classification={cat} className="justify-center mb-1" />
                  <div className="text-xs text-muted-foreground">{pct}% of total</div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : null}

      {/* Category sections */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : !data || data.classifications.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No classifications found.</p>
            <p className="text-sm text-muted-foreground mt-2">
              Click &quot;Reclassify All&quot; to run the bottleneck classifier across all SKUs with generated content.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>SKUs by Bottleneck Category</CardTitle>
            <CardDescription>
              {totalClassified} SKU{totalClassified !== 1 ? 's' : ''} classified — click a category to expand and manage individual SKUs
            </CardDescription>
          </CardHeader>
          <CardContent className="divide-y">
            {CATEGORY_ORDER.filter((cat) => (byCategory[cat]?.length ?? 0) > 0).map((cat) => (
              <CategorySection
                key={cat}
                category={cat}
                items={byCategory[cat] ?? []}
                onRefresh={fetchData}
              />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
