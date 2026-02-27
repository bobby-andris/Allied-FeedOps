'use client'

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, PlayCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

type QueueState = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'
type RunStatus = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'

interface QueueItem {
  id: string
  action_key: string
  title: string
  action_type: string
  current_state: QueueState
  master_sku: string | null
  platform: string | null
  rationale: string | null
  expected_revenue_impact: number | null
  confidence_score: number | null
  effort_score: number | null
  policy_risk_score: number | null
  priority_score: number | null
  latest_score?: {
    composite_score: number
    score_version: string
  } | null
}

interface ExperimentCandidate {
  id: number
  run_id: string
  status: RunStatus
  observed_lift: number | null
  sample_size: number | null
}

interface ExperimentRun {
  id: string
  run_key: string
  experiment_key: string
  status: RunStatus
  gate_status: string | null
  created_at: string
  completed_at: string | null
  action_id: string | null
  candidates: ExperimentCandidate[]
}

interface QueueResponse {
  queue: QueueItem[]
  warnings: string[]
}

interface RunResponse {
  runs: ExperimentRun[]
  warnings: string[]
}

export default function OptimizationControlCenterPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [runs, setRuns] = useState<ExperimentRun[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [newActionTitle, setNewActionTitle] = useState('')
  const [newActionType, setNewActionType] = useState('content_refresh')
  const [newActionSku, setNewActionSku] = useState('')
  const [newActionPlatform, setNewActionPlatform] = useState('google')
  const [newActionRationale, setNewActionRationale] = useState('')

  const [newRunExperimentKey, setNewRunExperimentKey] = useState('')
  const [newRunActionId, setNewRunActionId] = useState('')

  const loadData = useCallback(async () => {
    const [queueResponse, runsResponse] = await Promise.all([
      fetch('/api/optimization/action-queue?limit=100'),
      fetch('/api/optimization/experiments/runs?limit=100'),
    ])

    if (!queueResponse.ok) {
      throw new Error(await queueResponse.text())
    }
    if (!runsResponse.ok) {
      throw new Error(await runsResponse.text())
    }

    const queueBody = (await queueResponse.json()) as QueueResponse
    const runBody = (await runsResponse.json()) as RunResponse

    setQueue(queueBody.queue ?? [])
    setRuns(runBody.runs ?? [])
    setWarnings([...(queueBody.warnings ?? []), ...(runBody.warnings ?? [])])
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    void loadData()
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load optimization control data')
      })
      .finally(() => setLoading(false))
  }, [loadData])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setError(null)
    try {
      await loadData()
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to refresh optimization control data')
    } finally {
      setRefreshing(false)
    }
  }, [loadData])

  const queueCounts = useMemo(() => {
    return queue.reduce(
      (acc, item) => {
        acc[item.current_state] += 1
        return acc
      },
      {
        proposed: 0,
        approved: 0,
        executing: 0,
        validated: 0,
        rejected: 0,
      } as Record<QueueState, number>
    )
  }, [queue])

  const createAction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)

    try {
      const response = await fetch('/api/optimization/action-queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newActionTitle,
          action_type: newActionType,
          master_sku: newActionSku || null,
          platform: newActionPlatform || null,
          rationale: newActionRationale || null,
          score: {
            expected_revenue_impact: 0,
            confidence_score: 0,
            effort_score: 0,
            policy_risk_score: 0,
            score_version: 'r5.v1',
          },
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const body = (await response.json()) as { action?: QueueItem }
      setMessage(`Queued optimization action: ${body.action?.action_key ?? 'created'}`)
      setNewActionTitle('')
      setNewActionSku('')
      setNewActionRationale('')
      await loadData()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to create optimization action')
    } finally {
      setSaving(false)
    }
  }

  const transitionAction = async (actionId: string, nextState: QueueState) => {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const response = await fetch('/api/optimization/action-queue', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_id: actionId,
          next_state: nextState,
          actor: 'dashboard:optimization-control-center',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      setMessage(`Updated action state to ${nextState}`)
      await loadData()
    } catch (transitionError) {
      setError(transitionError instanceof Error ? transitionError.message : 'Failed to update action state')
    } finally {
      setSaving(false)
    }
  }

  const createRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)

    try {
      const response = await fetch('/api/optimization/experiments/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          experiment_key: newRunExperimentKey,
          action_id: newRunActionId || null,
          owner: 'dashboard:optimization-control-center',
          status: 'proposed',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const body = (await response.json()) as { run?: ExperimentRun }
      setMessage(`Created experiment run: ${body.run?.run_key ?? 'created'}`)
      setNewRunExperimentKey('')
      setNewRunActionId('')
      await loadData()
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : 'Failed to create experiment run')
    } finally {
      setSaving(false)
    }
  }

  const promoteRun = async (runKey: string, decision: 'promote' | 'reject') => {
    setSaving(true)
    setError(null)
    setMessage(null)

    try {
      const response = await fetch('/api/optimization/experiments/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_key: runKey,
          decision,
          min_sample_size: 100,
          min_observed_lift: 0.05,
          actor: 'dashboard:optimization-control-center',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const body = (await response.json()) as { promoted: boolean; gate_status: string }
      setMessage(`Run gate decision: ${body.gate_status} (${body.promoted ? 'promoted' : 'blocked'})`)
      await loadData()
    } catch (promoteError) {
      setError(promoteError instanceof Error ? promoteError.message : 'Failed to apply run gate decision')
    } finally {
      setSaving(false)
    }
  }

  const nextStatesByCurrent: Record<QueueState, QueueState[]> = {
    proposed: ['approved', 'rejected'],
    approved: ['executing', 'rejected'],
    executing: ['validated', 'rejected'],
    validated: [],
    rejected: [],
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Optimization Control Center</h1>
          <p className="text-muted-foreground">
            Prioritized action queue and experiment lifecycle control plane for R5 closed-loop operations.
          </p>
        </div>
        <Button onClick={() => void refresh()} disabled={refreshing || loading || saving}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {error}
          </CardContent>
        </Card>
      ) : null}

      {message ? (
        <Card>
          <CardContent className="py-4 text-sm">{message}</CardContent>
        </Card>
      ) : null}

      {warnings.length > 0 ? (
        <Card className="border-amber-300 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-sm text-amber-900">Warnings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-amber-800">
            {warnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>{warning}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-5">
        {(['proposed', 'approved', 'executing', 'validated', 'rejected'] as QueueState[]).map((state) => (
          <Card key={state}>
            <CardContent className="py-4 text-center">
              <div className="text-xs uppercase text-muted-foreground">{state}</div>
              <div className="text-2xl font-semibold">{queueCounts[state]}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Create Queue Action</CardTitle>
            <CardDescription>Add a prioritized optimization task to the R5 action queue.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={createAction}>
              <div className="space-y-2">
                <Label htmlFor="action-title">Title</Label>
                <Input
                  id="action-title"
                  value={newActionTitle}
                  onChange={(event) => setNewActionTitle(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="action-type">Action type</Label>
                <Input
                  id="action-type"
                  value={newActionType}
                  onChange={(event) => setNewActionType(event.target.value)}
                  required
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="action-sku">Master SKU</Label>
                  <Input
                    id="action-sku"
                    value={newActionSku}
                    onChange={(event) => setNewActionSku(event.target.value)}
                    placeholder="Optional"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="action-platform">Platform</Label>
                  <Input
                    id="action-platform"
                    value={newActionPlatform}
                    onChange={(event) => setNewActionPlatform(event.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="action-rationale">Rationale</Label>
                <Textarea
                  id="action-rationale"
                  value={newActionRationale}
                  onChange={(event) => setNewActionRationale(event.target.value)}
                  placeholder="Evidence-backed reason this action should be prioritized"
                />
              </div>
              <Button type="submit" disabled={saving || loading}>Queue action</Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create Experiment Run</CardTitle>
            <CardDescription>Attach queue actions to measurable experiment lifecycle runs.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={createRun}>
              <div className="space-y-2">
                <Label htmlFor="run-experiment-key">Experiment key</Label>
                <Input
                  id="run-experiment-key"
                  value={newRunExperimentKey}
                  onChange={(event) => setNewRunExperimentKey(event.target.value)}
                  placeholder="search-buildout-holdout-..."
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="run-action-id">Linked queue action ID</Label>
                <Input
                  id="run-action-id"
                  value={newRunActionId}
                  onChange={(event) => setNewRunActionId(event.target.value)}
                  placeholder="Optional"
                />
              </div>
              <Button type="submit" disabled={saving || loading}>Create run</Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Action Queue</CardTitle>
          <CardDescription>{queue.length.toLocaleString()} active queue rows</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Transition</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-[420px]">
                    <div className="font-medium">{item.title}</div>
                    <div className="text-xs text-muted-foreground">{item.action_key} · {item.action_type}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.current_state}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs">
                      SKU: {item.master_sku ?? '-'}
                      <br />
                      Platform: {item.platform ?? '-'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs">
                      priority: {item.priority_score ?? '-'}
                      <br />
                      composite: {item.latest_score?.composite_score?.toFixed?.(3) ?? '-'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      {nextStatesByCurrent[item.current_state].map((nextState) => (
                        <Button
                          key={`${item.id}-${nextState}`}
                          size="sm"
                          variant="outline"
                          disabled={saving || loading}
                          onClick={() => void transitionAction(item.id, nextState)}
                        >
                          {nextState}
                        </Button>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {queue.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">
                    No queue items found.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Runs</CardTitle>
          <CardDescription>{runs.length.toLocaleString()} lifecycle runs</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Candidates</TableHead>
                <TableHead>Gate</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="max-w-[360px]">
                    <div className="font-medium">{run.experiment_key}</div>
                    <div className="text-xs text-muted-foreground">{run.run_key}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{run.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs">
                      {run.candidates.length.toLocaleString()} candidates
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs">{run.gate_status ?? 'pending'}</div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={saving || loading}
                        onClick={() => void promoteRun(run.run_key, 'promote')}
                      >
                        <PlayCircle className="mr-1.5 h-3.5 w-3.5" />
                        Apply gate
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={saving || loading}
                        onClick={() => void promoteRun(run.run_key, 'reject')}
                      >
                        Reject
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {runs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">
                    No experiment runs found.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
