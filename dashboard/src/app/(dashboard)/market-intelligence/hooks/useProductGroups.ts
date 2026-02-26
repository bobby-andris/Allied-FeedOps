'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ProductsData, ProductGroupDetail } from '@/lib/market-intelligence/types'

export function useProductGroups(customLabel0?: string) {
  const [data, setData] = useState<ProductsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (customLabel0) params.set('customLabel0', customLabel0)
      const url = `/api/market-intelligence/products${params.toString() ? '?' + params.toString() : ''}`
      const res = await fetch(url)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.error || `API returned ${res.status}`)
      }
      const json = await res.json()
      setData(json)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load product groups')
    } finally {
      setLoading(false)
    }
  }, [customLabel0])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const fetchGroupDetail = useCallback(async (group: string): Promise<ProductGroupDetail> => {
    const params = new URLSearchParams({ group })
    const res = await fetch(`/api/market-intelligence/products?${params.toString()}`)
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.error || `API returned ${res.status}`)
    }
    return res.json()
  }, [])

  return { data, loading, error, refresh: fetchData, fetchGroupDetail }
}
