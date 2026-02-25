'use client'

import { formatDollars } from '@/lib/formatting'
import type { ImpactRange } from '@/lib/optimization/tier-scoring.types'

interface ImpactBadgeProps {
  impact: ImpactRange | null
}

export function ImpactBadge({ impact }: ImpactBadgeProps) {
  if (!impact) {
    return <span className="text-xs text-muted-foreground">&mdash;</span>
  }

  return (
    <span className="inline-flex items-center rounded-md bg-blue-50 text-blue-800 px-2 py-0.5 text-xs font-medium whitespace-nowrap">
      {formatDollars(impact.low)}&ndash;{formatDollars(impact.high)}/mo
    </span>
  )
}
