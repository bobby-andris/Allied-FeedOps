import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { REASON_LABELS, REASON_COLORS } from '../lib/reason-codes'
import type { ReasonCode } from '../lib/reason-codes'

interface ReasonBadgeProps {
  reasonCode: ReasonCode
}

export function ReasonBadge({ reasonCode }: ReasonBadgeProps) {
  return (
    <Badge variant="outline" className={cn('text-xs font-medium', REASON_COLORS[reasonCode])}>
      {REASON_LABELS[reasonCode]}
    </Badge>
  )
}
