import type { FallbackLevel } from '@/lib/optimization/tier-scoring.types'

interface FallbackIndicatorProps {
  level: FallbackLevel
  groupName?: string
  tierName?: string
}

export function FallbackIndicator({ level, groupName, tierName }: FallbackIndicatorProps) {
  return null
}
