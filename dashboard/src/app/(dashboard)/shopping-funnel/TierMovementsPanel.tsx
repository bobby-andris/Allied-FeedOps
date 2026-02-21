'use client'

import { useCallback, useEffect, useMemo, useState, useTransition } from 'react'
import {
  AlertCircle,
  ArrowUpDown,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  RefreshCw,
  Shield,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface TierRecommendation {
  search_term: string
  custom_label_0: string | null
  current_tier: string
  value_signal_score: number | undefined
  decision: {
    searchTerm: string
    action: string
    confidence: number
    reasonCodes: string[]
    policyVersion: string
  }
}

interface TierMovementHistoryEntry {
  id: string
  searchTerm: string
  customLabel0: string | null
  previousTier: string | null
  newTier: string | null
  action: string | null
  status: string
  reasonCodes: string[]
  createdBy: string | null
  createdAt: string
}

type OperatorAction = 'approve' | 'reject' | 'defer'

const ACTION_LABELS: Record<string, string> = {
  promote_to_medium: 'Promote to Medium',
  promote_to_high: 'Promote to High',
  demote_to_medium: 'Demote to Medium',
  demote_to_low: 'Demote to Low',
  negative: 'Negative',
  hold: 'Hold',
}

const TIER_LABELS: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  campaign_negative: 'Campaign Negative',
}

function targetTierFromAction(action: string): string {
  if (action === 'promote_to_medium') return 'medium'
  if (action === 'promote_to_high') return 'high'
  if (action === 'demote_to_medium') return 'medium'
  if (action === 'demote_to_low') return 'low'
  if (action === 'negative') return 'campaign_negative'
  return 'unknown'
}

function confidenceBadgeVariant(confidence: number): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (confidence >= 0.75) return 'default'
  if (confidence >= 0.55) return 'secondary'
  return 'destructive'
}

