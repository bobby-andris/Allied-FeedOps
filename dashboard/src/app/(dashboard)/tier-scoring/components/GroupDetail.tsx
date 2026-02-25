import type { GroupDistributions, TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

interface GroupDetailProps {
  group: GroupDistributions
  scores: TermScore[]
  onBack: () => void
  onSelectTier: (tier: FunnelTier) => void
}

export function GroupDetail({ group, scores, onBack, onSelectTier }: GroupDetailProps) {
  return <div>Group detail</div>
}
