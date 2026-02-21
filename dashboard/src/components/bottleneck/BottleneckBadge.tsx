/**
 * BottleneckBadge — color-coded inline badge for SKU bottleneck classification
 *
 * Usage example (in ReviewListClient or any SKU table):
 *   import { BottleneckBadge } from '@/components/bottleneck/BottleneckBadge'
 *   <BottleneckBadge classification="coverage_gap" confidence={0.95} />
 *   <BottleneckBadge classification="auction_bid" isOverride />
 */

import { Badge } from '@/components/ui/badge'

const BOTTLENECK_COLORS: Record<string, string> = {
  coverage_gap: 'bg-gray-100 text-gray-800 hover:bg-gray-100',
  code_path_gap: 'bg-purple-100 text-purple-800 hover:bg-purple-100',
  query_relevance: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
  propagation_failure: 'bg-orange-100 text-orange-800 hover:bg-orange-100',
  auction_bid: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
}

const BOTTLENECK_LABELS: Record<string, string> = {
  coverage_gap: 'Coverage Gap',
  code_path_gap: 'Code Path Gap',
  query_relevance: 'Query Relevance',
  propagation_failure: 'Propagation Failure',
  auction_bid: 'Auction/Bid',
}

interface BottleneckBadgeProps {
  classification: string
  confidence?: number
  isOverride?: boolean
  className?: string
}

export function BottleneckBadge({
  classification,
  confidence,
  isOverride = false,
  className = '',
}: BottleneckBadgeProps) {
  const colorClass = BOTTLENECK_COLORS[classification] ?? 'bg-gray-100 text-gray-600 hover:bg-gray-100'
  const label = BOTTLENECK_LABELS[classification] ?? classification

  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <Badge className={colorClass}>
        {label}
        {confidence !== undefined && (
          <span className="ml-1 opacity-70 text-xs">
            {Math.round(confidence * 100)}%
          </span>
        )}
      </Badge>
      {isOverride && (
        <span className="text-xs text-muted-foreground border border-dashed rounded px-1">
          Override
        </span>
      )}
    </span>
  )
}
