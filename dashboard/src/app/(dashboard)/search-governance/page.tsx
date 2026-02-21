'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type DateRangePreset = '7d' | '30d' | '60d' | '90d'

const DATE_RANGE_OPTIONS: Array<{ value: DateRangePreset; label: string }> = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '60d', label: 'Last 60 days' },
  { value: '90d', label: 'Last 90 days' },
]

interface CandidateResponse {
  candidate_count: number
  cluster_summaries?: Array<{
    cluster_key: string
    suggested_campaign: string
    suggested_ad_group: string
    recommended_tier: 'broad' | 'phrase' | 'exact'
    candidate_count: number
    avg_confidence: number
    avg_priority_score: number
    top_terms: string[]
  }>
  candidates: Array<{
    search_term: string
    current_tier: 'broad' | 'phrase' | 'exact'
    custom_label_0s: Array<{ custom_label_0: string }>
    metrics: {
      impressions?: number
      clicks?: number
      conversions?: number
      conversionsValue?: number
      costMicros?: number
    }
    governance: {
      action: string
      recommendedTier: 'broad' | 'phrase' | 'exact' | null
      confidence: number
      reasonCodes: string[]
    }
    route_decision: {
      classification: {
        intentClass: string
      }
    }
    buildout?: {
      cluster_key: string
      suggested_campaign: string
      suggested_ad_group: string
      recommended_tier?: 'broad' | 'phrase' | 'exact'
      priority_score?: number
    }
  }>
}

