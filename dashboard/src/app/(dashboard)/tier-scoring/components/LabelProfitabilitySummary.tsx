'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react'
import { formatDollars } from '@/lib/formatting'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'

interface LabelProfitability {
  custom_label_0: string
  days_of_data: number
  total_spend: number
  total_revenue: number
  roas: number
  total_impressions: number
  total_conversions: number
}

interface LabelProfitabilitySummaryProps {
  scores: TermScore[]
}

export function LabelProfitabilitySummary({ scores }: LabelProfitabilitySummaryProps) {
  const [labels, setLabels] = useState<LabelProfitability[]>([])
  const [loading, setLoading] = useState(true)

  // Count opportunities per label from in-memory TermScore data
  const opportunityCounts = new Map<string, number>()
  for (const score of scores) {
    if (score.isMisplaced) {
      opportunityCounts.set(
        score.customLabel0,
        (opportunityCounts.get(score.customLabel0) ?? 0) + 1
      )
    }
  }

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch('/api/shopping-funnel/label-profitability')
        if (!res.ok) throw new Error(`API error: ${res.status}`)
        const data = await res.json()
        if (!cancelled) {
          setLabels(data.labels ?? [])
        }
      } catch (err) {
        console.error('Failed to load label profitability:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Label Profitability</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (labels.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Label Profitability</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No snapshot data available yet. Label profitability will appear once funnel snapshots are captured.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Label Profitability (30-day)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="pb-2 font-medium">Label</th>
                <th className="pb-2 font-medium text-right">Data</th>
                <th className="pb-2 font-medium text-right">Spend</th>
                <th className="pb-2 font-medium text-right">ROAS</th>
                <th className="pb-2 font-medium text-right">Conversions</th>
                <th className="pb-2 font-medium text-right">Opportunities</th>
                <th className="pb-2 font-medium text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {labels.map((label) => {
                const insufficient = label.days_of_data < 7
                const opportunities = opportunityCounts.get(label.custom_label_0) ?? 0

                return (
                  <tr key={label.custom_label_0} className="border-b last:border-0">
                    <td className="py-2 font-medium">{label.custom_label_0}</td>
                    <td className="py-2 text-right text-muted-foreground">
                      {label.days_of_data}d
                    </td>
                    <td className="py-2 text-right">
                      {insufficient ? (
                        <span className="text-muted-foreground">--</span>
                      ) : (
                        formatDollars(label.total_spend)
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {insufficient ? (
                        <span className="text-muted-foreground">--</span>
                      ) : (
                        <span className={label.roas >= 1 ? 'text-emerald-600' : 'text-red-600'}>
                          {label.roas.toFixed(1)}x
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {insufficient ? (
                        <span className="text-muted-foreground">--</span>
                      ) : (
                        Math.round(label.total_conversions)
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {opportunities > 0 ? (
                        <span className="text-amber-600 font-medium">{opportunities}</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </td>
                    <td className="py-2 text-center">
                      {insufficient ? (
                        <Badge variant="outline" className="gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          {label.days_of_data}d data
                        </Badge>
                      ) : label.roas >= 1 ? (
                        <Badge variant="outline" className="gap-1 border-emerald-200 bg-emerald-50 text-emerald-700">
                          <TrendingUp className="h-3 w-3" />
                          Profitable
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="gap-1 border-red-200 bg-red-50 text-red-700">
                          <TrendingDown className="h-3 w-3" />
                          Unprofitable
                        </Badge>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
