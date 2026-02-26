'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { CompetitorMention } from '@/lib/market-intelligence/types'

interface Props {
  data: CompetitorMention[]
}

function formatDollars(value: number): string {
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export function CompetitorTracker({ data }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  if (!data.length) {
    return (
      <div className="flex h-[250px] items-center justify-center text-muted-foreground">
        No competitor terms detected
      </div>
    )
  }

  const sorted = [...data].sort((a, b) => b.spend - a.spend)

  function toggleExpand(token: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(token)) next.delete(token)
      else next.add(token)
      return next
    })
  }

  return (
    <div className="max-h-[400px] overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8"></TableHead>
            <TableHead>Competitor</TableHead>
            <TableHead className="text-right">Terms</TableHead>
            <TableHead className="text-right">Impressions</TableHead>
            <TableHead className="text-right">Spend</TableHead>
            <TableHead className="text-right">Revenue</TableHead>
            <TableHead className="text-right">ROAS</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((c) => {
            const isExpanded = expanded.has(c.token)
            return (
              <TableRow key={c.token} className="group">
                <TableCell>
                  <button
                    onClick={() => toggleExpand(c.token)}
                    className="p-1 text-muted-foreground hover:text-foreground"
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                </TableCell>
                <TableCell>
                  <span className="font-medium capitalize">{c.token}</span>
                  {isExpanded && c.topTerms.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {c.topTerms.map((term, i) => (
                        <p
                          key={i}
                          className="ml-2 text-xs text-muted-foreground"
                        >
                          {term}
                        </p>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-right">{c.termCount}</TableCell>
                <TableCell className="text-right">
                  {c.impressions.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">{formatDollars(c.spend)}</TableCell>
                <TableCell className="text-right">{formatDollars(c.revenue)}</TableCell>
                <TableCell className="text-right">{c.roas.toFixed(2)}x</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
