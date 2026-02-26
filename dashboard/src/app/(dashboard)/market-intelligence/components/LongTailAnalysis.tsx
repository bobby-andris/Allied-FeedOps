'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
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

export function LongTailAnalysis({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No long-tail analysis data available
      </div>
    )
  }

  const chartData = data.map((b) => ({
    bucket: b.wordCountRange,
    ROAS: parseFloat(b.avgRoas.toFixed(2)),
    CVR: parseFloat((b.avgCvr * 100).toFixed(2)),
    Terms: b.termCount,
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="ROAS" fill="#3b82f6" name="ROAS" />
          <Bar dataKey="CVR" fill="#22c55e" name="CVR %" />
          <Bar dataKey="Terms" fill="#94a3b8" name="Terms" />
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Bucket</TableHead>
              <TableHead className="text-right">Terms</TableHead>
              <TableHead className="text-right">Avg ROAS</TableHead>
              <TableHead className="text-right">Avg CVR</TableHead>
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((b) => (
              <TableRow key={b.wordCountRange}>
                <TableCell className="font-medium">{b.wordCountRange} words</TableCell>
                <TableCell className="text-right">{b.termCount.toLocaleString()}</TableCell>
                <TableCell className="text-right">{b.avgRoas.toFixed(2)}x</TableCell>
                <TableCell className="text-right">{(b.avgCvr * 100).toFixed(1)}%</TableCell>
                <TableCell className="text-right">{b.totalImpressions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{formatDollars(b.totalRevenue)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
