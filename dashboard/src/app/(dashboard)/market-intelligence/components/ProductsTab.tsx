'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { BarChart3, LayoutGrid, RefreshCw, AlertCircle } from 'lucide-react'
import { useProductGroups } from '../hooks/useProductGroups'
import { BcgBubbleChart } from './BcgBubbleChart'
import { BcgTableView } from './BcgTableView'
import { ProductGroupSlideOut } from './ProductGroupSlideOut'
import { BCG_QUADRANT_LABELS, BCG_COLORS } from '@/lib/market-intelligence/constants'
import { formatDollars } from '@/lib/formatting'

interface ProductsTabProps {
  customLabel0?: string
}

const QUADRANT_ORDER = ['star', 'cashCow', 'questionMark', 'dog'] as const

export function ProductsTab({ customLabel0 }: ProductsTabProps) {
  const { data, loading, error, refresh, fetchGroupDetail } = useProductGroups(customLabel0)
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [slideOutOpen, setSlideOutOpen] = useState(false)

  function handleGroupClick(group: string) {
    setSelectedGroup(group)
    setSlideOutOpen(true)
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-[500px] rounded-lg" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="flex items-center justify-between">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  if (!data) return null

  const kpiCards = QUADRANT_ORDER.map(key => {
    const countMap: Record<string, number> = {
      star: data.kpis.starCount,
      cashCow: data.kpis.cashCowCount,
      questionMark: data.kpis.questionMarkCount,
      dog: data.kpis.dogCount,
    }
    return {
      key,
      label: BCG_QUADRANT_LABELS[key].label,
      count: countMap[key],
      color: BCG_COLORS[key],
    }
  })

  return (
    <div className="space-y-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {kpiCards.map(kpi => (
          <Card key={kpi.key}>
            <CardContent className="p-4">
              <p className="text-3xl font-bold" style={{ color: kpi.color }}>
                {kpi.count}
              </p>
              <p className="text-sm text-muted-foreground mt-1">{kpi.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Chart/Table Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle>Product Group Analysis</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {formatDollars(data.kpis.totalRevenue)} revenue / {formatDollars(data.kpis.totalSpend)} spend across {data.groups.length} groups
            </p>
          </div>
          <div className="flex items-center gap-1 border rounded-md p-0.5">
            <Button
              variant={view === 'chart' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setView('chart')}
              className="h-7 px-2"
            >
              <BarChart3 className="h-3.5 w-3.5 mr-1" />
              Chart
            </Button>
            <Button
              variant={view === 'table' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setView('table')}
              className="h-7 px-2"
            >
              <LayoutGrid className="h-3.5 w-3.5 mr-1" />
              Table
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {view === 'chart' ? (
            <BcgBubbleChart
              groups={data.groups}
              medianRoas={data.medianRoas}
              medianRevenue={data.medianRevenue}
              onGroupClick={handleGroupClick}
              dimmed={slideOutOpen}
            />
          ) : (
            <BcgTableView
              groups={data.groups}
              onGroupClick={handleGroupClick}
            />
          )}
        </CardContent>
      </Card>

      {/* Slide-out Panel */}
      <ProductGroupSlideOut
        open={slideOutOpen}
        onOpenChange={setSlideOutOpen}
        groupName={selectedGroup}
        fetchGroupDetail={fetchGroupDetail}
      />
    </div>
  )
}
