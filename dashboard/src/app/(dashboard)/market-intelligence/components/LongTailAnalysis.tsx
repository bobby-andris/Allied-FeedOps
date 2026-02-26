'use client'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { LongTailBucket } from '@/lib/market-intelligence/types'

interface Props {
  data: LongTailBucket[]
}

function formatDollars(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function roasColor(roas: number): string {
  if (roas >= 3) return 'text-green-600'
  if (roas >= 2) return 'text-amber-600'
  return 'text-red-600'
}

function roasBgColor(roas: number): string {
  if (roas >= 3) return 'bg-green-500'
  if (roas >= 2) return 'bg-amber-500'
  return 'bg-red-500'
}

export function LongTailAnalysis({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No long-tail analysis data available
      </div>
    )
  }

  const maxRevenue = Math.max(...data.map(b => b.totalRevenue))
  const totals = data.reduce(
    (acc, b) => ({
      termCount: acc.termCount + b.termCount,
      totalImpressions: acc.totalImpressions + b.totalImpressions,
      totalRevenue: acc.totalRevenue + b.totalRevenue,
      totalSpend: acc.totalSpend + b.totalSpend,
      totalConversions: acc.totalConversions + b.totalConversions,
      weightedRoas: acc.weightedRoas + b.avgRoas * b.totalSpend,
      weightedCvr: acc.weightedCvr + b.avgCvr * b.totalImpressions,
    }),
    { termCount: 0, totalImpressions: 0, totalRevenue: 0, totalSpend: 0, totalConversions: 0, weightedRoas: 0, weightedCvr: 0 }
  )
  const avgRoas = totals.totalSpend > 0 ? totals.weightedRoas / totals.totalSpend : 0
  const avgCvr = totals.totalImpressions > 0 ? totals.weightedCvr / totals.totalImpressions : 0

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Bucket</TableHead>
          <TableHead className="text-right">Terms</TableHead>
          <TableHead className="text-right">Avg ROAS</TableHead>
          <TableHead className="text-right">Avg CVR</TableHead>
          <TableHead className="text-right">Impressions</TableHead>
          <TableHead className="text-right">Revenue</TableHead>
          <TableHead className="w-[120px]">Share</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((b) => {
          const revenuePercent = maxRevenue > 0 ? (b.totalRevenue / maxRevenue) * 100 : 0
          return (
            <TableRow key={b.wordCountRange}>
              <TableCell className="font-medium">{b.wordCountRange} words</TableCell>
              <TableCell className="text-right">{b.termCount.toLocaleString()}</TableCell>
              <TableCell className={`text-right font-semibold ${roasColor(b.avgRoas)}`}>
                {b.avgRoas.toFixed(2)}x
              </TableCell>
              <TableCell className="text-right">{(b.avgCvr * 100).toFixed(1)}%</TableCell>
              <TableCell className="text-right">{b.totalImpressions.toLocaleString()}</TableCell>
              <TableCell className="text-right">{formatDollars(b.totalRevenue)}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="h-2.5 flex-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full ${roasBgColor(b.avgRoas)}`}
                      style={{ width: `${revenuePercent}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-muted-foreground w-[36px] text-right">
                    {maxRevenue > 0 ? `${((b.totalRevenue / totals.totalRevenue) * 100).toFixed(0)}%` : '—'}
                  </span>
                </div>
              </TableCell>
            </TableRow>
          )
        })}
        {/* Totals row */}
        <TableRow className="border-t-2 font-semibold bg-muted/30">
          <TableCell>Total</TableCell>
          <TableCell className="text-right">{totals.termCount.toLocaleString()}</TableCell>
          <TableCell className={`text-right ${roasColor(avgRoas)}`}>
            {avgRoas.toFixed(2)}x
          </TableCell>
          <TableCell className="text-right">{(avgCvr * 100).toFixed(1)}%</TableCell>
          <TableCell className="text-right">{totals.totalImpressions.toLocaleString()}</TableCell>
          <TableCell className="text-right">{formatDollars(totals.totalRevenue)}</TableCell>
          <TableCell>
            <span className="text-[11px] text-muted-foreground">100%</span>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  )
}
