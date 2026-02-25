import type { GroupDistributions, TermScore } from '@/lib/optimization/tier-scoring.types'

interface GroupOverviewProps {
  distributions: Record<string, GroupDistributions>
  scores: TermScore[]
  onSelectGroup: (group: string) => void
}

export function GroupOverview({ distributions, scores, onSelectGroup }: GroupOverviewProps) {
  return <div>Groups overview</div>
}
