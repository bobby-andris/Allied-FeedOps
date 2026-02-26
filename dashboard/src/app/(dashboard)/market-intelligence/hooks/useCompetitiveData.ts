'use client'

import { useState, useEffect, useCallback } from 'react'
import type { CompetitiveData } from '@/lib/market-intelligence/types'

export function useCompetitiveData(customLabel0?: string) {
  const [data, setData] = useState<CompetitiveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (customLabel0) params.set('customLabel0', customLabel0)
      const res = await fetch(`/api/market-intelligence/competitive?${params}`)
      if (!res.ok) throw new Error(await res.text())
      setData(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [customLabel0])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { data, loading, error, refresh }
}
