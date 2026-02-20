'use client'

import { useCallback, useDeferredValue, useEffect, useMemo, useState, useTransition } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  RefreshCw,
  Search,
  Send,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type {
  AssignmentTier,
  DecisionActionType,
  ExistingFunnelResponse,
  ExistingFunnelTerm,
  ExistingFunnelUpdateResult,
  NeedsDecisionResponse,
  NeedsDecisionTerm,
  StagedDecisionsResponse,
  StagedDecisionSnapshot,
  ShoppingFunnelLineageResponse,
} from '@/lib/shopping-funnel/types'
import {
  buildDecisionItem,
  createDecisionSignature,
  getDecisionCompletion,
} from '@/lib/shopping-funnel/decision-staging'
import {
  EXISTING_FUNNEL_UI_LIMIT,
  NEEDS_DECISION_UI_LIMIT,
} from '@/lib/shopping-funnel/ui-performance'

type DateRangePreset = '7d' | '30d' | '60d' | '90d'

interface NeedsDecisionState {
  selected: boolean
  actionType: DecisionActionType
  assignments: Partial<Record<string, AssignmentTier>>
  stagedSignature: string | null
  stagedAt: string | null
}

interface ExistingUpdateState {
  search_term: string
  custom_label_0: string
  new_tier?: AssignmentTier
  new_action?: 'global_block' | 'competitor' | 'branded'
}

type NeedsSortOption =
  | 'impact_desc'
  | 'impressions_desc'
  | 'cost_desc'
  | 'conversions_desc'
  | 'labels_desc'
  | 'search_asc'

type ExistingSortOption =
  | 'errors_first'
  | 'impressions_desc'
  | 'cost_desc'
  | 'conversions_desc'
  | 'search_asc'

interface NeedsTermMetrics {
  impressions: number
  clicks: number
  costMicros: number
  conversions: number
  conversionsValue: number
}

type StagedDecisionMap = Record<string, StagedDecisionSnapshot>

const DATE_RANGE_OPTIONS: Array<{ label: string; value: DateRangePreset }> = [
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
  { label: 'Last 60 days', value: '60d' },
  { label: 'Last 90 days', value: '90d' },
]

const ACTION_OPTIONS: Array<{ value: DecisionActionType; label: string }> = [
  { value: 'funnel', label: 'Funnel Term' },
  { value: 'global_block', label: 'Global Block' },
  { value: 'competitor', label: 'Competitor Term' },
  { value: 'branded', label: 'Branded Term' },
]

const ACTION_LABEL_BY_VALUE: Record<DecisionActionType, string> = Object.fromEntries(
  ACTION_OPTIONS.map((option) => [option.value, option.label])
) as Record<DecisionActionType, string>

