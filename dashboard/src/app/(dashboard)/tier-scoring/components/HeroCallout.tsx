import type { ImpactRange } from '@/lib/optimization/tier-scoring.types'

interface HeroCalloutProps {
  heroText: string
  totalMisplaced: number
  totalImpact: ImpactRange
  totalTermsScored: number
}

export function HeroCallout({ heroText, totalMisplaced, totalImpact, totalTermsScored }: HeroCalloutProps) {
  return <div>{heroText}</div>
}
