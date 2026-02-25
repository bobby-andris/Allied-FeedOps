import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ConfidenceLevel } from '@/lib/optimization/tier-scoring.types'

interface ConfidenceBadgeProps {
  level: ConfidenceLevel
  score?: number
}

const colorMap: Record<ConfidenceLevel, string> = {
  High: 'bg-green-100 text-green-800 border-green-200',
  Medium: 'bg-amber-100 text-amber-800 border-amber-200',
  Low: 'bg-red-100 text-red-800 border-red-200',
}

export function ConfidenceBadge({ level, score }: ConfidenceBadgeProps) {
  return (
    <Badge variant="outline" className={cn('text-xs font-medium', colorMap[level])}>
      {level}
      {score !== undefined && ` (${score.toFixed(2)})`}
    </Badge>
  )
}
