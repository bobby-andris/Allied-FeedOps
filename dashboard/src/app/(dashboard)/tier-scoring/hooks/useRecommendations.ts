'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import type { TermScore, ImpactRange } from '@/lib/optimization/tier-scoring.types'
import type { ApproveOptions } from '../components/LeakageTermRow'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ReviewStatus = 'pending' | 'accepted' | 'rejected' | 'expired'

export interface RecommendationStatus {
  status: ReviewStatus
  updatedAt: string | null
  rejectionReason?: string
}

export interface HistoryEntry {
  search_term: string
  custom_label_0: string
  recommended_tier: string | null
  review_status: ReviewStatus
  accepted_at: string | null
  accepted_by: string | null
  metadata: {
    current_tier?: string
    impact?: ImpactRange
    rejection_reason?: string
    history?: Array<{ action: string; at: string }>
    [key: string]: unknown
  }
  created_at: string
}

interface UseRecommendationsReturn {
  statuses: Record<string, RecommendationStatus>
  history: HistoryEntry[]
  historyLoading: boolean
  loading: boolean
  approve: (term: TermScore, options?: ApproveOptions) => Promise<void>
  reject: (term: TermScore, reason?: string) => Promise<void>
  undo: (searchTerm: string, customLabel0: string) => Promise<void>
  batchApprove: (terms: TermScore[]) => Promise<void>
  blockLabel: (customLabel0: string) => Promise<void>
  loadHistory: () => Promise<void>
  getStatus: (searchTerm: string, customLabel0: string) => RecommendationStatus | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}::${customLabel0}`
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRecommendations(): UseRecommendationsReturn {
  const [statuses, setStatuses] = useState<Record<string, RecommendationStatus>>({})
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const mountedRef = useRef(true)

  // Load statuses on mount
  useEffect(() => {
    mountedRef.current = true
    let cancelled = false

    async function loadStatuses() {
      try {
        const res = await fetch('/api/shopping-funnel/recommendations?action=statuses')
        if (!res.ok) throw new Error(`API error: ${res.status}`)
        const data = await res.json()

        if (cancelled) return

        const statusMap: Record<string, RecommendationStatus> = {}
        for (const row of data.statuses ?? []) {
          const key = makeKey(row.search_term, row.custom_label_0)
          // Only keep the first (most recent) entry per key
          if (!statusMap[key]) {
            const meta = (row.metadata ?? {}) as Record<string, unknown>
            statusMap[key] = {
              status: row.review_status as ReviewStatus,
              updatedAt: row.accepted_at ?? null,
              ...(meta.rejection_reason ? { rejectionReason: String(meta.rejection_reason) } : {}),
            }
          }
        }

        setStatuses(statusMap)
      } catch (err) {
        console.error('Failed to load recommendation statuses:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadStatuses()

    return () => {
      cancelled = true
      mountedRef.current = false
    }
  }, [])

  // ----- approve -----
  const approve = useCallback(async (term: TermScore, options?: ApproveOptions) => {
    const key = makeKey(term.searchTerm, term.customLabel0)
    const previous = statuses[key]

    // Optimistic update
    setStatuses(prev => ({
      ...prev,
      [key]: { status: 'accepted', updatedAt: new Date().toISOString() },
    }))

    try {
      const res = await fetch('/api/shopping-funnel/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'approve',
          searchTerm: term.searchTerm,
          customLabel0: term.customLabel0,
          recommendedTier: options?.recommendedTier ?? term.targetTier ?? term.recommendedTier,
          currentTier: term.currentTier,
          confidence: term.confidence.score,
          impact: term.impact,
          ...(options?.recommendedAction ? { recommendedAction: options.recommendedAction } : {}),
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
    } catch (err) {
      // Revert on failure
      setStatuses(prev => ({
        ...prev,
        [key]: previous ?? { status: 'pending', updatedAt: null },
      }))
      console.error('Failed to approve recommendation:', err)
    }
  }, [statuses])

  // ----- reject -----
  const reject = useCallback(async (term: TermScore, reason?: string) => {
    const key = makeKey(term.searchTerm, term.customLabel0)
    const previous = statuses[key]

    // Optimistic update
    setStatuses(prev => ({
      ...prev,
      [key]: {
        status: 'rejected',
        updatedAt: new Date().toISOString(),
        ...(reason ? { rejectionReason: reason } : {}),
      },
    }))

    try {
      const res = await fetch('/api/shopping-funnel/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'reject',
          searchTerm: term.searchTerm,
          customLabel0: term.customLabel0,
          reason,
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
    } catch (err) {
      // Revert on failure
      setStatuses(prev => ({
        ...prev,
        [key]: previous ?? { status: 'pending', updatedAt: null },
      }))
      console.error('Failed to reject recommendation:', err)
    }
  }, [statuses])

  // ----- undo -----
  const undo = useCallback(async (searchTerm: string, customLabel0: string) => {
    const key = makeKey(searchTerm, customLabel0)
    const previous = statuses[key]

    // Optimistic update
    setStatuses(prev => ({
      ...prev,
      [key]: { status: 'pending', updatedAt: new Date().toISOString() },
    }))

    try {
      const res = await fetch('/api/shopping-funnel/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'undo',
          searchTerm,
          customLabel0,
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
    } catch (err) {
      // Revert on failure
      setStatuses(prev => ({
        ...prev,
        [key]: previous ?? { status: 'pending', updatedAt: null },
      }))
      console.error('Failed to undo recommendation:', err)
    }
  }, [statuses])

  // ----- batchApprove -----
  const batchApprove = useCallback(async (terms: TermScore[]) => {
    if (terms.length === 0) return

    // Save previous states for rollback
    const previousEntries: Array<[string, RecommendationStatus | undefined]> = terms.map(t => {
      const key = makeKey(t.searchTerm, t.customLabel0)
      return [key, statuses[key]]
    })

    // Optimistic update all
    const now = new Date().toISOString()
    setStatuses(prev => {
      const next = { ...prev }
      for (const term of terms) {
        const key = makeKey(term.searchTerm, term.customLabel0)
        next[key] = { status: 'accepted', updatedAt: now }
      }
      return next
    })

    try {
      const res = await fetch('/api/shopping-funnel/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'batch_approve',
          terms: terms.map(t => ({
            searchTerm: t.searchTerm,
            customLabel0: t.customLabel0,
            recommendedTier: t.recommendedTier,
            currentTier: t.currentTier,
            confidence: t.confidence.score,
            impact: t.impact,
          })),
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
    } catch (err) {
      // Revert all on failure
      setStatuses(prev => {
        const next = { ...prev }
        for (const [key, prevStatus] of previousEntries) {
          next[key] = prevStatus ?? { status: 'pending', updatedAt: null }
        }
        return next
      })
      console.error('Failed to batch approve recommendations:', err)
    }
  }, [statuses])

  // ----- blockLabel -----
  const blockLabel = useCallback(async (customLabel0: string) => {
    const key = makeKey('__LABEL_BLOCK__', customLabel0)

    // Optimistic update
    setStatuses(prev => ({
      ...prev,
      [key]: { status: 'accepted', updatedAt: new Date().toISOString() },
    }))

    try {
      const res = await fetch('/api/shopping-funnel/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'label_block',
          customLabel0,
          metadata: { blockedBy: 'group_overview' },
        }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
    } catch (err) {
      // Revert on failure
      setStatuses(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
      console.error('Failed to block label:', err)
    }
  }, [])

  // ----- loadHistory -----
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const res = await fetch('/api/shopping-funnel/recommendations?action=history')
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      if (mountedRef.current) {
        setHistory(data.history ?? [])
      }
    } catch (err) {
      console.error('Failed to load recommendation history:', err)
    } finally {
      if (mountedRef.current) setHistoryLoading(false)
    }
  }, [])

  // ----- getStatus -----
  const getStatus = useCallback(
    (searchTerm: string, customLabel0: string): RecommendationStatus | null => {
      const key = makeKey(searchTerm, customLabel0)
      return statuses[key] ?? null
    },
    [statuses]
  )

  return {
    statuses,
    history,
    historyLoading,
    loading,
    approve,
    reject,
    undo,
    batchApprove,
    blockLabel,
    loadHistory,
    getStatus,
  }
}
