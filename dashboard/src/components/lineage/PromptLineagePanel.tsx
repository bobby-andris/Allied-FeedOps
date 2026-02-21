'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, GitBranch, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'

interface FlagState {
  PROMPT_CONTRACT_V2: boolean
  INTENT_CURATOR_V1: boolean
  SEGMENT_STRATEGY_V1: boolean
}

interface LineageEntry {
  prompt_hash: string
  prompt_alias: string | null
  model_version: string | null
  feature_flags: FlagState | null
  tokens_used: number | null
  latency_ms: number | null
  quality_score: number | null
  published_at: string | null
  generated_at: string | null
}

interface LineageResponse {
  lineage: LineageEntry | null
  note?: string
  compare?: {
    hash_a: LineageEntry | null
    hash_b: LineageEntry | null
  }
}

interface PromptLineagePanelProps {
  masterSku: string
  platform: string
}

function FlagBadge({ name, active }: { name: string; active: boolean }) {
  return (
    <Badge className={active ? 'bg-green-100 text-green-800 hover:bg-green-100' : 'bg-gray-100 text-gray-500 hover:bg-gray-100'}>
      {name}
    </Badge>
  )
}

function LineageCard({ entry }: { entry: LineageEntry }) {
  const shortHash = entry.prompt_hash.slice(0, 8)
  const flags = entry.feature_flags

  return (
    <div className="space-y-3 text-sm">
      {/* Hash + alias */}
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <span className="text-xs text-muted-foreground">Prompt Hash</span>
          <div
            className="font-mono font-semibold"
            title={entry.prompt_hash}
          >
            {shortHash}
          </div>
        </div>
        {entry.prompt_alias && (
          <div>
            <span className="text-xs text-muted-foreground">Alias</span>
            <div className="font-semibold">{entry.prompt_alias}</div>
          </div>
        )}
        {entry.model_version && (
          <div>
            <span className="text-xs text-muted-foreground">Model</span>
            <div>{entry.model_version}</div>
          </div>
        )}
        {entry.quality_score !== null && (
          <div>
            <span className="text-xs text-muted-foreground">Quality</span>
            <div className="font-semibold">{entry.quality_score}/100</div>
          </div>
        )}
      </div>

      {/* Feature flags */}
      {flags && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">Feature Flags</span>
          <div className="flex gap-2 flex-wrap">
            <FlagBadge name="CONTRACT_V2" active={flags.PROMPT_CONTRACT_V2} />
            <FlagBadge name="INTENT_V1" active={flags.INTENT_CURATOR_V1} />
            <FlagBadge name="SEGMENT_V1" active={flags.SEGMENT_STRATEGY_V1} />
          </div>
        </div>
      )}

      {/* Cost + timing */}
      <div className="flex gap-4 flex-wrap text-xs text-muted-foreground">
        {entry.tokens_used !== null && (
          <span>Tokens: <span className="font-medium text-foreground">{entry.tokens_used.toLocaleString()}</span></span>
        )}
        {entry.latency_ms !== null && (
          <span>Latency: <span className="font-medium text-foreground">{(entry.latency_ms / 1000).toFixed(1)}s</span></span>
        )}
        {entry.published_at && (
          <span>Published: <span className="font-medium text-foreground">{new Date(entry.published_at).toLocaleDateString()}</span></span>
        )}
        {entry.generated_at && (
          <span>Generated: <span className="font-medium text-foreground">{new Date(entry.generated_at).toLocaleDateString()}</span></span>
        )}
      </div>
    </div>
  )
}


export function PromptLineagePanel({ masterSku, platform }: PromptLineagePanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [data, setData] = useState<LineageResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [showCompare, setShowCompare] = useState(false)
  const [compareHashA, setCompareHashA] = useState('')
  const [compareHashB, setCompareHashB] = useState('')
  const [compareData, setCompareData] = useState<LineageResponse | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  // Fetch on expand
  useEffect(() => {
    if (!isOpen || data) return
    setLoading(true)
    fetch(`/api/prompt-lineage?master_sku=${encodeURIComponent(masterSku)}&platform=${encodeURIComponent(platform)}`)
      .then((r) => r.json())
      .then((json) => setData(json))
      .catch(() => setData({ lineage: null, note: 'Failed to load lineage data.' }))
      .finally(() => setLoading(false))
  }, [isOpen, data, masterSku, platform])

  const handleCompare = async () => {
    if (!compareHashA || !compareHashB) return
    setCompareLoading(true)
    try {
      const res = await fetch(
        `/api/prompt-lineage?master_sku=${encodeURIComponent(masterSku)}&platform=${encodeURIComponent(platform)}&compare=true&hash_a=${encodeURIComponent(compareHashA)}&hash_b=${encodeURIComponent(compareHashB)}`
      )
      const json = await res.json()
      setCompareData(json)
    } catch {
      setCompareData({ lineage: null, note: 'Failed to load comparison data.' })
    } finally {
      setCompareLoading(false)
    }
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors py-1"
          type="button"
        >
          <GitBranch className="h-3.5 w-3.5" />
          Prompt Lineage
          {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="mt-2 border rounded-lg p-4 bg-muted/30 space-y-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading lineage data...
            </div>
          )}

          {!loading && data && (
            <>
              {data.lineage ? (
                <LineageCard entry={data.lineage} />
              ) : (
                <p className="text-sm text-muted-foreground">
                  {data.note ?? 'Lineage tracking not available for this publish event.'}
                </p>
              )}

              {/* Opt-in Compare Versions */}
              {!showCompare ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCompare(true)}
                  className="mt-2"
                >
                  Compare Versions
                </Button>
              ) : (
                <div className="border-t pt-4 space-y-3">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Compare Two Prompt Versions
                  </p>
                  <div className="flex gap-2 items-end flex-wrap">
                    <div className="flex-1 min-w-[140px]">
                      <label className="text-xs text-muted-foreground block mb-1">Hash A (8-char prefix)</label>
                      <input
                        type="text"
                        className="w-full border rounded px-2 py-1 text-sm font-mono"
                        placeholder="e.g. a1b2c3d4"
                        value={compareHashA}
                        onChange={(e) => setCompareHashA(e.target.value)}
                        maxLength={64}
                      />
                    </div>
                    <div className="flex-1 min-w-[140px]">
                      <label className="text-xs text-muted-foreground block mb-1">Hash B (8-char prefix)</label>
                      <input
                        type="text"
                        className="w-full border rounded px-2 py-1 text-sm font-mono"
                        placeholder="e.g. e5f6a7b8"
                        value={compareHashB}
                        onChange={(e) => setCompareHashB(e.target.value)}
                        maxLength={64}
                      />
                    </div>
                    <Button
                      size="sm"
                      onClick={handleCompare}
                      disabled={!compareHashA || !compareHashB || compareLoading}
                    >
                      {compareLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Compare'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { setShowCompare(false); setCompareData(null) }}
                    >
                      Cancel
                    </Button>
                  </div>

                  {compareData && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
                      <div className="border rounded p-3">
                        <p className="text-xs font-medium text-muted-foreground mb-2">Version A</p>
                        {compareData.compare?.hash_a ? (
                          <LineageCard entry={compareData.compare.hash_a} />
                        ) : (
                          <p className="text-sm text-muted-foreground">No data for hash A</p>
                        )}
                      </div>
                      <div className="border rounded p-3">
                        <p className="text-xs font-medium text-muted-foreground mb-2">Version B</p>
                        {compareData.compare?.hash_b ? (
                          <LineageCard entry={compareData.compare.hash_b} />
                        ) : (
                          <p className="text-sm text-muted-foreground">No data for hash B</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
