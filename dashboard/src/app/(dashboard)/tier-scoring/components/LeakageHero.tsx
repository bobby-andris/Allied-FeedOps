'use client'

import { Card, CardContent } from '@/components/ui/card'
import { CheckCircle2 } from 'lucide-react'
import { formatDollars } from '@/lib/formatting'
import type { ImpactRange } from '@/lib/optimization/tier-scoring.types'

interface LeakageHeroProps {
  totalImpact: ImpactRange
  avgConfidence: number
  actionableCount: number
  computedAt: string
}

function getConfidenceDotColor(avgConfidence: number): string {
  if (avgConfidence >= 0.70) return 'bg-green-500'
  if (avgConfidence >= 0.40) return 'bg-yellow-500'
  return 'bg-red-500'
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function LeakageHero({
  totalImpact,
  avgConfidence,
  actionableCount,
  computedAt,
}: LeakageHeroProps) {
  if (actionableCount === 0) {
    return (
      <Card className="border-l-4 border-l-green-500">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="h-6 w-6 text-green-500 mt-0.5 shrink-0" />
            <div>
              <h2 className="text-lg font-semibold">No revenue leakage detected</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Last computed {formatTimestamp(computedAt)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-l-4 border-l-amber-500">
      <CardContent className="pt-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${getConfidenceDotColor(avgConfidence)}`} />
            <h2 className="text-lg font-semibold">
              {formatDollars(totalImpact.low)} &ndash; {formatDollars(totalImpact.high)}/mo{' '}
              <span className="text-muted-foreground font-normal">
                (est. {formatDollars(totalImpact.mid)})
              </span>
            </h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Last computed {formatTimestamp(computedAt)}
          </p>
          <p className="text-sm text-muted-foreground">
            {actionableCount} {actionableCount === 1 ? 'term needs' : 'terms need'} review
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

// Export helpers for testing
export { getConfidenceDotColor, formatTimestamp }
