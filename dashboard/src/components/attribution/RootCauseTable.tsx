'use client'

import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { Ga4AttributionRootCauseRow } from '@/lib/ga4/forensics'

interface RootCauseTableProps {
  rows: Ga4AttributionRootCauseRow[]
}

type SortColumn = 'purchaseRevenue' | 'revenueShare' | 'sessions'

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function typeBadge(type: Ga4AttributionRootCauseRow['rootCauseType']) {
  if (type === 'campaign_pattern') return 'Campaign naming'
  if (type === 'landing_page') return 'Landing page'
  return 'Source/Medium'
}

export function RootCauseTable({ rows }: RootCauseTableProps) {
  const [sortBy, setSortBy] = useState<SortColumn>('purchaseRevenue')
  const [descending, setDescending] = useState(true)

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      const delta = (a[sortBy] as number) - (b[sortBy] as number)
      return descending ? -delta : delta
    })
    return copy
  }, [rows, sortBy, descending])

  const toggleSort = (column: SortColumn) => {
    if (column === sortBy) {
      setDescending((value) => !value)
      return
    }
    setSortBy(column)
    setDescending(true)
  }

  const sortIcon = descending ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />

  return (
    <Card>
      <CardHeader>
        <CardTitle>Root Cause Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => toggleSort('purchaseRevenue')}>
            Revenue impact {sortBy === 'purchaseRevenue' ? sortIcon : null}
          </Button>
          <Button variant="outline" size="sm" onClick={() => toggleSort('revenueShare')}>
            Revenue share {sortBy === 'revenueShare' ? sortIcon : null}
          </Button>
          <Button variant="outline" size="sm" onClick={() => toggleSort('sessions')}>
            Sessions {sortBy === 'sessions' ? sortIcon : null}
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Bucket</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
              <TableHead className="text-right">Revenue share</TableHead>
              <TableHead className="text-right">Sessions</TableHead>
              <TableHead>Sample values</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  No root-cause data available.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((row) => (
                <TableRow key={`${row.rootCauseType}-${row.rootCauseKey}`}>
                  <TableCell>
                    <Badge variant="secondary">{typeBadge(row.rootCauseType)}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">{row.rootCauseKey}</TableCell>
                  <TableCell className="text-right">${row.purchaseRevenue.toFixed(2)}</TableCell>
                  <TableCell className="text-right">{formatPercent(row.revenueShare)}</TableCell>
                  <TableCell className="text-right">{row.sessions.toLocaleString()}</TableCell>
                  <TableCell className="max-w-[420px] truncate text-xs text-muted-foreground">
                    {row.sampleValues.join(', ')}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
