import type { ConfidenceLevel } from '@/lib/optimization/tier-scoring.types'

interface ConfidenceBadgeProps {
  level: ConfidenceLevel
  score?: number
}

export function ConfidenceBadge({ level, score }: ConfidenceBadgeProps) {
  return <span>{level}</span>
}
