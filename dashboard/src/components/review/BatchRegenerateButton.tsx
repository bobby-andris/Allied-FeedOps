'use client'

import { useState } from 'react'
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

interface BatchRegenerateButtonProps {
  totalSkus: number
  /** Called when regeneration completes (successfully or not) */
  onComplete?: () => void
}

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
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<{
    phase: 'idle' | 'running' | 'complete'
    message: string
    percent: number
  }>({ phase: 'idle', message: '', percent: 0 })
  const [result, setResult] = useState<BatchResult | null>(null)

  // Estimate time: ~2 seconds per operation (6 ops per SKU: 3 platforms x 2 content types)
  const estimatedOperations = totalSkus * 6
  const estimatedMinutes = Math.ceil((estimatedOperations * 2) / 60)

  const handleRegenerate = async () => {
    setLoading(true)
    setProgress({ phase: 'running', message: 'Starting batch regeneration...', percent: 0 })
    setResult(null)

    try {
      // Call the batch API with all SKUs
      const response = await fetch('/api/regenerate/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all: true }),
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
          <DialogTitle>Regenerate All Content</DialogTitle>
          <DialogDescription>
            This will regenerate titles and descriptions for all {totalSkus} SKUs across Google, Bing, and Shopify platforms.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Pre-run info */}
          {progress.phase === 'idle' && (
            <div className="space-y-3">
              <div className="text-sm">
                <span className="font-medium">Total operations:</span>{' '}
                <span className="text-muted-foreground">
                  ~{estimatedOperations} (3 platforms × 2 content types × {totalSkus} SKUs)
                </span>
              </div>
              <div className="text-sm">
                <span className="font-medium">Estimated time:</span>{' '}
                <span className="text-muted-foreground">~{estimatedMinutes} minutes</span>
              </div>
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-800 dark:text-amber-200">
                This will update <code>candidate_content</code> for all SKUs. Approved content will not be affected until you re-approve.
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
            <Button onClick={handleRegenerate} disabled={loading}>
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