export default function TierMovementsPanel() {
  const [, startTransition] = useTransition()
  const [innerTab, setInnerTab] = useState<'recommendations' | 'history'>('recommendations')

  // Recommendations state
  const [recommendations, setRecommendations] = useState<TierRecommendation[]>([])
  const [recoLoading, setRecoLoading] = useState(false)
  const [operatorActions, setOperatorActions] = useState<Record<string, OperatorAction>>({})
  const [expandedTerms, setExpandedTerms] = useState<Record<string, boolean>>({})
  const [executing, setExecuting] = useState(false)

  // History state
  const [history, setHistory] = useState<TierMovementHistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Messages
  const [message, setMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchRecommendations = useCallback(async () => {
    setRecoLoading(true)
    setErrorMessage(null)
    try {
      const response = await fetch('/api/intent/promote-demote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          terms: [], // Empty triggers a scan of existing funnel terms
        }),
      })

      if (!response.ok) {
        // If endpoint returns 400 for empty terms, that's expected — show empty state
        if (response.status === 400) {
          setRecommendations([])
          return
        }
        throw new Error(await response.text())
      }

      const data = await response.json()
      const actionableDecisions = (data.decisions ?? []).filter(
        (d: TierRecommendation) => d.decision.action !== 'hold'
      )
      setRecommendations(actionableDecisions)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch recommendations')
    } finally {
      setRecoLoading(false)
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const response = await fetch('/api/shopping-funnel/tier-movement?limit=50&status=applied')
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const data = await response.json()
      setHistory(data.entries ?? [])
    } catch (error) {
      console.error('Failed to fetch tier movement history:', error)
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (innerTab === 'recommendations') {
      // Don't auto-fetch recommendations — they require search terms
    } else {
      void fetchHistory()
    }
  }, [innerTab, fetchHistory])

  const approvedCount = useMemo(
    () => Object.values(operatorActions).filter((a) => a === 'approve').length,
    [operatorActions]
  )

  const rejectedCount = useMemo(
    () => Object.values(operatorActions).filter((a) => a === 'reject').length,
    [operatorActions]
  )

  function setAction(searchTerm: string, action: OperatorAction) {
    startTransition(() => {
      setOperatorActions((prev) => ({ ...prev, [searchTerm]: action }))
    })
  }

  function bulkApprove() {
    startTransition(() => {
      const next: Record<string, OperatorAction> = {}
      for (const rec of recommendations) {
        next[rec.search_term] = 'approve'
      }
      setOperatorActions(next)
    })
  }

  function bulkReject() {
    startTransition(() => {
      const next: Record<string, OperatorAction> = {}
      for (const rec of recommendations) {
        next[rec.search_term] = 'reject'
      }
      setOperatorActions(next)
    })
  }

  async function executeApproved() {
    const approved = recommendations.filter((r) => operatorActions[r.search_term] === 'approve')
    if (approved.length === 0) {
      setErrorMessage('No approved movements to execute.')
      return
    }

    const confirmed = window.confirm(
      `Execute ${approved.length} tier movement(s)? This will update the supplemental feed.`
    )
    if (!confirmed) return

    setExecuting(true)
    setErrorMessage(null)
    setMessage(null)
    try {
      const response = await fetch('/api/shopping-funnel/tier-movement', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          movements: approved.map((r) => ({
            search_term: r.search_term,
            custom_label_0: r.custom_label_0 ?? '',
            current_tier: r.current_tier,
            target_tier: targetTierFromAction(r.decision.action),
            confidence: r.decision.confidence,
            metrics: {},
          })),
          created_by: 'operator',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const result = await response.json()
      setMessage(
        `Executed: ${result.appliedCount} applied, ${result.failedCount} failed, ` +
        `${result.blockedCount} blocked, ${result.reviewRequiredCount} need review.`
      )

      // Clear approved items from the recommendations list
      const approvedTerms = new Set(approved.map((r) => r.search_term))
      setRecommendations((prev) => prev.filter((r) => !approvedTerms.has(r.search_term)))
      setOperatorActions((prev) => {
        const next = { ...prev }
        for (const term of approvedTerms) {
          delete next[term]
        }
        return next
      })
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Execution failed')
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="space-y-4">
      {message && (
        <Card className="border-emerald-300 bg-emerald-50">
          <CardContent className="py-3 text-emerald-700 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {message}
          </CardContent>
        </Card>
      )}

      {errorMessage && (
        <Card className="border-red-300 bg-red-50">
          <CardContent className="py-3 text-red-700 flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      )}

      <Tabs
        value={innerTab}
        onValueChange={(v) => startTransition(() => setInnerTab(v as typeof innerTab))}
      >
        <TabsList>
          <TabsTrigger value="recommendations">
            <ArrowUpDown className="mr-2 h-4 w-4" />
            Recommendations
          </TabsTrigger>
          <TabsTrigger value="history">
            <Clock className="mr-2 h-4 w-4" />
            Movement History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="recommendations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Tier Movement Recommendations</CardTitle>
              <CardDescription>
                Keywords recommended for promotion or demotion by the policy engine.
                Review and approve each recommendation before executing.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => void fetchRecommendations()}
                  disabled={recoLoading}
                >
                  <RefreshCw className={`mr-2 h-4 w-4 ${recoLoading ? 'animate-spin' : ''}`} />
                  {recoLoading ? 'Loading...' : 'Load Recommendations'}
                </Button>

                {recommendations.length > 0 && (
                  <>
                    <Button variant="outline" size="sm" onClick={bulkApprove}>
                      Approve All
                    </Button>
                    <Button variant="outline" size="sm" onClick={bulkReject}>
                      Reject All
                    </Button>
                    <Button
                      onClick={() => void executeApproved()}
                      disabled={executing || approvedCount === 0}
                    >
                      <Shield className="mr-2 h-4 w-4" />
                      {executing ? 'Executing...' : `Execute ${approvedCount} Approved`}
                    </Button>
                  </>
                )}

                <div className="ml-auto flex items-center gap-2">
                  <Badge variant="secondary">{recommendations.length} recommendations</Badge>
                  {approvedCount > 0 && <Badge variant="default">{approvedCount} approved</Badge>}
                  {rejectedCount > 0 && <Badge variant="destructive">{rejectedCount} rejected</Badge>}
                </div>
              </div>
            </CardContent>
          </Card>

          {recoLoading && (
            <Card>
              <CardContent className="pt-6 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </CardContent>
            </Card>
          )}

          {!recoLoading && recommendations.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No tier movement recommendations. Click &quot;Load Recommendations&quot; to evaluate
                existing funnel terms against policy thresholds.
              </CardContent>
            </Card>
          )}

          {!recoLoading && recommendations.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
                  {recommendations.map((rec) => {
                    const action = operatorActions[rec.search_term]
                    const isExpanded = expandedTerms[rec.search_term] ?? false
                    const targetTier = targetTierFromAction(rec.decision.action)

                    return (
                      <div
                        key={rec.search_term}
                        className={`rounded-md border p-3 ${
                          action === 'approve'
                            ? 'border-emerald-300 bg-emerald-50/50'
                            : action === 'reject'
                              ? 'border-red-300 bg-red-50/50'
                              : action === 'defer'
                                ? 'border-amber-300 bg-amber-50/50'
                                : ''
                        }`}
                      >
                        <div className="flex flex-wrap items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="font-medium leading-tight">{rec.search_term}</p>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              {rec.custom_label_0 && <span>Label: {rec.custom_label_0}</span>}
                              <span>Current: {TIER_LABELS[rec.current_tier] ?? rec.current_tier}</span>
                              <span>
                                Target: {TIER_LABELS[targetTier] ?? targetTier}
                              </span>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">
                              {ACTION_LABELS[rec.decision.action] ?? rec.decision.action}
                            </Badge>
                            <Badge variant={confidenceBadgeVariant(rec.decision.confidence)}>
                              {Math.round(rec.decision.confidence * 100)}% confidence
                            </Badge>

                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                variant={action === 'approve' ? 'default' : 'outline'}
                                onClick={() => setAction(rec.search_term, 'approve')}
                              >
                                <CheckCircle2 className="h-4 w-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant={action === 'reject' ? 'destructive' : 'outline'}
                                onClick={() => setAction(rec.search_term, 'reject')}
                              >
                                <XCircle className="h-4 w-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant={action === 'defer' ? 'secondary' : 'outline'}
                                onClick={() => setAction(rec.search_term, 'defer')}
                              >
                                <Clock className="h-4 w-4" />
                              </Button>
                            </div>

                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                startTransition(() =>
                                  setExpandedTerms((prev) => ({
                                    ...prev,
                                    [rec.search_term]: !prev[rec.search_term],
                                  }))
                                )
                              }
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-3 rounded-md border bg-muted/30 p-2 text-xs text-muted-foreground space-y-1">
                            <p>Policy version: {rec.decision.policyVersion}</p>
                            <p>Reason codes: {rec.decision.reasonCodes.join(', ')}</p>
                            {rec.value_signal_score != null && (
                              <p>Value signal score: {rec.value_signal_score.toFixed(3)}</p>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Movement History</CardTitle>
              <CardDescription>
                Recent tier movements executed through the policy engine.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                onClick={() => void fetchHistory()}
                disabled={historyLoading}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${historyLoading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </CardContent>
          </Card>

          {historyLoading && (
            <Card>
              <CardContent className="pt-6 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </CardContent>
            </Card>
          )}

          {!historyLoading && history.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No tier movement history found.
              </CardContent>
            </Card>
          )}

          {!historyLoading && history.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
                  {history.map((entry) => (
                    <div key={entry.id} className="rounded-md border p-3">
                      <div className="flex flex-wrap items-start gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium leading-tight">{entry.searchTerm}</p>
                          <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            {entry.customLabel0 && <span>Label: {entry.customLabel0}</span>}
                            <span>
                              {TIER_LABELS[entry.previousTier ?? ''] ?? entry.previousTier} →{' '}
                              {TIER_LABELS[entry.newTier ?? ''] ?? entry.newTier}
                            </span>
                            <span>{new Date(entry.createdAt).toLocaleString()}</span>
                            {entry.createdBy && <span>by {entry.createdBy}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {ACTION_LABELS[entry.action ?? ''] ?? entry.action}
                          </Badge>
                          <Badge variant={entry.status === 'applied' ? 'default' : 'destructive'}>
                            {entry.status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
