'use client'

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface ExperimentResultsResponse {
  experiments: Array<{
    experiment_key: string
    name: string
    initiative: string
    hypothesis: string
    status: string
    start_date: string
    end_date: string | null
    success_threshold: number | null
    failure_threshold: number | null
    created_at: string
  }>
  outcomes: Array<{
    experiment_key: string
    metric_name: string
    observed_lift: number
    sample_size: number
    status: string
    measured_at: string
  }>
  assignments: Array<{
    experiment_key: string
    entity_key: string
    cohort: 'control' | 'treatment'
    assigned_at: string
  }>
  governance: Array<{
    experiment_key: string
    initiative: string
    weekly_status: string
    checkpoint_due: boolean
    holdout_share: number | null
    holdout_control_count: number
    holdout_treatment_count: number
    latest_metric_name: string | null
    latest_observed_lift: number | null
    latest_sample_size: number | null
    latest_measured_at: string | null
  }>
  warnings: string[]
}

export default function ExperimentLabPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [payload, setPayload] = useState<ExperimentResultsResponse | null>(null)

  const [name, setName] = useState('')
  const [initiative, setInitiative] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [decisionRule, setDecisionRule] = useState('')
  const [successThreshold, setSuccessThreshold] = useState('')
  const [failureThreshold, setFailureThreshold] = useState('')
  const [assignmentExperimentKey, setAssignmentExperimentKey] = useState('')
  const [assignmentEntityKeys, setAssignmentEntityKeys] = useState('')
  const [holdoutPercent, setHoldoutPercent] = useState('20')

  const outcomesByExperiment = useMemo(() => {
    const map = new Map<string, ExperimentResultsResponse['outcomes']>()
    for (const outcome of payload?.outcomes ?? []) {
      const current = map.get(outcome.experiment_key) ?? []
      current.push(outcome)
      map.set(outcome.experiment_key, current)
    }
    return map
  }, [payload?.outcomes])

  const loadData = useCallback(async () => {
    const response = await fetch('/api/experiments/results?limit=100')
    if (!response.ok) {
      throw new Error(await response.text())
    }
    const body = (await response.json()) as ExperimentResultsResponse
    setPayload(body)
  }, [])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setErrorMessage(null)
    try {
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load experiment data')
    } finally {
      setRefreshing(false)
    }
  }, [loadData])

  useEffect(() => {
    setLoading(true)
    setErrorMessage(null)
    void loadData()
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load experiment data')
      })
      .finally(() => setLoading(false))
  }, [loadData])

  const submitExperiment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setErrorMessage(null)
    setMessage(null)

    try {
      const response = await fetch('/api/experiments/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          initiative,
          hypothesis,
          decision_rule: decisionRule,
          success_threshold: successThreshold ? Number(successThreshold) : null,
          failure_threshold: failureThreshold ? Number(failureThreshold) : null,
          created_by: 'dashboard:experiment-lab',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const body = (await response.json()) as { experiment_key: string; warnings?: string[] }
      setMessage(`Registered experiment: ${body.experiment_key}`)
      if (body.warnings && body.warnings.length > 0) {
        setErrorMessage(body.warnings.join(' | '))
      }
      setName('')
      setInitiative('')
      setHypothesis('')
      setDecisionRule('')
      setSuccessThreshold('')
      setFailureThreshold('')
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to register experiment')
    } finally {
      setSubmitting(false)
    }
  }

  const assignHoldouts = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setErrorMessage(null)
    setMessage(null)

    const entityKeys = assignmentEntityKeys
      .split(/[\n,]/)
      .map((value) => value.trim())
      .filter(Boolean)

    if (!assignmentExperimentKey || entityKeys.length === 0) {
      setSubmitting(false)
      setErrorMessage('Experiment key and at least one entity key are required.')
      return
    }

    try {
      const response = await fetch('/api/experiments/assignments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          experiment_key: assignmentExperimentKey,
          entity_keys: entityKeys,
          holdout_percent: Number(holdoutPercent || '20'),
          created_by: 'dashboard:experiment-lab',
        }),
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      const body = (await response.json()) as {
        assigned_count: number
        inserted_count: number
        warnings?: string[]
      }
      setMessage(
        `Assigned holdouts for ${body.assigned_count.toLocaleString()} entity keys (${body.inserted_count.toLocaleString()} new assignment rows).`
      )
      if (body.warnings && body.warnings.length > 0) {
        setErrorMessage(body.warnings.join(' | '))
      }
      setAssignmentEntityKeys('')
      await loadData()
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to assign holdouts')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Experiment Lab</h1>
          <p className="text-muted-foreground">
            Register initiative experiments, track outcomes, and enforce policy rollouts with explicit decision rules.
          </p>
        </div>
        <Button onClick={() => void refresh()} disabled={refreshing || loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {errorMessage ? (
        <Card className="border-destructive/50">
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {errorMessage}
          </CardContent>
        </Card>
      ) : null}

      {message ? (
        <Card>
          <CardContent className="py-4 text-sm">{message}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Register Experiment</CardTitle>
          <CardDescription>Create a tracked experiment before enabling major optimization changes.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={submitExperiment}>
            <div className="space-y-2">
              <Label htmlFor="name">Experiment name</Label>
              <Input id="name" value={name} onChange={(event) => setName(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="initiative">Initiative</Label>
              <Input
                id="initiative"
                value={initiative}
                onChange={(event) => setInitiative(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="hypothesis">Hypothesis</Label>
              <Textarea
                id="hypothesis"
                value={hypothesis}
                onChange={(event) => setHypothesis(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="decision-rule">Decision rule</Label>
              <Textarea
                id="decision-rule"
                value={decisionRule}
                onChange={(event) => setDecisionRule(event.target.value)}
                placeholder="Roll out if margin-ROAS improves 8% for two consecutive weeks with no conversion drop >5%."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="success-threshold">Success threshold</Label>
              <Input
                id="success-threshold"
                type="number"
                value={successThreshold}
                onChange={(event) => setSuccessThreshold(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="failure-threshold">Failure threshold</Label>
              <Input
                id="failure-threshold"
                type="number"
                value={failureThreshold}
                onChange={(event) => setFailureThreshold(event.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <Button type="submit" disabled={submitting || loading}>
                Register experiment
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Registry</CardTitle>
          <CardDescription>
            {(payload?.experiments.length ?? 0).toLocaleString()} experiments and {(payload?.outcomes.length ?? 0).toLocaleString()} outcomes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Experiment</TableHead>
                <TableHead>Initiative</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Thresholds</TableHead>
                <TableHead>Latest outcome</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(payload?.experiments ?? []).map((experiment) => {
                const latestOutcome = outcomesByExperiment.get(experiment.experiment_key)?.[0]
                return (
                  <TableRow key={experiment.experiment_key}>
                    <TableCell className="max-w-[360px]">
                      <div className="font-medium">{experiment.name}</div>
                      <div className="text-xs text-muted-foreground">{experiment.experiment_key}</div>
                    </TableCell>
                    <TableCell>{experiment.initiative}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{experiment.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-xs">
                        success: {experiment.success_threshold ?? '-'}
                        <br />
                        failure: {experiment.failure_threshold ?? '-'}
                      </div>
                    </TableCell>
                    <TableCell>
                      {latestOutcome ? (
                        <div className="text-xs">
                          {latestOutcome.metric_name}: {latestOutcome.observed_lift.toFixed(3)} ({latestOutcome.status})
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">No outcomes</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Assign Holdouts</CardTitle>
          <CardDescription>
            Assign treatment/control cohorts for initiative entities before policy expansion.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={assignHoldouts}>
            <div className="space-y-2">
              <Label htmlFor="assignment-experiment-key">Experiment key</Label>
              <Input
                id="assignment-experiment-key"
                value={assignmentExperimentKey}
                onChange={(event) => setAssignmentExperimentKey(event.target.value)}
                placeholder="query-mining-buildout-holdout-..."
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="holdout-percent">Holdout percent</Label>
              <Input
                id="holdout-percent"
                type="number"
                value={holdoutPercent}
                onChange={(event) => setHoldoutPercent(event.target.value)}
                min={1}
                max={95}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="assignment-entity-keys">Entity keys (comma or newline separated)</Label>
              <Textarea
                id="assignment-entity-keys"
                value={assignmentEntityKeys}
                onChange={(event) => setAssignmentEntityKeys(event.target.value)}
                placeholder="term-a, term-b, term-c"
                required
              />
            </div>
            <div className="md:col-span-2">
              <Button type="submit" disabled={submitting || loading}>
                Assign holdouts
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Weekly Governance Checkpoints</CardTitle>
          <CardDescription>
            Govern rollout decisions weekly using latest outcomes, holdout mix, and threshold policy.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Experiment key</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Holdout share</TableHead>
                <TableHead>Latest metric</TableHead>
                <TableHead>Checkpoint</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(payload?.governance ?? []).map((checkpoint) => (
                <TableRow key={checkpoint.experiment_key}>
                  <TableCell className="max-w-[360px]">
                    <div className="font-medium">{checkpoint.experiment_key}</div>
                    <div className="text-xs text-muted-foreground">{checkpoint.initiative}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{checkpoint.weekly_status}</Badge>
                  </TableCell>
                  <TableCell>
                    {checkpoint.holdout_share === null
                      ? '-'
                      : `${(checkpoint.holdout_share * 100).toFixed(1)}%`}
                  </TableCell>
                  <TableCell className="text-xs">
                    {checkpoint.latest_metric_name ? (
                      <>
                        <div>{checkpoint.latest_metric_name}</div>
                        <div className="text-muted-foreground">
                          lift {checkpoint.latest_observed_lift?.toFixed(3) ?? '-'} / sample{' '}
                          {checkpoint.latest_sample_size?.toLocaleString() ?? '-'}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted-foreground">No outcomes</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {checkpoint.checkpoint_due ? (
                      <Badge variant="destructive">Due</Badge>
                    ) : (
                      <Badge variant="outline">On track</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {(payload?.warnings ?? []).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Warnings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {payload?.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