export default function SearchGovernancePage() {
  const [range, setRange] = useState<DateRangePreset>('30d')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [generatingDrafts, setGeneratingDrafts] = useState(false)
  const [evaluatingMovements, setEvaluatingMovements] = useState(false)
  const [applying, setApplying] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [candidateData, setCandidateData] = useState<CandidateResponse | null>(null)
  const [selected, setSelected] = useState<Record<string, boolean>>({})

  const selectedCandidates = useMemo(
    () =>
      (candidateData?.candidates ?? []).filter((candidate) => selected[candidate.search_term]),
    [candidateData?.candidates, selected]
  )

  const buildoutBriefs = useMemo(() => {
    const persistedBriefs = candidateData?.cluster_summaries ?? []
    if (persistedBriefs.length > 0) {
      return persistedBriefs
    }

    const byCluster = new Map<
      string,
      {
        cluster_key: string
        suggested_campaign: string
        suggested_ad_group: string
        recommended_tier: 'broad' | 'phrase' | 'exact'
        candidate_count: number
        confidenceTotal: number
        priorityTotal: number
        top_terms: string[]
      }
    >()

    for (const candidate of candidateData?.candidates ?? []) {
      if (!candidate.buildout?.cluster_key) continue
      const current = byCluster.get(candidate.buildout.cluster_key) ?? {
        cluster_key: candidate.buildout.cluster_key,
        suggested_campaign: candidate.buildout.suggested_campaign,
        suggested_ad_group: candidate.buildout.suggested_ad_group,
        recommended_tier: candidate.buildout.recommended_tier ?? candidate.governance.recommendedTier ?? 'phrase',
        candidate_count: 0,
        confidenceTotal: 0,
        priorityTotal: 0,
        top_terms: [],
      }

      current.candidate_count += 1
      current.confidenceTotal += candidate.governance.confidence
      current.priorityTotal += Number(candidate.buildout.priority_score ?? 0)
      if (!current.top_terms.includes(candidate.search_term)) {
        current.top_terms.push(candidate.search_term)
      }
      byCluster.set(candidate.buildout.cluster_key, current)
    }

    return Array.from(byCluster.values())
      .map((entry) => ({
        cluster_key: entry.cluster_key,
        suggested_campaign: entry.suggested_campaign,
        suggested_ad_group: entry.suggested_ad_group,
        recommended_tier: entry.recommended_tier,
        candidate_count: entry.candidate_count,
        avg_confidence: entry.candidate_count > 0 ? entry.confidenceTotal / entry.candidate_count : 0,
        avg_priority_score: entry.candidate_count > 0 ? entry.priorityTotal / entry.candidate_count : 0,
        top_terms: entry.top_terms.slice(0, 10),
      }))
      .sort((a, b) => b.avg_priority_score - a.avg_priority_score)
      .slice(0, 12)
  }, [candidateData])

  const loadCandidates = useCallback(async () => {
    const response = await fetch(`/api/search/governance/candidates?range=${range}&limit=600`)
    if (!response.ok) {
      throw new Error(await response.text())
    }
    const payload = (await response.json()) as CandidateResponse
    setCandidateData(payload)
    setSelected(Object.fromEntries(payload.candidates.map((candidate) => [candidate.search_term, false])))
  }, [range])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setErrorMessage(null)
    try {
      await loadCandidates()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch Search governance candidates')
    } finally {
      setRefreshing(false)
    }
  }, [loadCandidates])

  useEffect(() => {
    setLoading(true)
    setErrorMessage(null)
    setMessage(null)
    void loadCandidates()
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch Search governance candidates')
      })
      .finally(() => setLoading(false))
  }, [loadCandidates])

  const generateDrafts = async () => {
    setGeneratingDrafts(true)
    setErrorMessage(null)
    setMessage(null)
    try {
      const response = await fetch('/api/search/governance/drafts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          range,
          limit: 600,
          created_by: 'dashboard:search-governance',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const payload = (await response.json()) as {
        drafted_count: number
        eligible_count: number
        warnings?: string[]
      }
      setMessage(
        `Generated ${payload.drafted_count.toLocaleString()} draft candidate(s) from ${payload.eligible_count.toLocaleString()} eligible terms.`
      )
      if (payload.warnings && payload.warnings.length > 0) {
        setErrorMessage(payload.warnings.join(' | '))
      }

      await loadCandidates()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to generate Search governance drafts')
    } finally {
      setGeneratingDrafts(false)
    }
  }

  const toggleAll = (value: boolean) => {
    const terms = candidateData?.candidates ?? []
    setSelected(Object.fromEntries(terms.map((candidate) => [candidate.search_term, value])))
  }

  const applySelected = async () => {
    if (selectedCandidates.length === 0) {
      setErrorMessage('Select at least one candidate before applying.')
      return
    }

    setApplying(true)
    setErrorMessage(null)
    setMessage(null)
    try {
      const response = await fetch('/api/search/governance/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidates: selectedCandidates.map((candidate) => ({
            search_term: candidate.search_term,
            custom_label_0: candidate.custom_label_0s[0]?.custom_label_0 ?? null,
            recommended_tier: candidate.governance.recommendedTier ?? 'phrase',
            confidence: candidate.governance.confidence,
            reason_codes: candidate.governance.reasonCodes,
          })),
          created_by: 'dashboard:search-governance',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const payload = (await response.json()) as { applied_count: number; warnings?: string[] }
      setMessage(`Applied ${payload.applied_count.toLocaleString()} candidate(s) to Search governance queue.`)
      if (payload.warnings && payload.warnings.length > 0) {
        setErrorMessage(payload.warnings.join(' | '))
      }
      await loadCandidates()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to apply Search governance candidates')
    } finally {
      setApplying(false)
    }
  }

  const evaluateMovements = async () => {
    if (selectedCandidates.length === 0) {
      setErrorMessage('Select at least one candidate before evaluating tier movements.')
      return
    }

    setEvaluatingMovements(true)
    setErrorMessage(null)
    setMessage(null)
    try {
      const response = await fetch('/api/search/governance/movements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          terms: selectedCandidates.map((candidate) => ({
            search_term: candidate.search_term,
            custom_label_0: candidate.custom_label_0s[0]?.custom_label_0 ?? null,
            current_tier: candidate.current_tier,
            metrics: {
              impressions: Number(candidate.metrics.impressions ?? 0),
              clicks: Number(candidate.metrics.clicks ?? 0),
              conversions: Number(candidate.metrics.conversions ?? 0),
              conversionsValue: Number(candidate.metrics.conversionsValue ?? 0),
              costMicros: Number(candidate.metrics.costMicros ?? 0),
            },
            confidence: candidate.governance.confidence,
          })),
          created_by: 'dashboard:search-governance',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const payload = (await response.json()) as {
        generated_count: number
        staged_count: number
        cancelled_count?: number
        rollout_safety?: {
          status: 'go' | 'hold' | 'blocked'
        }
        warnings?: string[]
      }

      const safetyStatus = payload.rollout_safety?.status ?? 'go'
      setMessage(
        `Movement run generated ${payload.generated_count.toLocaleString()} decision(s); staged ${payload.staged_count.toLocaleString()} action(s); safety: ${safetyStatus}.`
      )
      if (payload.warnings && payload.warnings.length > 0) {
        setErrorMessage(payload.warnings.join(' | '))
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to evaluate Search tier movements')
    } finally {
      setEvaluatingMovements(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Search Governance</h1>
          <p className="text-muted-foreground">
            Promote and govern Shopping-to-Search candidates with confidence and cross-channel negative safeguards.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={range} onValueChange={(value) => setRange(value as DateRangePreset)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DATE_RANGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => void refresh()} disabled={refreshing || loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            onClick={() => void generateDrafts()}
            disabled={generatingDrafts || loading}
          >
            Generate Drafts
          </Button>
          <Button
            variant="outline"
            onClick={() => void evaluateMovements()}
            disabled={evaluatingMovements || loading || selectedCandidates.length === 0}
          >
            Evaluate Movements
          </Button>
          <Button onClick={() => void applySelected()} disabled={applying || loading || selectedCandidates.length === 0}>
            Apply Selected ({selectedCandidates.length})
          </Button>
        </div>
      </div>

      {errorMessage ? (
        <Card className="border-destructive/50">
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      ) : null}

      {message ? (
        <Card>
          <CardContent className="py-4 text-sm">{message}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Search Buildout Briefs</CardTitle>
          <CardDescription>
            Structured query-mining clusters for campaign/ad-group buildouts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {buildoutBriefs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No buildout briefs available for the selected range.
            </p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {buildoutBriefs.map((brief) => (
                <div key={brief.cluster_key} className="rounded-md border p-3">
                  <p className="font-medium">{brief.cluster_key}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{brief.suggested_campaign}</p>
                  <p className="text-xs text-muted-foreground">{brief.suggested_ad_group}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <Badge variant="outline">Tier: {brief.recommended_tier}</Badge>
                    <Badge variant="outline">{brief.candidate_count} terms</Badge>
                    <Badge variant="outline">
                      Conf {(brief.avg_confidence * 100).toFixed(0)}%
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Candidates</CardTitle>
          <CardDescription>
            {candidateData?.candidate_count.toLocaleString() ?? '0'} candidate terms available for Search tier governance.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => toggleAll(true)}>
              Select all
            </Button>
            <Button variant="outline" size="sm" onClick={() => toggleAll(false)}>
              Clear
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">Sel</TableHead>
                <TableHead>Search term</TableHead>
                <TableHead>Intent</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Target tier</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Reason codes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(candidateData?.candidates ?? []).slice(0, 200).map((candidate) => (
                <TableRow key={candidate.search_term}>
                  <TableCell>
                    <Checkbox
                      checked={Boolean(selected[candidate.search_term])}
                      onCheckedChange={(value) =>
                        setSelected((current) => ({
                          ...current,
                          [candidate.search_term]: Boolean(value),
                        }))
                      }
                    />
                  </TableCell>
                  <TableCell className="max-w-[340px] truncate">{candidate.search_term}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{candidate.route_decision.classification.intentClass}</Badge>
                  </TableCell>
                  <TableCell>{candidate.governance.action}</TableCell>
                  <TableCell>{candidate.governance.recommendedTier ?? '-'}</TableCell>
                  <TableCell>{(candidate.governance.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell className="max-w-[420px] truncate">{candidate.governance.reasonCodes.join(', ')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
