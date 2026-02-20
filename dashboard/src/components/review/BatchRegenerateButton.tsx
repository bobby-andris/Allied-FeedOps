'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { RefreshCw, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CATCHALL_CUSTOM_LABEL } from '@/lib/regeneration/custom-label'

interface BatchRegenerateButtonProps {
  totalSkus: number
  /** Called when regeneration completes (successfully or not) */
  onComplete?: () => void
}

type RegenerateScope = 'all' | 'custom_label_0'

interface BatchResult {
  summary: {
    total_skus: number
    total_operations: number
    successful: number
    failed: number
    with_validation_warnings?: number
    no_change?: number
  }
  results?: Array<{
    sku: string
    platform: string
    content_type: string
    success: boolean
    state?: 'completed' | 'no_change'
    validation_errors?: string[]
    actionable_message?: string | null
    code?: string | null
    step?: string | null
    error?: string
  }>
}

type BatchRegenerateErrorPayload = {
  error?: string
  actionable_message?: string | null
  code?: string | null
  step?: string | null
}

interface BatchPreviewResponse {
  total_skus: number
  total_content_items: number
  estimated_time_minutes: number
  catchall_value?: string
}

interface CustomLabelsListResponse {
  custom_labels: string[]
}

function formatFailureMessage(payload: BatchRegenerateErrorPayload, fallback: string): string {
  const parts: string[] = [payload.error || fallback]
  if (payload.actionable_message) {
    parts.push(`Next step: ${payload.actionable_message}`)
  }
  if (process.env.NODE_ENV !== 'production' && (payload.code || payload.step)) {
    parts.push(`(code=${payload.code ?? 'n/a'} step=${payload.step ?? 'n/a'})`)
  }
  return parts.join(' ')
}

