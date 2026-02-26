'use client'

import { useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AlertCircle, RefreshCw, LayoutList, Search, DollarSign, Clock } from 'lucide-react'
import { useTierScoring } from './hooks/useTierScoring'
import { useRecommendations } from './hooks/useRecommendations'
import { classifyAllTerms } from './lib/reason-codes'

// Action Queue components
import { HeroSummary } from './components/HeroSummary'
import { ActionQueueTable } from './components/ActionQueueTable'

// Revenue Leakage components
import { LeakageHero } from './components/LeakageHero'
import { RoasBoxPlot } from './components/RoasBoxPlot'
import { LeakageTermList } from './components/LeakageTermList'
import { BatchApproveBar } from './components/BatchApproveBar'

// History components
import { HistoryView } from './components/HistoryView'

// Explorer view components (preserved from Phase 33)
import { HeroCallout } from './components/HeroCallout'
import { GroupOverview } from './components/GroupOverview'
import { GroupDetail } from './components/GroupDetail'
import { TierDetail } from './components/TierDetail'
import { TermScorecard } from './components/TermScorecard'

import type { TermScore } from '@/lib/optimization/tier-scoring.types'
import type { FunnelTier } from '@/lib/shopping-funnel/types'

export default function TierScoringPage() {
  const { data, loading, error, refresh } = useTierScoring()
  const recommendations = useRecommendations()

  // Tab state (controlled for programmatic switching)
  const [activeTab, setActiveTab] = useState('actions')

  // Action Queue view state
  const [actionSelectedTerm, setActionSelectedTerm] = useState<TermScore | null>(null)

  // Explorer view state (preserved from Phase 33)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [selectedTier, setSelectedTier] = useState<FunnelTier | null>(null)
  const [selectedTerm, setSelectedTerm] = useState<TermScore | null>(null)

  // Revenue Leakage computed data
  const classifiedTerms = useMemo(() => {
    if (!data) return []
    return classifyAllTerms(data.scores)
  }, [data])

  const pendingTerms = useMemo(() => {
    return classifiedTerms.filter(t => {
      const status = recommendations.getStatus(t.searchTerm, t.customLabel0)
      return !status || status.status === 'pending' || status.status === 'rejected'
    })
  }, [classifiedTerms, recommendations])

  const highConfidenceCount = useMemo(() => {
    return pendingTerms.filter(t => t.confidence.score > 0.80).length
  }, [pendingTerms])

  const avgConfidence = useMemo(() => {
    if (pendingTerms.length === 0) return 0
    return pendingTerms.reduce((sum, t) => sum + t.confidence.score, 0) / pendingTerms.length
  }, [pendingTerms])

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

  return (
    <div className="space-y-6 p-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tier Intelligence</h1>
          <p className="text-muted-foreground">
            Data-driven tier analysis — surfaces high-confidence opportunities where performance disagrees with current placement
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refresh(true)}
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      {/* Four-view Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="actions" className="gap-1.5">
            <LayoutList className="h-3.5 w-3.5" />
            Action Queue
          </TabsTrigger>
          <TabsTrigger value="explorer" className="gap-1.5">
            <Search className="h-3.5 w-3.5" />
            Explorer
          </TabsTrigger>
          <TabsTrigger value="leakage" className="gap-1.5">
            <DollarSign className="h-3.5 w-3.5" />
            Revenue Leakage
            {pendingTerms.length > 0 && (
              <span className="ml-1 rounded-full bg-amber-100 text-amber-800 px-1.5 py-0.5 text-xs font-medium">
                {pendingTerms.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            History
          </TabsTrigger>
        </TabsList>

        {/* ACTION QUEUE TAB */}
        <TabsContent value="actions" className="space-y-6 mt-4">
          {actionSelectedTerm ? (
            <TermScorecard
              term={actionSelectedTerm}
              onBack={() => setActionSelectedTerm(null)}
            />
          ) : (
            <>
              <HeroSummary
                totalMisplaced={data.totalMisplaced}
                totalImpact={data.totalImpact}
                totalTermsScored={data.totalTermsScored}
                computedAt={data.computedAt}
                onApplyClick={() => setActiveTab('leakage')}
              />
              <ActionQueueTable
                scores={data.scores}
                onSelectTerm={(term) => setActionSelectedTerm(term)}
                recommendationStatuses={recommendations.statuses}
                onUndo={recommendations.undo}
              />
            </>
          )}
        </TabsContent>

        {/* EXPLORER TAB */}
        <TabsContent value="explorer" className="space-y-6 mt-4">
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
        </TabsContent>

        {/* REVENUE LEAKAGE TAB */}
        <TabsContent value="leakage" className="space-y-6 mt-4">
          <LeakageHero
            totalImpact={data.totalImpact}
            avgConfidence={avgConfidence}
            actionableCount={pendingTerms.length}
            computedAt={data.computedAt}
          />
          <RoasBoxPlot distributions={data.distributions} />
          <BatchApproveBar
            highConfidenceCount={highConfidenceCount}
            onBatchApprove={() => {
              const highConfTerms = pendingTerms.filter(t => t.confidence.score > 0.80)
              recommendations.batchApprove(highConfTerms)
            }}
          />
          <LeakageTermList
            terms={pendingTerms}
            statuses={recommendations.statuses}
            onApprove={recommendations.approve}
            onReject={recommendations.reject}
            onUndo={recommendations.undo}
            onViewDetails={setActionSelectedTerm}
          />
        </TabsContent>

        {/* HISTORY TAB */}
        <TabsContent value="history" className="space-y-6 mt-4">
          <HistoryView
            history={recommendations.history}
            historyLoading={recommendations.historyLoading}
            onUndo={recommendations.undo}
            onLoadHistory={recommendations.loadHistory}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
