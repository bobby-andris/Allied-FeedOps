import type { MetricDistribution } from '@/lib/optimization/tier-scoring.types'

interface DistributionChartProps {
  distribution: MetricDistribution
  metricName: string
  tierColor: string
  terms?: number[]
}

export function DistributionChart({ distribution, metricName, tierColor, terms }: DistributionChartProps) {
  return <div>Distribution chart</div>
}
