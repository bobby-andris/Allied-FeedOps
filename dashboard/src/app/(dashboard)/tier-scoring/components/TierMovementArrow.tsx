'use client'

import { ArrowUp, ArrowDown, Minus } from 'lucide-react'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface TierMovementArrowProps {
  current: FunnelTier
  recommended: FunnelTier
  /** If provided, overrides recommended for arrow direction and destination label */
  targetTier?: FunnelTier
}

const tierRank: Record<FunnelTier, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }

const tierColor: Record<FunnelTier, string> = {
  HIGH: 'text-emerald-700',
  MEDIUM: 'text-blue-700',
  LOW: 'text-amber-700',
}

const tierBg: Record<FunnelTier, string> = {
  HIGH: 'bg-emerald-50',
  MEDIUM: 'bg-blue-50',
  LOW: 'bg-amber-50',
}

export function TierMovementArrow({ current, recommended, targetTier }: TierMovementArrowProps) {
  const destination = targetTier ?? recommended
  const goingUp = tierRank[destination] > tierRank[current]
  const same = current === destination

  if (same) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="h-3 w-3" />
        {current}
      </span>
    )
  }

  return (
    <span className="flex items-center gap-1.5 shrink-0">
      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${tierBg[current]} ${tierColor[current]}`}>
        {current}
      </span>
      {goingUp ? (
        <ArrowUp className="h-3.5 w-3.5 text-emerald-600" />
      ) : (
        <ArrowDown className="h-3.5 w-3.5 text-orange-600" />
      )}
      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${tierBg[destination]} ${tierColor[destination]}`}>
        {destination}
      </span>
    </span>
  )
}
