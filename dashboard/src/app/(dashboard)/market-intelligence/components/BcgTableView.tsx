'use client'

import { useState, useMemo } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { ArrowUpDown } from 'lucide-react'
import type { ProductGroup } from '@/lib/market-intelligence/types'
import { BCG_QUADRANT_LABELS, BCG_COLORS } from '@/lib/market-intelligence/constants'
import { formatDollars } from '@/lib/formatting'

interface BcgTableViewProps {
  groups: ProductGroup[]
  onGroupClick: (customLabel0: string) => void
}

type SortField = 'customLabel0' | 'quadrant' | 'roas' | 'revenue' | 'spend' | 'trend' | 'termCount'
type SortDirection = 'asc' | 'desc'

export function BcgTableView({ groups, onGroupClick }: BcgTableViewProps) {
  const [sortField, setSortField] = useState<SortField>('revenue')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const sortedGroups = useMemo(() => {
    const sorted = [...groups].sort((a, b) => {
      const aVal = a[sortField]
      const bVal = b[sortField]
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }
      const aNum = Number(aVal)
      const bNum = Number(bVal)
      return sortDirection === 'asc' ? aNum - bNum : bNum - aNum
    })
    return sorted
  }, [groups, sortField, sortDirection])

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  function SortableHeader({ field, children }: { field: SortField; children: React.ReactNode }) {
    return (
      <TableHead
        className="cursor-pointer select-none hover:bg-muted/50"
        onClick={() => handleSort(field)}
      >
        <div className="flex items-center gap-1">
          {children}
          <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
        </div>
      </TableHead>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <SortableHeader field="customLabel0">Product Group</SortableHeader>
          <SortableHeader field="quadrant">Quadrant</SortableHeader>
          <SortableHeader field="roas">ROAS</SortableHeader>
          <SortableHeader field="revenue">Revenue</SortableHeader>
          <SortableHeader field="spend">Spend</SortableHeader>
          <SortableHeader field="trend">Trend</SortableHeader>
          <SortableHeader field="termCount">Terms</SortableHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedGroups.map(group => {
          const quadrantInfo = BCG_QUADRANT_LABELS[group.quadrant]
          const trendColor =
            group.trendDirection === 'up'
              ? 'text-green-600'
              : group.trendDirection === 'down'
                ? 'text-red-600'
                : 'text-muted-foreground'

          return (
            <TableRow
              key={group.customLabel0}
              className="hover:bg-muted/50 cursor-pointer"
              onClick={() => onGroupClick(group.customLabel0)}
            >
              <TableCell className="font-medium">{group.customLabel0}</TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  style={{
                    borderColor: BCG_COLORS[group.quadrant],
                    color: BCG_COLORS[group.quadrant],
                  }}
                >
                  {quadrantInfo?.label || group.quadrant}
                </Badge>
              </TableCell>
              <TableCell>{group.roas.toFixed(2)}x</TableCell>
              <TableCell>{formatDollars(group.revenue)}</TableCell>
              <TableCell>{formatDollars(group.spend)}</TableCell>
              <TableCell>
                <span className={trendColor}>
                  {group.trend > 0 ? '+' : ''}{group.trend.toFixed(1)}%
                </span>
              </TableCell>
              <TableCell>{group.termCount}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
