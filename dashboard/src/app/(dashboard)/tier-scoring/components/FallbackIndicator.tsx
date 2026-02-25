import { Info, AlertTriangle } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { FallbackLevel } from '@/lib/optimization/tier-scoring.types'

interface FallbackIndicatorProps {
  level: FallbackLevel
  groupName?: string
  tierName?: string
}

export function FallbackIndicator({ level, groupName, tierName }: FallbackIndicatorProps) {
  if (level === 'per_group') {
    return null
  }

  if (level === 'global') {
    const explanation = groupName && tierName
      ? `Limited terms in ${groupName} ${tierName} tier — using all groups combined for scoring`
      : 'Using category-wide averages for scoring due to limited group data'

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex items-center gap-1 text-xs text-amber-600">
              <Info className="h-3 w-3" />
              <span>Global fallback</span>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p className="max-w-xs">{explanation}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  // defaults
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 text-xs text-red-600">
            <AlertTriangle className="h-3 w-3" />
            <span>Default baselines</span>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="max-w-xs">
            Scored using default baselines — not enough real data for statistical scoring
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
