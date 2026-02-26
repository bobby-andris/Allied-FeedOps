'use client'

import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, Clock } from 'lucide-react'
import { HistoryDayGroup } from './HistoryDayGroup'
import type { HistoryEntry } from '../hooks/useRecommendations'

interface HistoryViewProps {
  history: HistoryEntry[]
  historyLoading: boolean
  onUndo: (searchTerm: string, customLabel0: string) => void
  onLoadHistory: () => void
}

interface DayGroup {
  date: string
  entries: HistoryEntry[]
}

/**
 * Group history entries by day (reverse chronological).
 * Entries within a day are sorted most-recent-first.
 * Exported for unit testing.
 */
export function groupHistoryByDay(entries: HistoryEntry[]): DayGroup[] {
  if (entries.length === 0) return []

  const groups = new Map<string, HistoryEntry[]>()

  for (const entry of entries) {
    const ts = entry.accepted_at || entry.created_at
    const dateKey = new Date(ts).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
    const existing = groups.get(dateKey) ?? []
    existing.push(entry)
    groups.set(dateKey, existing)
  }

  // Sort entries within each day (most recent first)
  for (const [, dayEntries] of groups) {
    dayEntries.sort((a, b) => {
      const tsA = new Date(a.accepted_at || a.created_at).getTime()
      const tsB = new Date(b.accepted_at || b.created_at).getTime()
      return tsB - tsA
    })
  }

  // Sort day groups reverse chronologically
  const sortedDays = Array.from(groups.entries()).sort((a, b) => {
    const dateA = new Date(a[1][0].accepted_at || a[1][0].created_at).getTime()
    const dateB = new Date(b[1][0].accepted_at || b[1][0].created_at).getTime()
    return dateB - dateA
  })

  return sortedDays.map(([date, dayEntries]) => ({ date, entries: dayEntries }))
}

export function HistoryView({
  history,
  historyLoading,
  onUndo,
  onLoadHistory,
}: HistoryViewProps) {
  // Load history on mount
  useEffect(() => {
    onLoadHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (historyLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ))}
      </div>
    )
  }

  const dayGroups = groupHistoryByDay(history)

  if (dayGroups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
        <Clock className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          No actions taken yet — review terms in the Revenue Leakage tab to get started
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={onLoadHistory} className="gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {dayGroups.map(group => (
        <HistoryDayGroup
          key={group.date}
          date={group.date}
          entries={group.entries}
          onUndo={onUndo}
        />
      ))}
    </div>
  )
}