const TIER_OPTIONS: Array<{ value: AssignmentTier; label: string }> = [
  { value: 'campaign_negative', label: 'Campaign Negative' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const NEEDS_DECISION_LIMIT = NEEDS_DECISION_UI_LIMIT
const EXISTING_FUNNEL_LIMIT = EXISTING_FUNNEL_UI_LIMIT

const EXISTING_ASSIGNMENT_OPTIONS: Array<{
  value: AssignmentTier | 'global_block' | 'competitor' | 'branded'
  label: string
}> = [
  { value: 'campaign_negative', label: 'Campaign Negative' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'global_block', label: 'Move to Global Block' },
  { value: 'competitor', label: 'Move to Competitor Terms' },
  { value: 'branded', label: 'Move to Branded Terms' },
]

const NEEDS_SORT_OPTIONS: Array<{ value: NeedsSortOption; label: string }> = [
  { value: 'impact_desc', label: 'Impact score (high to low)' },
  { value: 'impressions_desc', label: 'Impressions (high to low)' },
  { value: 'cost_desc', label: 'Cost (high to low)' },
  { value: 'conversions_desc', label: 'Conversions (high to low)' },
  { value: 'labels_desc', label: 'Custom labels (high to low)' },
  { value: 'search_asc', label: 'Search term (A-Z)' },
]

const EXISTING_SORT_OPTIONS: Array<{ value: ExistingSortOption; label: string }> = [
  { value: 'errors_first', label: 'Errors first' },
  { value: 'impressions_desc', label: 'Impressions (high to low)' },
  { value: 'cost_desc', label: 'Cost (high to low)' },
  { value: 'conversions_desc', label: 'Conversions (high to low)' },
  { value: 'search_asc', label: 'Search term (A-Z)' },
]

function fromExistingTierLabel(value: ExistingFunnelTerm['funnels'][number]['tier']): AssignmentTier | null {
  if (value === 'Campaign Negative') return 'campaign_negative'
  if (value === 'High') return 'high'
  if (value === 'Medium') return 'medium'
  if (value === 'Low') return 'low'
  return null
}

function updateKey(searchTerm: string, customLabel0: string): string {
  return `${searchTerm}|${customLabel0}`
}

function aggregateNeedsMetrics(term: NeedsDecisionTerm): NeedsTermMetrics {
  return term.custom_label_0s.reduce<NeedsTermMetrics>(
    (acc, item) => {
      acc.impressions += item.impressions
      acc.clicks += item.clicks
      acc.costMicros += item.cost_micros
      acc.conversions += item.conversions
      acc.conversionsValue += item.conversions_value
      return acc
    },
    {
      impressions: 0,
      clicks: 0,
      costMicros: 0,
      conversions: 0,
      conversionsValue: 0,
    }
  )
}

function createRecommendedNeedsState(term: NeedsDecisionTerm): NeedsDecisionState {
  const recommendedAction = term.recommendation?.action_type ?? 'funnel'
  const defaultTier = term.recommendation?.default_tier
  const assignments: Partial<Record<string, AssignmentTier>> = {}

  if (recommendedAction === 'funnel' && defaultTier) {
    for (const assignment of term.custom_label_0s) {
      assignments[assignment.custom_label_0] = defaultTier
    }
  }

  return {
    selected: false,
    actionType: recommendedAction,
    assignments,
    stagedSignature: null,
    stagedAt: null,
  }
}

function applyStagedDecisionToState(
  term: NeedsDecisionTerm,
  baseState: NeedsDecisionState,
  snapshot?: StagedDecisionSnapshot
): NeedsDecisionState {
  if (!snapshot) {
    return baseState
  }

  if (snapshot.action_type !== 'funnel') {
    const decisionItem = buildDecisionItem(term, {
      actionType: snapshot.action_type,
      assignments: {},
    })
    return {
      ...baseState,
      actionType: snapshot.action_type,
      assignments: {},
      stagedSignature: createDecisionSignature(decisionItem),
      stagedAt: snapshot.staged_at,
    }
  }

  const assignmentMap: Partial<Record<string, AssignmentTier>> = {}
  for (const assignment of snapshot.assignments ?? []) {
    assignmentMap[assignment.custom_label_0] = assignment.tier
  }
  const decisionItem = buildDecisionItem(term, {
    actionType: 'funnel',
    assignments: assignmentMap,
  })

  return {
    ...baseState,
    actionType: 'funnel',
    assignments: assignmentMap,
    stagedSignature: createDecisionSignature(decisionItem),
    stagedAt: snapshot.staged_at,
  }
}

export default function ShoppingFunnelPage() {
  const [isTransitionPending, startTransition] = useTransition()
  const [activeTab, setActiveTab] = useState<'needs-decision' | 'existing-funnel'>('needs-decision')
  const [range, setRange] = useState<DateRangePreset>('30d')
  const [customLabelFilter, setCustomLabelFilter] = useState<string>('all')
  const [minImpressions, setMinImpressions] = useState<string>('0')
  const [showErrorsOnly, setShowErrorsOnly] = useState<boolean>(false)
  const [needsSearch, setNeedsSearch] = useState<string>('')
  const [existingSearch, setExistingSearch] = useState<string>('')
  const [needsSort, setNeedsSort] = useState<NeedsSortOption>('impact_desc')
  const [existingSort, setExistingSort] = useState<ExistingSortOption>('errors_first')
  const [showSelectedNeedsOnly, setShowSelectedNeedsOnly] = useState<boolean>(false)
  const [showPendingExistingOnly, setShowPendingExistingOnly] = useState<boolean>(false)
  const [bulkActionType, setBulkActionType] = useState<DecisionActionType>('funnel')
  const [bulkAssignmentTier, setBulkAssignmentTier] = useState<AssignmentTier>('campaign_negative')
  const [expandedNeedsTerms, setExpandedNeedsTerms] = useState<Record<string, boolean>>({})
  const [expandedExistingTerms, setExpandedExistingTerms] = useState<Record<string, boolean>>({})
  const [needsOffset, setNeedsOffset] = useState<number>(0)
  const [existingOffset, setExistingOffset] = useState<number>(0)

  const [needsLoading, setNeedsLoading] = useState<boolean>(false)
  const [existingLoading, setExistingLoading] = useState<boolean>(false)
  const [posting, setPosting] = useState<boolean>(false)
  const [staging, setStaging] = useState<boolean>(false)
  const [publishingStaged, setPublishingStaged] = useState<boolean>(false)

  const [needsData, setNeedsData] = useState<NeedsDecisionResponse | null>(null)
  const [existingData, setExistingData] = useState<ExistingFunnelResponse | null>(null)
  const [lineageData, setLineageData] = useState<ShoppingFunnelLineageResponse | null>(null)
  const [lineageLoading, setLineageLoading] = useState<boolean>(false)
  const [stagedQueueCount, setStagedQueueCount] = useState<number>(0)

  const [needsState, setNeedsState] = useState<Record<string, NeedsDecisionState>>({})
  const [existingUpdates, setExistingUpdates] = useState<Record<string, ExistingUpdateState>>({})

  const [message, setMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const deferredNeedsSearch = useDeferredValue(needsSearch)
  const deferredExistingSearch = useDeferredValue(existingSearch)

  const activeDataSource = useMemo(
    () =>
      activeTab === 'needs-decision'
        ? needsData?.data_source
        : existingData?.data_source,
    [activeTab, existingData?.data_source, needsData?.data_source]
  )

  const activeGeneratedAt = useMemo(
    () =>
      activeTab === 'needs-decision'
        ? needsData?.generated_at
        : existingData?.generated_at,
    [activeTab, existingData?.generated_at, needsData?.generated_at]
  )

  const availableCustomLabels = useMemo(() => {
    const labels = new Set<string>(needsData?.custom_labels ?? [])
    for (const label of existingData?.custom_labels ?? []) {
      labels.add(label)
    }
    return Array.from(labels).sort((a, b) => a.localeCompare(b))
  }, [existingData?.custom_labels, needsData?.custom_labels])

  const minImpressionsNum = useMemo(() => {
    const parsed = Number(minImpressions)
    return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : 0
  }, [minImpressions])

  const fetchStagedDecisions = useCallback(async (searchTerms?: string[]) => {
    const fetchPayload = async (terms?: string[]) => {
      const response = await fetch('/api/search-terms/staged-decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_terms: terms,
        }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      return (await response.json()) as StagedDecisionsResponse
    }

    let payload: StagedDecisionsResponse
    try {
      payload = await fetchPayload(searchTerms)
    } catch (error) {
      // Fallback for large filter sets or transient route failures.
      if (searchTerms && searchTerms.length > 0) {
        payload = await fetchPayload(undefined)
      } else {
        throw error
      }
    }

    const byTerm: StagedDecisionMap = Object.fromEntries(
      payload.decisions.map((item) => [item.search_term, item])
    )
    setStagedQueueCount(payload.total_unposted_terms)
    return byTerm
  }, [])

  const fetchNeedsDecision = useCallback(async () => {
    setNeedsLoading(true)
    setErrorMessage(null)
    try {
      const params = new URLSearchParams({
        range,
        min_impressions: String(minImpressionsNum),
        limit: String(NEEDS_DECISION_LIMIT),
        offset: String(needsOffset),
        sort_by: needsSort === 'impact_desc' ? 'impact_desc' : 'impressions_desc',
      })
      if (customLabelFilter !== 'all') {
        params.set('custom_label_0', customLabelFilter)
      }
      const response = await fetch(`/api/search-terms/needs-decision?${params.toString()}`)
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const payload = (await response.json()) as NeedsDecisionResponse
      let stagedByTerm: StagedDecisionMap = {}
      try {
        stagedByTerm = await fetchStagedDecisions(payload.terms.map((term) => term.search_term))
      } catch (error) {
        console.warn('Unable to load staged decisions for shopping funnel', error)
        setStagedQueueCount(0)
      }
      setNeedsData(payload)

      const nextState: Record<string, NeedsDecisionState> = {}
      for (const term of payload.terms) {
        nextState[term.search_term] = applyStagedDecisionToState(
          term,
          createRecommendedNeedsState(term),
          stagedByTerm[term.search_term]
        )
      }
      setNeedsState(nextState)
      setExpandedNeedsTerms({})
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch needs-decision terms')
    } finally {
      setNeedsLoading(false)
    }
  }, [customLabelFilter, fetchStagedDecisions, minImpressionsNum, needsOffset, needsSort, range])

  const fetchExistingWithParams = useCallback(
    async ({
      rangeValue,
      customLabel,
      minImpressionsValue,
      errorsOnly,
      offsetValue,
    }: {
      rangeValue: DateRangePreset
      customLabel: string
      minImpressionsValue: number
      errorsOnly: boolean
      offsetValue: number
    }) => {
      const params = new URLSearchParams({
        range: rangeValue,
        min_impressions: String(minImpressionsValue),
        show_errors_only: errorsOnly ? 'true' : 'false',
        limit: String(EXISTING_FUNNEL_LIMIT),
        offset: String(offsetValue),
      })
      if (customLabel !== 'all') {
        params.set('custom_label_0', customLabel)
      }

      const response = await fetch(`/api/search-terms/existing-funnel?${params.toString()}`)
      if (!response.ok) {
        throw new Error(await response.text())
      }
      return (await response.json()) as ExistingFunnelResponse
    },
    []
  )

  const fetchExisting = useCallback(async () => {
    setExistingLoading(true)
    setErrorMessage(null)
    try {
      const payload = await fetchExistingWithParams({
        rangeValue: range,
        customLabel: customLabelFilter,
        minImpressionsValue: minImpressionsNum,
        errorsOnly: showErrorsOnly,
        offsetValue: existingOffset,
      })
      setExistingData(payload)
      setExistingUpdates({})
      setExpandedExistingTerms({})
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch existing funnel terms')
    } finally {
      setExistingLoading(false)
    }
  }, [customLabelFilter, existingOffset, fetchExistingWithParams, minImpressionsNum, range, showErrorsOnly])

  const fetchDataLineage = useCallback(async () => {
    setLineageLoading(true)
    try {
      const params = new URLSearchParams({ range })
      const response = await fetch(`/api/search-terms/data-lineage?${params.toString()}`)
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const payload = (await response.json()) as ShoppingFunnelLineageResponse
      setLineageData(payload)
    } catch (error) {
      console.error('Failed to fetch shopping funnel data lineage', error)
    } finally {
      setLineageLoading(false)
    }
  }, [range])

  const applyExistingFunnelFilters = useCallback(
    async ({
      customLabel,
      errorsOnly,
    }: {
      customLabel?: string
      errorsOnly?: boolean
    }) => {
      const nextCustomLabel = customLabel ?? customLabelFilter
      const nextErrorsOnly = errorsOnly ?? showErrorsOnly

      setCustomLabelFilter(nextCustomLabel)
      setShowErrorsOnly(nextErrorsOnly)
      setExistingOffset(0)
      setActiveTab('existing-funnel')

      setExistingLoading(true)
      setErrorMessage(null)
      try {
        const payload = await fetchExistingWithParams({
          rangeValue: range,
          customLabel: nextCustomLabel,
          minImpressionsValue: minImpressionsNum,
          errorsOnly: nextErrorsOnly,
          offsetValue: 0,
        })
        setExistingData(payload)
        setExistingUpdates({})
        setExpandedExistingTerms({})
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to fetch existing funnel terms')
      } finally {
        setExistingLoading(false)
      }
    },
    [
      customLabelFilter,
      fetchExistingWithParams,
      minImpressionsNum,
      range,
      showErrorsOnly,
      setActiveTab,
      setCustomLabelFilter,
      setExistingOffset,
      setShowErrorsOnly,
    ]
  )

  useEffect(() => {
    if (activeTab === 'needs-decision') {
      fetchNeedsDecision()
    } else {
      fetchExisting()
    }
  }, [activeTab, fetchExisting, fetchNeedsDecision])

  useEffect(() => {
    void fetchDataLineage()
  }, [fetchDataLineage])

  const selectedNeedsTerms = useMemo(
    () => Object.entries(needsState).filter(([, state]) => state.selected).map(([term]) => term),
    [needsState]
  )

  const needsRows = useMemo(() => {
    const normalizedSearch = deferredNeedsSearch.trim().toLowerCase()
    const rows =
      needsData?.terms
        .map((term) => {
          const state = needsState[term.search_term]
          if (!state) {
            return null
          }
          const completion = getDecisionCompletion(term, state)
          const decisionItem = buildDecisionItem(term, state)
          const signature = completion.complete ? createDecisionSignature(decisionItem) : null
          const isConfirmed = Boolean(signature && state.stagedSignature === signature)
          return {
            term,
            state,
            metrics: aggregateNeedsMetrics(term),
            completion,
            decisionItem,
            signature,
            isConfirmed,
            needsReconfirm: Boolean(state.stagedSignature && signature && state.stagedSignature !== signature),
          }
        })
        .filter(
          (
            row
          ): row is {
            term: NeedsDecisionTerm
            state: NeedsDecisionState
            metrics: NeedsTermMetrics
            completion: ReturnType<typeof getDecisionCompletion>
            decisionItem: ReturnType<typeof buildDecisionItem>
            signature: string | null
            isConfirmed: boolean
            needsReconfirm: boolean
          } => Boolean(row)
        ) ?? []

    const filtered = rows
      .filter((row) => {
        if (!normalizedSearch) return true
        return (
          row.term.search_term.toLowerCase().includes(normalizedSearch) ||
          row.term.custom_label_0s.some((assignment) =>
            assignment.custom_label_0.toLowerCase().includes(normalizedSearch)
          )
        )
      })
      .filter((row) => !showSelectedNeedsOnly || row.state.selected)

    return filtered.sort((a, b) => {
      if (needsSort === 'impact_desc') {
        return (b.term.value_score?.impact_score ?? 0) - (a.term.value_score?.impact_score ?? 0)
      }
      if (needsSort === 'search_asc') {
        return a.term.search_term.localeCompare(b.term.search_term)
      }
      if (needsSort === 'labels_desc') {
        return b.term.custom_label_0s.length - a.term.custom_label_0s.length
      }
      if (needsSort === 'cost_desc') {
        return b.metrics.costMicros - a.metrics.costMicros
      }
      if (needsSort === 'conversions_desc') {
        return b.metrics.conversions - a.metrics.conversions
      }
      return b.metrics.impressions - a.metrics.impressions
    })
  }, [deferredNeedsSearch, needsData?.terms, needsSort, needsState, showSelectedNeedsOnly])

  const selectedVisibleNeedsCount = useMemo(
    () => needsRows.filter((row) => row.state.selected).length,
    [needsRows]
  )

  const confirmedNeedsTerms = useMemo(
    () => needsRows.filter((row) => row.isConfirmed).map((row) => row.term.search_term),
    [needsRows]
  )

  const selectedConfirmableNeedsCount = useMemo(
    () =>
      needsRows.filter((row) => row.state.selected && row.completion.complete && !row.isConfirmed).length,
    [needsRows]
  )

  const needsRowsByTerm = useMemo(
    () => Object.fromEntries(needsRows.map((row) => [row.term.search_term, row])),
    [needsRows]
  )

  const existingRows = useMemo(() => {
    const normalizedSearch = deferredExistingSearch.trim().toLowerCase()
    const rows =
      existingData?.terms.map((term) => {
        const pendingCount = term.funnels.reduce(
          (count, funnel) =>
            existingUpdates[updateKey(term.search_term, funnel.custom_label_0)] ? count + 1 : count,
          0
        )
        return {
          term,
          pendingCount,
          hasError: term.funnels.some((funnel) => funnel.error),
        }
      }) ?? []

    const filtered = rows
      .filter((row) => {
        if (!normalizedSearch) return true
        return (
          row.term.search_term.toLowerCase().includes(normalizedSearch) ||
          row.term.funnels.some((funnel) => funnel.custom_label_0.toLowerCase().includes(normalizedSearch))
        )
      })
      .filter((row) => !showPendingExistingOnly || row.pendingCount > 0)

    return filtered.sort((a, b) => {
      if (existingSort === 'search_asc') {
        return a.term.search_term.localeCompare(b.term.search_term)
      }
      if (existingSort === 'impressions_desc') {
        return b.term.total_impressions - a.term.total_impressions
      }
      if (existingSort === 'cost_desc') {
        return b.term.total_cost_micros - a.term.total_cost_micros
      }
      if (existingSort === 'conversions_desc') {
        return b.term.total_conversions - a.term.total_conversions
      }
      if (a.hasError !== b.hasError) {
        return a.hasError ? -1 : 1
      }
      return b.term.total_impressions - a.term.total_impressions
    })
  }, [deferredExistingSearch, existingData?.terms, existingSort, existingUpdates, showPendingExistingOnly])

  const existingTierByKey = useMemo(() => {
    const tierByKey: Record<string, AssignmentTier | null> = {}
    for (const term of existingData?.terms ?? []) {
      for (const funnel of term.funnels) {
        tierByKey[updateKey(term.search_term, funnel.custom_label_0)] = fromExistingTierLabel(funnel.tier)
      }
    }
    return tierByKey
  }, [existingData?.terms])

  const needsTotal = needsData?.total_count ?? 0
  const needsReturned = needsData?.returned_count ?? 0
  const needsLimit = needsData?.limit ?? NEEDS_DECISION_LIMIT
  const needsRangeStart = needsTotal === 0 ? 0 : (needsData?.offset ?? 0) + 1
  const needsRangeEnd = needsData ? (needsData.offset ?? 0) + needsReturned : 0

  const existingTotal = existingData?.total_count ?? 0
  const existingReturned = existingData?.returned_count ?? 0
  const existingLimit = existingData?.limit ?? EXISTING_FUNNEL_LIMIT
  const existingRangeStart = existingTotal === 0 ? 0 : (existingData?.offset ?? 0) + 1
  const existingRangeEnd = existingData ? (existingData.offset ?? 0) + existingReturned : 0

  function toggleNeedsSelection(searchTerm: string, selected: boolean) {
    startTransition(() => {
      setNeedsState((current) => ({
        ...current,
        [searchTerm]: {
          ...current[searchTerm],
          selected,
        },
      }))
    })
  }

  function updateNeedsAction(searchTerm: string, actionType: DecisionActionType) {
    startTransition(() => {
      setNeedsState((current) => ({
        ...current,
        [searchTerm]: {
          ...current[searchTerm],
          actionType,
        },
      }))
    })
  }

  function updateNeedsAssignment(searchTerm: string, customLabel0: string, tier: AssignmentTier) {
    startTransition(() => {
      setNeedsState((current) => ({
        ...current,
        [searchTerm]: {
          ...current[searchTerm],
          assignments: {
            ...current[searchTerm].assignments,
            [customLabel0]: tier,
          },
        },
      }))
    })
  }

  function selectAllNeeds(selected: boolean) {
    startTransition(() => {
      setNeedsState((current) =>
        Object.fromEntries(
          Object.entries(current).map(([searchTerm, state]) => [
            searchTerm,
            {
              ...state,
              selected,
            },
          ])
        )
      )
    })
  }

  function selectVisibleNeeds(selected: boolean) {
    const visibleTerms = new Set(needsRows.map((row) => row.term.search_term))
    startTransition(() => {
      setNeedsState((current) =>
        Object.fromEntries(
          Object.entries(current).map(([searchTerm, state]) => [
            searchTerm,
            visibleTerms.has(searchTerm)
              ? {
                  ...state,
                  selected,
                }
              : state,
          ])
        )
      )
    })
  }

  function applyBulkActionToSelectedNeeds() {
    const selectedTerms = new Set(selectedNeedsTerms)
    if (selectedTerms.size === 0) {
      setErrorMessage('Select at least one term before applying a bulk action.')
      return
    }

    startTransition(() => {
      setNeedsState((current) =>
        Object.fromEntries(
          Object.entries(current).map(([searchTerm, state]) => [
            searchTerm,
            selectedTerms.has(searchTerm)
              ? {
                  ...state,
                  actionType: bulkActionType,
                }
              : state,
          ])
        )
      )
    })
    setMessage(`Applied "${bulkActionType}" to ${selectedTerms.size.toLocaleString()} selected term(s).`)
  }

  function applyBulkTierToSelectedNeeds() {
    const selectedTerms = new Set(selectedNeedsTerms)
    if (selectedTerms.size === 0) {
      setErrorMessage('Select at least one term before applying a bulk tier.')
      return
    }

    startTransition(() => {
      setNeedsState((current) =>
        Object.fromEntries(
          Object.entries(current).map(([searchTerm, state]) => {
            if (!selectedTerms.has(searchTerm) || state.actionType !== 'funnel') {
              return [searchTerm, state]
            }
            const row = needsRowsByTerm[searchTerm]
            return [
              searchTerm,
              {
                ...state,
                assignments: Object.fromEntries(
                  (row?.term.custom_label_0s ?? []).map((assignment) => [
                    assignment.custom_label_0,
                    bulkAssignmentTier,
                  ])
                ),
              },
            ]
          })
        )
      )
    })
    setMessage(
      `Applied "${bulkAssignmentTier}" to funnel assignments for ${selectedTerms.size.toLocaleString()} selected term(s).`
    )
  }

  function toggleNeedsExpanded(searchTerm: string) {
    startTransition(() => {
      setExpandedNeedsTerms((current) => ({
        ...current,
        [searchTerm]: !current[searchTerm],
      }))
    })
  }

  function toggleExistingExpanded(searchTerm: string) {
    startTransition(() => {
      setExpandedExistingTerms((current) => ({
        ...current,
        [searchTerm]: !current[searchTerm],
      }))
    })
  }

  function confirmPublishStaged(stagedCount: number): boolean {
    const summary = [
      `Publish ${stagedCount.toLocaleString()} staged search terms to Google Ads?`,
      '',
      'Only confirmed staged decisions will be posted.',
      'This will make live Google Ads changes immediately.',
    ].join('\n')
    return window.confirm(summary)
  }

  function confirmExistingFunnelPost(updates: ExistingUpdateState[]): boolean {
    const tierChangeCount = updates.filter((item) => Boolean(item.new_tier)).length
    const sharedListMoveCount = updates.filter((item) => Boolean(item.new_action)).length
    const byAction = updates.reduce<Record<string, number>>((acc, item) => {
      const key = item.new_action ?? item.new_tier ?? 'unknown'
      acc[key] = (acc[key] ?? 0) + 1
      return acc
    }, {})

    const byActionSummary = Object.entries(byAction)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([key, count]) => `- ${key}: ${count}`)
      .join('\n')

    const summary = [
      `Post ${updates.length} existing-funnel changes to Google Ads?`,
      '',
      `Tier changes: ${tierChangeCount}`,
      `Moves to shared lists: ${sharedListMoveCount}`,
      byActionSummary,
      '',
      'This will update live campaign/ad-group/shared-list negatives immediately.',
    ].join('\n')

    return window.confirm(summary)
  }

  async function stageNeedsDecisions(searchTerms: string[]) {
    const rowsToStage = searchTerms
      .map((searchTerm) => needsRowsByTerm[searchTerm])
      .filter((row): row is (typeof needsRows)[number] => Boolean(row))

    const incompleteRows = rowsToStage.filter((row) => !row.completion.complete)
    if (incompleteRows.length > 0) {
      setErrorMessage(
        `${incompleteRows.length.toLocaleString()} selected term(s) are incomplete. Assign all custom_label_0 tiers before confirming.`
      )
      return
    }

    if (rowsToStage.length === 0) {
      setErrorMessage('No confirmable terms found.')
      return
    }

    setStaging(true)
    setErrorMessage(null)
    try {
      const decisions = rowsToStage.map((row) => row.decisionItem)
      const response = await fetch('/api/search-terms/save-decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decisions }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const payload = (await response.json()) as { saved_count: number; staged_term_count: number }
      const now = new Date().toISOString()
      const snapshots: StagedDecisionSnapshot[] = rowsToStage.map((row) => ({
        search_term: row.term.search_term,
        action_type: row.decisionItem.action_type,
        assignments: row.decisionItem.assignments,
        staged_at: now,
      }))
      const snapshotByTerm = Object.fromEntries(
        snapshots.map((snapshot) => [snapshot.search_term, snapshot])
      ) as StagedDecisionMap

      setNeedsState((current) =>
        Object.fromEntries(
          Object.entries(current).map(([searchTerm, state]) => {
            const row = needsRowsByTerm[searchTerm]
            if (!row || !snapshotByTerm[searchTerm]) {
              return [searchTerm, state]
            }
            return [
              searchTerm,
              applyStagedDecisionToState(row.term, { ...state, selected: false }, snapshotByTerm[searchTerm]),
            ]
          })
        )
      )
      await fetchStagedDecisions(needsData?.terms.map((term) => term.search_term))
      setMessage(
        `Confirmed ${payload.staged_term_count.toLocaleString()} term(s) to staging (${payload.saved_count.toLocaleString()} row(s)).`
      )
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to stage confirmed decisions')
    } finally {
      setStaging(false)
    }
  }

  async function handleConfirmNeedsTerm(searchTerm: string) {
    await stageNeedsDecisions([searchTerm])
  }

  async function handleConfirmSelectedNeeds() {
    const selectedTerms = selectedNeedsTerms
    if (selectedTerms.length === 0) {
      setErrorMessage('Select at least one term before confirming.')
      return
    }
    await stageNeedsDecisions(selectedTerms)
  }

  async function handlePublishStagedNeedsDecisions() {
    if (stagedQueueCount === 0) {
      setErrorMessage('There are no staged decisions to publish.')
      return
    }
    if (!confirmPublishStaged(stagedQueueCount)) {
      return
    }

    setPublishingStaged(true)
    setErrorMessage(null)
    try {
      const response = await fetch('/api/search-terms/post-staged', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const payload = (await response.json()) as {
        success_count: number
        error_count: number
      }
      setMessage(
        `Published staged decisions: ${payload.success_count.toLocaleString()} succeeded, ${payload.error_count.toLocaleString()} failed.`
      )
      await fetchNeedsDecision()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to publish staged decisions')
    } finally {
      setPublishingStaged(false)
    }
  }

  function upsertExistingUpdate(
    searchTerm: string,
    customLabel0: string,
    value: AssignmentTier | 'global_block' | 'competitor' | 'branded'
  ) {
    const key = updateKey(searchTerm, customLabel0)
    const currentTier = existingTierByKey[key]

    startTransition(() => {
      setExistingUpdates((current) => {
        const next = { ...current }
        if (value === 'global_block' || value === 'competitor' || value === 'branded') {
          next[key] = {
            search_term: searchTerm,
            custom_label_0: customLabel0,
            new_action: value,
          }
        } else {
          next[key] = {
            search_term: searchTerm,
            custom_label_0: customLabel0,
            new_tier: value,
          }

          // If the user chooses the existing tier, remove pending change for this row.
          if (currentTier && value === currentTier) {
            delete next[key]
          }
        }
        return next
      })
    })
  }

  async function handlePostExistingUpdates() {
    const updates = Object.values(existingUpdates)
    if (updates.length === 0) {
      setErrorMessage('No existing funnel changes to post.')
      return
    }
    if (!confirmExistingFunnelPost(updates)) {
      return
    }

    setPosting(true)
    setErrorMessage(null)
    try {
      const response = await fetch('/api/search-terms/update-existing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const payload = (await response.json()) as {
        success_count: number
        error_count: number
        results: ExistingFunnelUpdateResult[]
      }
      setMessage(
        `Posted existing funnel changes: ${payload.success_count} succeeded, ${payload.error_count} failed.`
      )
      await fetchExisting()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to post existing changes')
    } finally {
      setPosting(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Shopping Funnel</h1>
        <p className="text-muted-foreground">
          Manage Shopping search terms across HIGH, MEDIUM, and LOW campaign intent tiers.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label>Date Range</Label>
              <Select
                value={range}
                onValueChange={(value) => {
                  startTransition(() => {
                    setRange(value as DateRangePreset)
                    setNeedsOffset(0)
                    setExistingOffset(0)
                  })
                }}
              >
                <SelectTrigger className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DATE_RANGE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Custom Label 0</Label>
              <Select
                value={customLabelFilter}
                onValueChange={(value) => {
                  startTransition(() => {
                    setCustomLabelFilter(value)
                    setNeedsOffset(0)
                    setExistingOffset(0)
                  })
                }}
              >
                <SelectTrigger className="w-72">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {availableCustomLabels.map((label) => (
                    <SelectItem key={label} value={label}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Min Impressions</Label>
              <Input
                value={minImpressions}
                onChange={(event) => {
                  const nextValue = event.target.value
                  startTransition(() => {
                    setMinImpressions(nextValue)
                    setNeedsOffset(0)
                    setExistingOffset(0)
                  })
                }}
                className="w-36"
              />
            </div>

            <Button
              variant="outline"
              onClick={() => {
                if (activeTab === 'needs-decision') {
                  void fetchNeedsDecision()
                } else {
                  void fetchExisting()
                }
                void fetchDataLineage()
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>

            {activeDataSource && (
              <Badge variant="outline" className="ml-auto">
                Source: {activeDataSource === 'google_ads_api_live' ? 'Live Google Ads API' : activeDataSource}
              </Badge>
            )}
            {activeGeneratedAt && (
              <span className="text-xs text-muted-foreground">
                Last pulled: {new Date(activeGeneratedAt).toLocaleString()}
              </span>
            )}
            {isTransitionPending && (
              <span className="text-xs text-muted-foreground">Updating filters...</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data Lineage Debug Panel</CardTitle>
          <CardDescription>
            Live integrity checks for Shopping funnel naming and custom_label_0 tier coverage.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {lineageLoading && (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          )}

          {!lineageLoading && !lineageData && (
            <p className="text-sm text-muted-foreground">
              Data lineage is temporarily unavailable.
            </p>
          )}

          {!lineageLoading && lineageData && (
            <div className="space-y-4">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <Badge variant="secondary">
                  Enabled campaigns: {lineageData.integrity.enabled_shopping_campaigns}
                </Badge>
                <Badge variant="secondary">
                  Parsed funnel campaigns: {lineageData.integrity.parsed_funnel_campaigns}
                </Badge>
                <Badge
                  variant={lineageData.integrity.non_pattern_campaign_count > 0 ? 'destructive' : 'secondary'}
                >
                  Non-pattern campaigns: {lineageData.integrity.non_pattern_campaign_count}
                </Badge>
                <Badge
                  variant={
                    lineageData.integrity.ad_group_name_mismatch_count > 0 ? 'destructive' : 'secondary'
                  }
                >
                  Ad group naming mismatches: {lineageData.integrity.ad_group_name_mismatch_count}
                </Badge>
                <Badge variant="secondary">
                  custom_label_0 groups: {lineageData.integrity.custom_label_0_count}
                </Badge>
                <Badge
                  variant={
                    lineageData.integrity.labels_with_missing_tiers.length > 0 ? 'destructive' : 'secondary'
                  }
                >
                  Labels missing tiers: {lineageData.integrity.labels_with_missing_tiers.length}
                </Badge>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void applyExistingFunnelFilters({ errorsOnly: true })}
                >
                  Open Existing Errors
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    void applyExistingFunnelFilters({ customLabel: 'all', errorsOnly: false })
                  }
                >
                  Reset Existing Filters
                </Button>
                {lineageData.integrity.labels_with_missing_tiers.slice(0, 3).map((issue) => (
                  <Button
                    key={issue.custom_label_0}
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      void applyExistingFunnelFilters({
                        customLabel: issue.custom_label_0,
                        errorsOnly: true,
                      })
                    }
                  >
                    Inspect {issue.custom_label_0}
                  </Button>
                ))}
              </div>

              <p className="text-xs text-muted-foreground">
                Source: Live Google Ads API | Window: {lineageData.date_window.startDate} to{' '}
                {lineageData.date_window.endDate} | Last pulled:{' '}
                {new Date(lineageData.generated_at).toLocaleString()}
              </p>

              {lineageData.integrity.labels_with_missing_tiers.length > 0 && (
                <div className="rounded-md border p-3">
                  <p className="mb-2 text-sm font-medium">
                    Missing tier coverage by custom_label_0
                  </p>
                  <div className="space-y-1 text-sm">
                    {lineageData.integrity.labels_with_missing_tiers.slice(0, 20).map((issue) => (
                      <p key={issue.custom_label_0}>
                        <span className="font-medium">{issue.custom_label_0}</span> missing:{' '}
                        {issue.missing_tiers.join(', ')}
                      </p>
                    ))}
                    {lineageData.integrity.labels_with_missing_tiers.length > 20 && (
                      <p className="text-muted-foreground">
                        Showing first 20 of {lineageData.integrity.labels_with_missing_tiers.length}{' '}
                        labels.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {lineageData.integrity.non_pattern_campaign_count > 0 && (
                <div className="rounded-md border p-3">
                  <p className="mb-2 text-sm font-medium">
                    Enabled Shopping campaigns not matching expected pattern
                  </p>
                  <div className="space-y-1 text-sm">
                    {lineageData.integrity.non_pattern_campaigns.slice(0, 20).map((campaignName) => (
                      <p key={campaignName}>{campaignName}</p>
                    ))}
                    {lineageData.integrity.non_pattern_campaigns.length > 20 && (
                      <p className="text-muted-foreground">
                        Showing first 20 of {lineageData.integrity.non_pattern_campaigns.length}{' '}
                        campaigns.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {message && (
        <Card className="border-emerald-300 bg-emerald-50">
          <CardContent className="py-3 text-emerald-700 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {message}
          </CardContent>
        </Card>
      )}

      {errorMessage && (
        <Card className="border-red-300 bg-red-50">
          <CardContent className="py-3 text-red-700 flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      )}

      <Tabs
        value={activeTab}
        onValueChange={(value) =>
          startTransition(() => setActiveTab(value as typeof activeTab))
        }
      >
        <TabsList>
          <TabsTrigger value="needs-decision">Needs Decision</TabsTrigger>
          <TabsTrigger value="existing-funnel">Existing Funnel</TabsTrigger>
        </TabsList>

        <TabsContent value="needs-decision" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Needs Decision</CardTitle>
              <CardDescription>
                {(needsData?.total_count ?? 0).toLocaleString()} search terms need funnel decisions.
                {needsData && needsData.total_count > needsData.terms.length
                  ? ` Showing first ${needsData.terms.length.toLocaleString()} terms.`
                  : ''}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 xl:grid-cols-[minmax(260px,1fr)_260px_auto]">
                <div className="space-y-1">
                  <Label>Search terms / custom labels</Label>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      value={needsSearch}
                      onChange={(event) => {
                        const nextValue = event.target.value
                        startTransition(() => setNeedsSearch(nextValue))
                      }}
                      placeholder="Filter visible rows..."
                      className="pl-8"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Sort by</Label>
                  <Select
                    value={needsSort}
                    onValueChange={(value) =>
                      startTransition(() => setNeedsSort(value as NeedsSortOption))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {NEEDS_SORT_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <Checkbox
                      checked={showSelectedNeedsOnly}
                      onCheckedChange={(checked) =>
                        startTransition(() => setShowSelectedNeedsOnly(Boolean(checked)))
                      }
                    />
                    Show selected only
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/25 p-3">
                <Button variant="outline" size="sm" onClick={() => selectVisibleNeeds(true)}>
                  Select Visible
                </Button>
                <Button variant="outline" size="sm" onClick={() => selectVisibleNeeds(false)}>
                  Clear Visible
                </Button>
                <Button variant="outline" size="sm" onClick={() => selectAllNeeds(true)}>
                  Select All Loaded
                </Button>
                <Button variant="outline" size="sm" onClick={() => selectAllNeeds(false)}>
                  Clear All Loaded
                </Button>
                <Badge variant="secondary">{selectedNeedsTerms.length.toLocaleString()} selected</Badge>
                <Badge variant="outline">{selectedVisibleNeedsCount.toLocaleString()} selected in view</Badge>
                <Badge variant="outline">
                  {selectedConfirmableNeedsCount.toLocaleString()} ready to confirm
                </Badge>
                <Badge variant="outline">{confirmedNeedsTerms.length.toLocaleString()} confirmed</Badge>
                <Badge variant="secondary">{stagedQueueCount.toLocaleString()} staged</Badge>
                <Badge variant="outline">{needsRows.length.toLocaleString()} rows in view</Badge>
              </div>

              <div className="flex flex-wrap items-end gap-2 rounded-md border p-3">
                <div className="space-y-1">
                  <Label>Bulk action for selected</Label>
                  <Select
                    value={bulkActionType}
                    onValueChange={(value) => setBulkActionType(value as DecisionActionType)}
                  >
                    <SelectTrigger className="w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACTION_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={selectedNeedsTerms.length === 0}
                  onClick={applyBulkActionToSelectedNeeds}
                >
                  Apply Action
                </Button>

                <div className="space-y-1">
                  <Label>Bulk funnel tier for selected</Label>
                  <Select
                    value={bulkAssignmentTier}
                    onValueChange={(value) => setBulkAssignmentTier(value as AssignmentTier)}
                  >
                    <SelectTrigger className="w-52">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={selectedNeedsTerms.length === 0}
                  onClick={applyBulkTierToSelectedNeeds}
                >
                  Apply Tier
                </Button>

                <div className="ml-auto flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => void handleConfirmSelectedNeeds()}
                    disabled={staging || publishingStaged || selectedConfirmableNeedsCount === 0}
                  >
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    {staging ? 'Confirming...' : 'Confirm Selected'}
                  </Button>
                  <Button
                    onClick={() => void handlePublishStagedNeedsDecisions()}
                    disabled={staging || publishingStaged || stagedQueueCount === 0}
                  >
                    <Send className="mr-2 h-4 w-4" />
                    {publishingStaged ? 'Publishing...' : 'Publish Staged'}
                  </Button>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2">
                <span className="text-xs text-muted-foreground">
                  Showing {needsRangeStart.toLocaleString()}-{needsRangeEnd.toLocaleString()} of{' '}
                  {needsTotal.toLocaleString()}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={needsOffset === 0 || staging || publishingStaged || needsLoading}
                  onClick={() =>
                    startTransition(() =>
                      setNeedsOffset((current) => Math.max(0, current - needsLimit))
                    )
                  }
                >
                  <ChevronLeft className="h-4 w-4" />
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!needsData?.has_next || staging || publishingStaged || needsLoading}
                  onClick={() =>
                    startTransition(() => setNeedsOffset((current) => current + needsLimit))
                  }
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>

          {needsLoading && (
            <Card>
              <CardContent className="pt-6 space-y-3">
                {[...Array(5)].map((_, index) => (
                  <Skeleton key={index} className="h-14 w-full" />
                ))}
              </CardContent>
            </Card>
          )}

          {!needsLoading && needsData && needsRows.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No needs-decision terms match your current filters.
              </CardContent>
            </Card>
          )}

          {!needsLoading && needsRows.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <div className="max-h-[68vh] space-y-2 overflow-y-auto pr-1">
                  {needsRows.map(({ term, state, metrics, completion, isConfirmed, needsReconfirm }) => {
                    const isExpanded = expandedNeedsTerms[term.search_term] ?? false
                    let confirmButtonLabel = 'Confirm Choices'
                    if (needsReconfirm) {
                      confirmButtonLabel = 'Reconfirm Choices'
                    } else if (isConfirmed) {
                      confirmButtonLabel = 'Confirmed'
                    }
                    return (
                      <div
                        key={term.search_term}
                        className={`rounded-md border p-3 ${
                          state.selected ? 'border-primary/40 bg-primary/5' : ''
                        } ${isConfirmed ? 'border-emerald-300 bg-emerald-50/50' : ''} ${
                          needsReconfirm ? 'border-amber-300 bg-amber-50/60' : ''
                        }`}
                      >
                        <div className="flex flex-wrap items-start gap-3">
                          <Checkbox
                            checked={state.selected}
                            onCheckedChange={(checked) =>
                              toggleNeedsSelection(term.search_term, Boolean(checked))
                            }
                          />

                          <div className="min-w-0 flex-1">
                            <p className="font-medium leading-tight">{term.search_term}</p>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>{term.custom_label_0s.length} label(s)</span>
                              <span>{metrics.impressions.toLocaleString()} impressions</span>
                              <span>{metrics.clicks.toLocaleString()} clicks</span>
                              <span>${(metrics.costMicros / 1_000_000).toFixed(2)} cost</span>
                              <span>{metrics.conversions.toFixed(2)} conv</span>
                              {typeof term.value_score?.impact_score === 'number' && (
                                <span>Impact {term.value_score.impact_score.toFixed(2)}</span>
                              )}
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            {term.recommendation && (
                              <Badge variant="outline">
                                Rec: {ACTION_LABEL_BY_VALUE[term.recommendation.action_type]}
                                {term.recommendation.default_tier
                                  ? ` (${term.recommendation.default_tier.toUpperCase()})`
                                  : ''}
                              </Badge>
                            )}
                            {typeof term.recommendation?.confidence === 'number' && (
                              <Badge variant="outline">
                                {Math.round(term.recommendation.confidence * 100)}% confidence
                              </Badge>
                            )}
                            {state.actionType === 'funnel' && (
                              <Badge variant={completion.complete ? 'secondary' : 'destructive'}>
                                {completion.selectedCount}/{completion.requiredCount} labels selected
                              </Badge>
                            )}
                            {isConfirmed && !needsReconfirm && <Badge variant="secondary">Confirmed</Badge>}
                            {needsReconfirm && <Badge variant="destructive">Needs Reconfirm</Badge>}
                            {!completion.complete && state.actionType === 'funnel' && (
                              <Badge variant="destructive">Incomplete</Badge>
                            )}
                            {isExpanded ? (
                              <Select
                                value={state.actionType}
                                onValueChange={(value) =>
                                  updateNeedsAction(term.search_term, value as DecisionActionType)
                                }
                              >
                                <SelectTrigger className="w-52">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {ACTION_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                      {option.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : (
                              <Badge variant="outline">{ACTION_LABEL_BY_VALUE[state.actionType]}</Badge>
                            )}

                            <Button
                              type="button"
                              size="sm"
                              variant={isConfirmed && !needsReconfirm ? 'outline' : 'default'}
                              disabled={
                                staging ||
                                publishingStaged ||
                                !completion.complete ||
                                (isConfirmed && !needsReconfirm)
                              }
                              onClick={() => void handleConfirmNeedsTerm(term.search_term)}
                            >
                              <CheckCircle2 className="mr-1 h-4 w-4" />
                              {confirmButtonLabel}
                            </Button>

                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleNeedsExpanded(term.search_term)}
                            >
                              {isExpanded ? (
                                <>
                                  <ChevronUp className="mr-1 h-4 w-4" />
                                  Hide
                                </>
                              ) : (
                                <>
                                  <ChevronDown className="mr-1 h-4 w-4" />
                                  Details
                                </>
                              )}
                            </Button>
                          </div>
                        </div>

                        {state.actionType === 'funnel' && isExpanded && (
                          <div className="mt-3 grid gap-2">
                            {term.recommendation?.reason_codes && term.recommendation.reason_codes.length > 0 && (
                              <div className="rounded-md border bg-muted/30 p-2 text-xs text-muted-foreground">
                                Recommendation rationale: {term.recommendation.reason_codes.join(', ')}
                              </div>
                            )}
                            {!completion.complete && (
                              <p className="text-xs text-amber-700">
                                Select a funnel tier for every custom_label_0 before confirming this term.
                              </p>
                            )}
                            {term.custom_label_0s.map((assignment) => (
                              <div
                                key={`${term.search_term}-${assignment.custom_label_0}`}
                                className="grid gap-2 rounded-md border p-2 md:grid-cols-[1fr_220px]"
                              >
                                <div>
                                  <p className="font-medium">{assignment.custom_label_0}</p>
                                  <p className="text-xs text-muted-foreground">
                                    Source: {assignment.source_campaign} ({assignment.source_tier}) |{' '}
                                    {assignment.impressions.toLocaleString()} imp | $
                                    {(assignment.cost_micros / 1_000_000).toFixed(2)} cost
                                  </p>
                                </div>
                                <Select
                                  value={state.assignments[assignment.custom_label_0]}
                                  onValueChange={(value) =>
                                    updateNeedsAssignment(
                                      term.search_term,
                                      assignment.custom_label_0,
                                      value as AssignmentTier
                                    )
                                  }
                                >
                                  <SelectTrigger>
                                    <SelectValue placeholder="Select tier..." />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {TIER_OPTIONS.map((option) => (
                                      <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="existing-funnel" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Existing Funnel</CardTitle>
              <CardDescription>
                {(existingData?.total_count ?? 0).toLocaleString()} decisioned terms with{' '}
                {(existingData?.error_count ?? 0).toLocaleString()} flagged errors.
                {existingData && existingData.total_count > existingData.terms.length
                  ? ` Showing first ${existingData.terms.length.toLocaleString()} terms.`
                  : ''}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 xl:grid-cols-[minmax(260px,1fr)_260px_auto_auto]">
                <div className="space-y-1">
                  <Label>Search terms / custom labels</Label>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      value={existingSearch}
                      onChange={(event) => {
                        const nextValue = event.target.value
                        startTransition(() => setExistingSearch(nextValue))
                      }}
                      placeholder="Filter visible rows..."
                      className="pl-8"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label>Sort by</Label>
                  <Select
                    value={existingSort}
                    onValueChange={(value) =>
                      startTransition(() => setExistingSort(value as ExistingSortOption))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {EXISTING_SORT_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-end">
                  <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <Checkbox
                      checked={showPendingExistingOnly}
                      onCheckedChange={(checked) =>
                        startTransition(() => setShowPendingExistingOnly(Boolean(checked)))
                      }
                    />
                    Show pending only
                  </label>
                </div>

                <div className="flex items-end">
                  <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <Checkbox
                      checked={showErrorsOnly}
                      onCheckedChange={(checked) =>
                        startTransition(() => setShowErrorsOnly(Boolean(checked)))
                      }
                    />
                    Show errors only
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/25 p-3">
                <Button variant="outline" onClick={() => void fetchExisting()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Apply Filters
                </Button>
                <Button
                  onClick={() => void handlePostExistingUpdates()}
                  disabled={posting || Object.keys(existingUpdates).length === 0}
                >
                  <Send className="mr-2 h-4 w-4" />
                  {posting ? 'Posting...' : 'Post Changes to Google Ads'}
                </Button>
                <Badge variant="secondary">
                  {Object.keys(existingUpdates).length.toLocaleString()} pending changes
                </Badge>
                <Badge variant="outline">{existingRows.length.toLocaleString()} rows in view</Badge>

                <div className="ml-auto flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Showing {existingRangeStart.toLocaleString()}-{existingRangeEnd.toLocaleString()} of{' '}
                    {existingTotal.toLocaleString()}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={existingOffset === 0 || posting || existingLoading}
                    onClick={() =>
                      startTransition(() =>
                        setExistingOffset((current) => Math.max(0, current - existingLimit))
                      )
                    }
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!existingData?.has_next || posting || existingLoading}
                    onClick={() =>
                      startTransition(() => setExistingOffset((current) => current + existingLimit))
                    }
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {existingLoading && (
            <Card>
              <CardContent className="pt-6 space-y-3">
                {[...Array(5)].map((_, index) => (
                  <Skeleton key={index} className="h-24 w-full" />
                ))}
              </CardContent>
            </Card>
          )}

          {!existingLoading && existingData && existingRows.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No existing funnel terms match your current filters.
              </CardContent>
            </Card>
          )}

          {!existingLoading && existingRows.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <div className="max-h-[68vh] space-y-2 overflow-y-auto pr-1">
                  {existingRows.map(({ term, hasError, pendingCount }) => {
                    const isExpanded =
                      expandedExistingTerms[term.search_term] ?? (pendingCount > 0 || hasError)
                    return (
                      <div
                        key={term.search_term}
                        className={`rounded-md border p-3 ${hasError ? 'border-red-300 bg-red-50/50' : ''}`}
                      >
                        <div className="flex flex-wrap items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="font-medium leading-tight">{term.search_term}</p>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <span>{term.total_impressions.toLocaleString()} impressions</span>
                              <span>{term.total_clicks.toLocaleString()} clicks</span>
                              <span>${(term.total_cost_micros / 1_000_000).toFixed(2)} cost</span>
                              <span>{term.total_conversions.toFixed(2)} conv</span>
                              <span>{term.funnels.length} label assignment(s)</span>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            {hasError && <Badge variant="destructive">Error</Badge>}
                            {pendingCount > 0 && (
                              <Badge variant="secondary">{pendingCount} pending update(s)</Badge>
                            )}
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleExistingExpanded(term.search_term)}
                            >
                              {isExpanded ? (
                                <>
                                  <ChevronUp className="mr-1 h-4 w-4" />
                                  Hide
                                </>
                              ) : (
                                <>
                                  <ChevronDown className="mr-1 h-4 w-4" />
                                  Details
                                </>
                              )}
                            </Button>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-3 grid gap-2">
                            {term.funnels.map((funnel) => {
                              const key = updateKey(term.search_term, funnel.custom_label_0)
                              const existingUpdate = existingUpdates[key]
                              const selectedValue =
                                existingUpdate?.new_action ??
                                existingUpdate?.new_tier ??
                                fromExistingTierLabel(funnel.tier) ??
                                'campaign_negative'

                              return (
                                <div
                                  key={key}
                                  className={`grid gap-2 rounded-md border p-2 md:grid-cols-[1fr_240px] ${
                                    funnel.error ? 'border-red-300 bg-red-50' : ''
                                  }`}
                                >
                                  <div>
                                    <p className="font-medium">{funnel.custom_label_0}</p>
                                    <p className="text-xs text-muted-foreground">
                                      Current tier: {funnel.tier}
                                    </p>
                                    {funnel.error && (
                                      <p className="text-xs text-red-700">{funnel.error_message}</p>
                                    )}
                                  </div>

                                  <Select
                                    value={selectedValue}
                                    onValueChange={(value) =>
                                      upsertExistingUpdate(
                                        term.search_term,
                                        funnel.custom_label_0,
                                        value as AssignmentTier | 'global_block' | 'competitor' | 'branded'
                                      )
                                    }
                                  >
                                    <SelectTrigger>
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                      {EXISTING_ASSIGNMENT_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value}>
                                          {option.label}
                                        </SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
