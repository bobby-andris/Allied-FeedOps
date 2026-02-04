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
import { FeedbackModal } from './FeedbackModal'

interface RegenerateButtonProps {
  sku: string
  contentType: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  currentContent: string | null
  onRegenerate?: () => void
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

  const handleSimpleRegenerate = async () => {
    if (!currentContent) {
      toast.error('No content to regenerate')
      return
    }

    setIsRegenerating(true)
    toast.info('Regenerating with latest model...')

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

      const data = await response.json()

      if (!response.ok) {
        const isProd = process.env.NODE_ENV === 'production'
        const extra =
          !isProd && (data?.code || data?.details || data?.step)
            ? ` (code=${data?.code ?? 'n/a'} step=${data?.step ?? 'n/a'} details=${data?.details ?? 'n/a'})`
            : ''
        throw new Error((data.error || 'Failed to regenerate') + extra)
      }

      toast.success(`${contentType === 'title' ? 'Title' : 'Description'} regenerated successfully`)
      
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

  const handleFeedbackRegenerate = async (feedback: string, feedbackType?: string) => {
    if (!currentContent) {
      toast.error('No content to regenerate')
      return
    }

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
          mode: 'with_feedback',
          feedback: {
            current_content: currentContent,
            user_feedback: feedback,
            feedback_type: feedbackType,
          },
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        const isProd = process.env.NODE_ENV === 'production'
        const extra =
          !isProd && (data?.code || data?.details || data?.step)
            ? ` (code=${data?.code ?? 'n/a'} step=${data?.step ?? 'n/a'} details=${data?.details ?? 'n/a'})`
            : ''
        throw new Error((data.error || 'Failed to regenerate') + extra)
      }

      toast.success(`${contentType === 'title' ? 'Title' : 'Description'} regenerated with feedback`)
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
            disabled={isRegenerating || !currentContent}
            className="gap-1"
          >
            {isRegenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Regenerate
            <ChevronDown className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={handleSimpleRegenerate}
            disabled={isRegenerating}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Regenerate
            <span className="text-xs text-muted-foreground ml-2">Same prompt</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => setFeedbackModalOpen(true)}
            disabled={isRegenerating}
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