export function BatchRegenerateButton({
  totalSkus,
  onComplete,
}: BatchRegenerateButtonProps) {
  const [open, setOpen] = useState(false)
  const [scope, setScope] = useState<RegenerateScope>('all')
  const [customLabels, setCustomLabels] = useState<string[]>([])
  const [customLabelsLoading, setCustomLabelsLoading] = useState(false)
  const [selectedCustomLabel, setSelectedCustomLabel] = useState<string>('')
  const [preview, setPreview] = useState<BatchPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<{
    phase: 'idle' | 'running' | 'complete'
    message: string
    percent: number
  }>({ phase: 'idle', message: '', percent: 0 })
  const [result, setResult] = useState<BatchResult | null>(null)

  const targetSkus = preview?.total_skus ?? totalSkus
  // Estimate time: ~2 seconds per operation (6 ops per SKU: 3 platforms x 2 content types)
  const estimatedOperations = targetSkus * 6
  const estimatedMinutes = Math.ceil((estimatedOperations * 2) / 60)
  const canStart = (scope === 'all' || Boolean(selectedCustomLabel)) && !previewLoading && !previewError

  useEffect(() => {
    if (!open) return

    let cancelled = false
    const loadCustomLabels = async () => {
      setCustomLabelsLoading(true)
      try {
        const response = await fetch('/api/custom-labels/list')
        const payload = (await response.json()) as CustomLabelsListResponse & BatchRegenerateErrorPayload
        if (!response.ok) {
          throw new Error(formatFailureMessage(payload, 'Failed to load custom labels'))
        }

        if (cancelled) return
        const labels = Array.isArray(payload.custom_labels) ? payload.custom_labels : []
        setCustomLabels(labels)
        if (labels.length > 0) {
          setSelectedCustomLabel((current) => current || labels[0])
        }
      } catch (error) {
        if (cancelled) return
        toast.error(error instanceof Error ? error.message : 'Failed to load custom labels')
      } finally {
        if (!cancelled) {
          setCustomLabelsLoading(false)
        }
      }
    }

    void loadCustomLabels()
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    if (scope === 'custom_label_0' && !selectedCustomLabel) {
      setPreview(null)
      setPreviewError(null)
      return
    }

    let cancelled = false
    const loadPreview = async () => {
      setPreviewLoading(true)
      setPreviewError(null)

      try {
        const params = new URLSearchParams()
        if (scope === 'custom_label_0') {
          params.set('custom_label_0', selectedCustomLabel)
        }
        const query = params.toString()
        const endpoint = query ? `/api/regenerate/batch?${query}` : '/api/regenerate/batch'

        const response = await fetch(endpoint)
        const payload = (await response.json()) as BatchPreviewResponse & BatchRegenerateErrorPayload
        if (!response.ok) {
          throw new Error(formatFailureMessage(payload, 'Failed to fetch regeneration preview'))
        }

        if (!cancelled) {
          setPreview(payload)
        }
      } catch (error) {
        if (!cancelled) {
          setPreviewError(error instanceof Error ? error.message : 'Failed to fetch regeneration preview')
          setPreview(null)
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false)
        }
      }
    }

    void loadPreview()
    return () => {
      cancelled = true
    }
  }, [open, scope, selectedCustomLabel])

  const handleRegenerate = async () => {
    if (!canStart) return
    setLoading(true)
    setProgress({ phase: 'running', message: 'Starting batch regeneration...', percent: 0 })
    setResult(null)

    try {
      const requestBody = scope === 'custom_label_0'
        ? { custom_label_0: selectedCustomLabel }
        : { all: true }

      // Call the batch API with selected scope.
      const response = await fetch('/api/regenerate/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })

      // Simulate progress updates (the actual API doesn't stream progress)
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev.percent >= 95) return prev
          const increment = Math.random() * 5 + 1
          return {
            phase: 'running',
            message: `Processing SKUs... ${Math.min(95, Math.round(prev.percent + increment))}%`,
            percent: Math.min(95, prev.percent + increment),
          }
        })
      }, 2000)

      const data = (await response.json()) as BatchResult & BatchRegenerateErrorPayload
      clearInterval(progressInterval)

      if (!response.ok) {
        throw new Error(formatFailureMessage(data, 'Batch regeneration failed'))
      }

      setResult(data)
      setProgress({
        phase: 'complete',
        message: `Completed: ${data.summary.successful}/${data.summary.total_operations} successful`,
        percent: 100,
      })

      if (data.summary.failed === 0) {
        toast.success(`All ${data.summary.total_operations} content items regenerated successfully!`)
      } else {
        toast.warning(
          `Regeneration completed with ${data.summary.failed} failures out of ${data.summary.total_operations}`
        )
      }

      if ((data.summary.with_validation_warnings || 0) > 0) {
        toast.warning('Some regenerated content has validation warnings', {
          description: `${data.summary.with_validation_warnings} item(s) need review before approval.`,
        })
      }

      onComplete?.()
    } catch (error) {
      console.error('Batch regeneration error:', error)
      setProgress({
        phase: 'complete',
        message: error instanceof Error ? error.message : 'Failed',
        percent: 100,
      })
      toast.error(error instanceof Error ? error.message : 'Batch regeneration failed')
    } finally {
      setLoading(false)
    }
  }

  const resetState = () => {
    if (!loading) {
      setProgress({ phase: 'idle', message: '', percent: 0 })
      setResult(null)
      setPreviewError(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => {
      setOpen(isOpen)
      if (!isOpen) resetState()
    }}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Regenerate All
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Batch Regenerate Content</DialogTitle>
          <DialogDescription>
            Regenerate titles and descriptions across Google, Bing, and Shopify for all SKUs or a specific <code>custom_label_0</code> segment.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Pre-run info */}
          {progress.phase === 'idle' && (
            <div className="space-y-3">
              <div className="space-y-2">
                <div className="text-sm font-medium">Scope</div>
                <Select value={scope} onValueChange={(value) => setScope(value as RegenerateScope)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All regeneratable SKUs</SelectItem>
                    <SelectItem value="custom_label_0">By custom_label_0 segment</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {scope === 'custom_label_0' && (
                <div className="space-y-2">
                  <div className="text-sm font-medium">custom_label_0</div>
                  <Select
                    value={selectedCustomLabel}
                    onValueChange={setSelectedCustomLabel}
                    disabled={customLabelsLoading}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={customLabelsLoading ? 'Loading labels…' : 'Select custom_label_0'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={CATCHALL_CUSTOM_LABEL}>Catchall (blank custom_label_0)</SelectItem>
                      {customLabels.map((label) => (
                        <SelectItem key={label} value={label}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="text-sm">
                <span className="font-medium">Target SKUs:</span>{' '}
                <span className="text-muted-foreground">
                  {previewLoading ? 'Calculating…' : targetSkus}
                </span>
              </div>
              <div className="text-sm">
                <span className="font-medium">Total operations:</span>{' '}
                <span className="text-muted-foreground">
                  ~{estimatedOperations} (3 platforms × 2 content types × {targetSkus} SKUs)
                </span>
              </div>
              <div className="text-sm">
                <span className="font-medium">Estimated time:</span>{' '}
                <span className="text-muted-foreground">~{estimatedMinutes} minutes</span>
              </div>
              {previewError && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-800 dark:text-red-200">
                  {previewError}
                </div>
              )}
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-800 dark:text-amber-200">
                This updates <code>candidate_content</code> for the selected scope only. Approved content will not change until re-approved.
              </div>
            </div>
          )}

          {/* Progress */}
          {progress.phase !== 'idle' && (
            <div className="space-y-3">
              <Progress value={progress.percent} className="h-2" />
              <p className="text-sm text-center text-muted-foreground">{progress.message}</p>
            </div>
          )}

          {/* Results summary */}
          {result && (
            <div className="space-y-3 pt-2 border-t">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span>Successful:</span>
                  <span className="font-medium text-green-600">{result.summary.successful}</span>
                </div>
                <div className="flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-red-600" />
                  <span>Failed:</span>
                  <span className="font-medium text-red-600">{result.summary.failed}</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-xs text-muted-foreground">
                <div>
                  No-change retries: <span className="font-medium">{result.summary.no_change || 0}</span>
                </div>
                <div>
                  Validation warnings: <span className="font-medium">{result.summary.with_validation_warnings || 0}</span>
                </div>
              </div>

              {/* Show failed items if any */}
              {result.summary.failed > 0 && result.results && (
                <div className="max-h-32 overflow-auto text-xs space-y-1 p-2 bg-muted rounded">
                  {result.results
                    .filter((r) => !r.success)
                    .slice(0, 10)
                    .map((r, i) => (
                      <div key={i} className="text-red-600">
                        {r.sku}/{r.platform}/{r.content_type}: {r.error || 'Unknown error'}
                        {r.actionable_message ? ` Next step: ${r.actionable_message}` : ''}
                      </div>
                    ))}
                  {result.results.filter((r) => !r.success).length > 10 && (
                    <div className="text-muted-foreground">
                      ...and {result.results.filter((r) => !r.success).length - 10} more
                    </div>
                  )}
                </div>
              )}

              {/* Show validation warning items if any */}
              {(result.summary.with_validation_warnings || 0) > 0 && result.results && (
                <div className="max-h-32 overflow-auto text-xs space-y-1 p-2 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded">
                  {result.results
                    .filter((r) => r.success && (r.validation_errors?.length || 0) > 0)
                    .slice(0, 10)
                    .map((r, i) => (
                      <div key={`warn-${i}`} className="text-amber-700 dark:text-amber-300">
                        {r.sku}/{r.platform}/{r.content_type}: {(r.validation_errors || []).join('; ')}
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          {progress.phase === 'complete' ? (
            <Button onClick={() => {
              setOpen(false)
              // Refresh page to show new content
              window.location.reload()
            }}>
              Done
            </Button>
          ) : (
            <Button onClick={handleRegenerate} disabled={loading || !canStart}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Regenerating...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Start Regeneration
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
