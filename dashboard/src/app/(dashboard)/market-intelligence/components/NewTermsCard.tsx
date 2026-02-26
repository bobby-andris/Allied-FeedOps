'use client'

import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { NewTerm } from '@/lib/market-intelligence/types'

interface Props {
  data: NewTerm[]
  count: number
}

export function NewTermsCard({ data, count }: Props) {
  if (count === 0) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No new terms discovered in the last 7 days
      </div>
    )
  }

  const sorted = [...data].sort((a, b) => b.impressions - a.impressions)

  return (
    <div>
      <div className="mb-3">
        <Badge variant="secondary">{count} new terms this week</Badge>
      </div>
      <div className="max-h-[240px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Term</TableHead>
              <TableHead>Product Group</TableHead>
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((term) => (
              <TableRow key={`${term.queryText}-${term.customLabel0}`}>
                <TableCell className="font-medium">{term.queryText}</TableCell>
                <TableCell className="text-muted-foreground">{term.customLabel0}</TableCell>
                <TableCell className="text-right">{term.impressions.toLocaleString()}</TableCell>
                <TableCell className="text-right">{term.clicks.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
