'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CheckCircle2, TrendingUp, Zap } from 'lucide-react'
import { formatDollars } from '@/lib/formatting'
import type { ImpactRange } from '@/lib/optimization/tier-scoring.types'

interface HeroSummaryProps {
  totalMisplaced: number
  totalImpact: ImpactRange
  totalTermsScored: number
  computedAt: string
  onApplyClick?: () => void
}

export function HeroSummary({
  totalMisplaced,
  totalImpact,
  totalTermsScored,
  computedAt,
  onApplyClick,
}: HeroSummaryProps) {
  const isAllGood = totalMisplaced === 0
  const computedDate = new Date(computedAt)
  const formattedDate = computedDate.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  if (isAllGood) {
    return (
      <Card className="border-l-4 border-l-green-500">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="h-6 w-6 text-green-500 mt-0.5 shrink-0" />
            <div>
              <h2 className="text-lg font-semibold">
                All {totalTermsScored.toLocaleString()} terms are performing well in their current tiers
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                No action needed. Last analyzed {formattedDate}.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardContent className="pt-6">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <TrendingUp className="h-6 w-6 text-blue-500 mt-0.5 shrink-0" />
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">
                {totalMisplaced} search {totalMisplaced === 1 ? 'term' : 'terms'} could perform better in a different tier
              </h2>
              <p className="text-sm text-muted-foreground">
                Moving these terms to their recommended tiers could improve returns by{' '}
                <span className="font-semibold text-foreground">
                  {formatDollars(totalImpact.low)}&ndash;{formatDollars(totalImpact.high)}/mo
                </span>
                . Out of {totalTermsScored.toLocaleString()} terms analyzed.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button className="gap-1.5" onClick={onApplyClick}>
              <Zap className="h-4 w-4" />
              Apply Recommendations
            </Button>
            <span className="text-xs text-muted-foreground">
              Last analyzed {formattedDate}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
