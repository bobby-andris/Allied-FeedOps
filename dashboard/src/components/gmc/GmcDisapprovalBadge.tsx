import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface GmcDisapprovalBadgeProps {
  issueCount: number
  disapprovalCount: number
}

/**
 * Inline badge showing GMC issue counts.
 *
 * - disapprovalCount > 0: red badge with AlertTriangle icon
 * - issueCount > 0 but no disapprovals: yellow badge (limited/warnings only)
 * - issueCount === 0: renders nothing
 */
export function GmcDisapprovalBadge({
  issueCount,
  disapprovalCount,
}: GmcDisapprovalBadgeProps) {
  if (issueCount === 0) return null

  const isDisapproval = disapprovalCount > 0
  const count = disapprovalCount > 0 ? disapprovalCount : issueCount
  const label = isDisapproval ? `${count} disapproval${count !== 1 ? 's' : ''}` : `${count} warning${count !== 1 ? 's' : ''}`
  const tooltipText =
    disapprovalCount > 0
      ? `GMC: ${disapprovalCount} disapproval${disapprovalCount !== 1 ? 's' : ''}${issueCount > disapprovalCount ? `, ${issueCount - disapprovalCount} warning${issueCount - disapprovalCount !== 1 ? 's' : ''}` : ''}`
      : `GMC: ${issueCount} warning${issueCount !== 1 ? 's' : ''}`

  return (
    <Badge
      title={tooltipText}
      className={
        isDisapproval
          ? 'bg-red-100 text-red-800 border-red-200 hover:bg-red-100 cursor-default gap-1'
          : 'bg-yellow-100 text-yellow-800 border-yellow-200 hover:bg-yellow-100 cursor-default gap-1'
      }
    >
      <AlertTriangle className="h-3 w-3" />
      {label}
    </Badge>
  )
}
