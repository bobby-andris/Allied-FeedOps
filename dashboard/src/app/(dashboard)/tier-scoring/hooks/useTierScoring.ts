'use client'

import { useState, useEffect, useCallback } from 'react'
import type { GroupDistributions, TermScore, ImpactRange, TierDistribution } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

export interface TierScoringResponse {
  distributions: Record<string, GroupDistributions>
  globalFallback: Record<FunnelTier, TierDistribution>
  scores: TermScore[]
  heroCallout: string
  computedAt: string
  totalGroups: number
  totalTermsScored: number
  totalMisplaced: number
  totalImpact: ImpactRange
}

export function useTierScoring() {
  const [data, setData] = useState<TierScoringResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchScores = useCallback(async (forceRefresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const url = forceRefresh
        ? '/api/shopping-funnel/tier-scoring?forceRefresh=true'
        : '/api/shopping-funnel/tier-scoring'
      const res = await fetch(url)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.error || `API returned ${res.status}`)
      }
      const json = await res.json()
      setData(json)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tier scoring data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchScores()
  }, [fetchScores])

  return { data, loading, error, refresh: fetchScores }
}
