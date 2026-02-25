'use client'

import { Card, CardContent } from '@/components/ui/card'
import { CheckCircle2, AlertTriangle, BarChart3, Target, DollarSign } from 'lucide-react'
import type { ImpactRange } from '@/lib/optimization/tier-scoring.types'

interface HeroCalloutProps {
  heroText: string
  totalMisplaced: number
  totalImpact: ImpactRange
  totalTermsScored: number
}

function formatDollars(amount: number): string {
  if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(1)}K`
  }
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

export function HeroCallout({ heroText, totalMisplaced, totalImpact, totalTermsScored }: HeroCalloutProps) {
  const isAllGood = totalMisplaced === 0

  return (
    <Card className={isAllGood ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-amber-500'}>
      <CardContent className="pt-6">
        <div className="flex items-start gap-3">
          {isAllGood ? (
            <CheckCircle2 className="h-6 w-6 text-green-500 mt-0.5 shrink-0" />
          ) : (
            <AlertTriangle className="h-6 w-6 text-amber-500 mt-0.5 shrink-0" />
          )}
          <div className="space-y-3 flex-1">
            <p className="text-lg font-semibold leading-snug">
              {isAllGood
                ? 'All terms align with current tier assignments — no action needed'
                : heroText}
            </p>
            {totalMisplaced > 0 && (
              <p className="text-sm text-muted-foreground mt-1">
                Tiers were assigned by business judgment. These are cases where performance data strongly disagrees.
              </p>
            )}
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-1.5 rounded-md bg-muted px-3 py-1.5 text-sm">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{totalTermsScored.toLocaleString()}</span>
                <span className="text-muted-foreground">terms scored</span>
              </div>
              <div className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm ${
                isAllGood ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'
              }`}>
                <Target className="h-4 w-4" />
                <span className="font-medium">{totalMisplaced.toLocaleString()}</span>
                <span>{totalMisplaced !== 1 ? 'opportunities' : 'opportunity'}</span>
              </div>
              {!isAllGood && (
                <div className="flex items-center gap-1.5 rounded-md bg-blue-50 text-blue-800 px-3 py-1.5 text-sm">
                  <DollarSign className="h-4 w-4" />
                  <span className="font-medium">
                    {formatDollars(totalImpact.low)}&ndash;{formatDollars(totalImpact.high)}
                  </span>
                  <span>/mo opportunity</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
