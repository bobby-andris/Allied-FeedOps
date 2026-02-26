'use client'

import { useState, useEffect } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DemandTab } from './components/DemandTab'
import { CompetitiveTab } from './components/CompetitiveTab'
import { ProductsTab } from './components/ProductsTab'

export default function MarketIntelligencePage() {
  const [activeTab, setActiveTab] = useState<string>('demand')
  const [customLabel0Filter, setCustomLabel0Filter] = useState<string | undefined>(undefined)
  const [customLabel0Options, setCustomLabel0Options] = useState<string[]>([])

  // Fetch product group names for filter dropdown
  useEffect(() => {
    let cancelled = false
    async function loadGroups() {
      try {
        const res = await fetch('/api/market-intelligence/products')
        if (!res.ok) return
        const data = await res.json()
        if (cancelled) return
        // Extract unique customLabel0 values from groups array
        const groups: string[] = Array.from(
          new Set(
            (data.groups || [])
              .map((g: { customLabel0: string }) => g.customLabel0)
              .filter(Boolean)
          )
        )
        groups.sort((a, b) => a.localeCompare(b))
        setCustomLabel0Options(groups)
      } catch {
        // Silently fail — filter just won't have options
      }
    }
    loadGroups()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="space-y-6 p-6">
      {/* Header + Filter */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Market Intelligence</h1>
          <p className="text-muted-foreground">
            Demand patterns, competitive positioning, and product group health
          </p>
        </div>
        <Select
          value={customLabel0Filter ?? 'all'}
          onValueChange={(v) => setCustomLabel0Filter(v === 'all' ? undefined : v)}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Groups" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Groups</SelectItem>
            {customLabel0Options.map((g) => (
              <SelectItem key={g} value={g}>
                {g}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="demand">Demand</TabsTrigger>
          <TabsTrigger value="competitive">Competitive</TabsTrigger>
          <TabsTrigger value="products">Products</TabsTrigger>
        </TabsList>
        <TabsContent value="demand" className="mt-4">
          <DemandTab customLabel0={customLabel0Filter} />
        </TabsContent>
        <TabsContent value="competitive" className="mt-4">
          <CompetitiveTab customLabel0={customLabel0Filter} />
        </TabsContent>
        <TabsContent value="products" className="mt-4">
          <ProductsTab customLabel0={customLabel0Filter} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
