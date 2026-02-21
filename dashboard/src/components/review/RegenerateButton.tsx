'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { RefreshCw, MessageSquare, ChevronDown, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { FeedbackModal, StructuredFeedback } from './FeedbackModal'

interface RegenerateButtonProps {
  sku: string
  contentType: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  currentContent: string | null
  onRegenerate?: () => void
}

type RegenerateApiResponse = {
  success?: boolean
  error?: string
  code?: string | null
  details?: string | null
  step?: string | null
  state?: 'completed' | 'no_change'
  actionable_message?: string | null
  validation_errors?: string[]
}

function formatActionableError(
  data: RegenerateApiResponse | null | undefined,
  fallback: string
): string {
  const base = data?.error || fallback
  const parts: string[] = [base]

  if (data?.actionable_message) {
    parts.push(`Next step: ${data.actionable_message}`)
  }
  if (Array.isArray(data?.validation_errors) && data.validation_errors.length > 0) {
    parts.push(`Validation: ${data.validation_errors.slice(0, 2).join('; ')}`)
  }

  if (process.env.NODE_ENV !== 'production' && (data?.code || data?.step || data?.details)) {
    parts.push(
      `(code=${data?.code ?? 'n/a'} step=${data?.step ?? 'n/a'} details=${data?.details ?? 'n/a'})`
    )
  }

  return parts.join(' ')
}

export function RegenerateButton({
  sku,
  contentType,
  platform,
  currentContent,
  onRegenerate,
}: RegenerateButtonProps) {
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)

  const isInitialGeneration = !currentContent

  const handleSimpleRegenerate = async () => {
    setIsRegenerating(true)
    toast.info(isInitialGeneration ? 'Generating content...' : 'Regenerating with latest model...')

    try {
      const response = await fetch('/api/regenerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          content_type: contentType,
          platform,
          mode: 'simple',
        }),
      })

      const data: RegenerateApiResponse = await response.json()

      if (!response.ok) {
        throw new Error(formatActionableError(data, 'Failed to regenerate'))
      }

      if (data.state === 'no_change') {
        toast.info(data.actionable_message || 'No content changes were needed')
      } else {
        toast.success(`${contentType === 'title' ? 'Title' : 'Description'} ${isInitialGeneration ? 'generated' : 'regenerated'} successfully`)
      }

      if (data.validation_errors && data.validation_errors.length > 0) {
        toast.warning('Validation warnings detected', {
          description: data.validation_errors.slice(0, 3).join('; '),
        })
      }

      // Trigger parent refresh
      onRegenerate?.()
      
      // Refresh the page to show new content
      window.location.reload()
    } catch (error) {
      console.error('Regeneration error:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to regenerate')
    } finally {
      setIsRegenerating(false)
    }
  }

  const handleFeedbackRegenerate = async (feedback: string, feedbackType?: string, structured?: StructuredFeedback) => {
    setIsRegenerating(true)
    toast.info('Regenerating with feedback...')

    try {
      const response = await fetch('/api/regenerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          content_type: contentType,
          platform,
          mode: feedback ? 'with_feedback' : 'simple',
          feedback: feedback ? {
            current_content: currentContent,
            user_feedback: feedback,
            feedback_type: feedbackType,
          } : undefined,
          // Structured feedback fields (FIX-01) — forwarded to Python pipeline
          ...(structured?.tone_style ? { tone_style: structured.tone_style } : {}),
          ...(structured?.emphasis && structured.emphasis.length > 0 ? { emphasis: structured.emphasis } : {}),
          ...(structured?.length_preference ? { length_preference: structured.length_preference } : {}),
          ...(structured?.save_as_correction ? { save_as_correction: true } : {}),
        }),
      })

      const data: RegenerateApiResponse = await response.json()

      if (!response.ok) {
        throw new Error(formatActionableError(data, 'Failed to regenerate'))
      }

      if (data.state === 'no_change') {
        toast.info(data.actionable_message || 'No content changes were needed')
      } else {
        toast.success(`${contentType === 'title' ? 'Title' : 'Description'} regenerated with feedback`)
      }

      if (data.validation_errors && data.validation_errors.length > 0) {
        toast.warning('Validation warnings detected', {
          description: data.validation_errors.slice(0, 3).join('; '),
        })
      }
      setFeedbackModalOpen(false)
      
      // Trigger parent refresh
      onRegenerate?.()
      
      // Refresh the page to show new content
      window.location.reload()
    } catch (error) {
      console.error('Regeneration error:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to regenerate')
    } finally {
      setIsRegenerating(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={isRegenerating}
            className="gap-1"
          >
            {isRegenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {isInitialGeneration ? 'Generate' : 'Regenerate'}
            <ChevronDown className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={handleSimpleRegenerate}
            disabled={isRegenerating}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            {isInitialGeneration ? 'Generate' : 'Regenerate'}
            <span className="text-xs text-muted-foreground ml-2">{isInitialGeneration ? 'Create new' : 'Same prompt'}</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => setFeedbackModalOpen(true)}
            disabled={isRegenerating || isInitialGeneration}
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Regenerate with Feedback
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <FeedbackModal
        open={feedbackModalOpen}
        onOpenChange={setFeedbackModalOpen}
        contentType={contentType}
        currentContent={currentContent || ''}
        onSubmit={handleFeedbackRegenerate}
        isLoading={isRegenerating}
      />
    </>
  )
}
