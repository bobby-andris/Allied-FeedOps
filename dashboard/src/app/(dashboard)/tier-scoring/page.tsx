'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { HeroCallout } from './components/HeroCallout'
import { GroupOverview } from './components/GroupOverview'
import { GroupDetail } from './components/GroupDetail'
import { TierDetail } from './components/TierDetail'
import { TermScorecard } from './components/TermScorecard'
import { useTierScoring } from './hooks/useTierScoring'
import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

export default function TierScoringPage() {
  const { data, loading, error, refresh } = useTierScoring()
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [selectedTier, setSelectedTier] = useState<FunnelTier | null>(null)
  const [selectedTerm, setSelectedTerm] = useState<TermScore | null>(null)

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48 mb-2" />
            <Skeleton className="h-4 w-96" />
          </div>
          <Skeleton className="h-9 w-24" />
        </div>
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
            <AlertCircle className="h-10 w-10 text-destructive" />
            <p className="text-lg font-medium">Failed to load tier intelligence</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" onClick={() => refresh()}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!data) return null

  const computedDate = new Date(data.computedAt)
  const formattedDate = computedDate.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tier Intelligence</h1>
          <p className="text-muted-foreground">
            Data-driven tier analysis — surfaces high-confidence opportunities where performance disagrees with current placement
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Last computed: {formattedDate}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh(true)}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      <HeroCallout
        heroText={data.heroCallout}
        totalMisplaced={data.totalMisplaced}
        totalImpact={data.totalImpact}
        totalTermsScored={data.totalTermsScored}
      />

      {selectedTerm ? (
        <TermScorecard
          term={selectedTerm}
          onBack={() => setSelectedTerm(null)}
        />
      ) : selectedTier && selectedGroup ? (
        <TierDetail
          tier={selectedTier}
          distribution={data.distributions[selectedGroup].tiers[selectedTier]}
          scores={data.scores.filter(s =>
            s.customLabel0 === selectedGroup && s.currentTier === selectedTier
          )}
          groupName={selectedGroup}
          onBack={() => setSelectedTier(null)}
          onSelectTerm={(term) => setSelectedTerm(term)}
        />
      ) : selectedGroup ? (
        <GroupDetail
          group={data.distributions[selectedGroup]}
          scores={data.scores.filter(s => s.customLabel0 === selectedGroup)}
          onBack={() => {
            setSelectedGroup(null)
            setSelectedTier(null)
            setSelectedTerm(null)
          }}
          onSelectTier={(tier) => setSelectedTier(tier)}
        />
      ) : (
        <GroupOverview
          distributions={data.distributions}
          scores={data.scores}
          onSelectGroup={(group) => setSelectedGroup(group)}
        />
      )}
    </div>
  )
}
