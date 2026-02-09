'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { History, ChevronDown, ChevronRight, Undo, Loader2, Code2 } from 'lucide-react'
import { toast } from 'sonner'
import { RegenerationHistory as RegenerationHistoryType } from '@/lib/supabase/types'

interface RegenerationHistoryProps {
  sku: string
  contentType?: 'title' | 'description'
  platform?: 'google' | 'bing' | 'shopify'
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFeedbackPreset(preset: string | null): string {
  if (!preset) return ''
  const labels: Record<string, string> = {
    shorter: 'Make Shorter',
    longer: 'Add More Detail',
    more_specific: 'More Specific',
    different_angle: 'Different Angle',
    more_keywords: 'More Keywords',
    less_promotional: 'Less Promotional',
    better_hook: 'Better Hook',
  }
  return labels[preset] || preset
}

export function RegenerationHistory({
  sku,
  contentType,
  platform,
}: RegenerationHistoryProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [history, setHistory] = useState<RegenerationHistoryType[]>([])
  const [loading, setLoading] = useState(false)
  const [reverting, setReverting] = useState<string | null>(null)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ sku })
      if (contentType) params.append('content_type', contentType)
      if (platform) params.append('platform', platform)

      const response = await fetch(`/api/regenerate/history?${params}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch history')
      }

      setHistory(data.history)
    } catch (error) {
      console.error('Failed to fetch history:', error)
      toast.error('Failed to load regeneration history')
    } finally {
      setLoading(false)
    }
  }, [sku, contentType, platform])

  // Fetch history when opened
  useEffect(() => {
    if (isOpen) {
      fetchHistory()
    }
  }, [isOpen, fetchHistory])

  const handleRevert = async (entry: RegenerationHistoryType) => {
    if (!entry.previous_content) {
      toast.error('No previous content to revert to')
      return
    }

    setReverting(entry.id)
    try {
      const response = await fetch('/api/regenerate/revert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: entry.master_sku,
          content_type: entry.content_type,
          platform: entry.platform,
          history_id: entry.id,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to revert')
      }

      toast.success('Reverted to previous version')
      
      // Refresh the page to show reverted content
      window.location.reload()
    } catch (error) {
      console.error('Revert error:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to revert')
    } finally {
      setReverting(null)
    }
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 w-full justify-start">
          {isOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          <History className="h-4 w-4" />
          Regeneration History
          {history.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {history.length}
            </Badge>
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Recent Regenerations</CardTitle>
          </CardHeader>
          <CardContent className="py-0 pb-4">
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : history.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                No regeneration history for this content
              </p>
            ) : (
              <div className="space-y-3">
                {history.map((entry) => (
                  <div
                    key={entry.id}
                    className="border-l-2 border-muted pl-4 py-2 relative"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 text-sm">
                          <Badge
                            variant={entry.mode === 'with_feedback' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {entry.mode === 'simple' ? 'Simple' : 'With Feedback'}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {entry.content_type} • {entry.platform}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatDate(entry.created_at)}
                        </p>
                        {entry.feedback_text && (
                          <p className="text-sm text-muted-foreground mt-2 italic">
                            &ldquo;{entry.feedback_text}&rdquo;
                          </p>
                        )}
                        {entry.feedback_preset && (
                          <Badge variant="outline" className="mt-1 text-xs">
                            {formatFeedbackPreset(entry.feedback_preset)}
                          </Badge>
                        )}
                        {entry.model_version && entry.model_version !== 'revert' && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Model: {entry.model_version}
                          </p>
                        )}
                      </div>
                      {entry.previous_content && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRevert(entry)}
                          disabled={reverting === entry.id}
                          className="shrink-0"
                        >
                          {reverting === entry.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <>
                              <Undo className="h-3 w-3 mr-1" />
                              Revert
                            </>
                          )}
                        </Button>
                      )}
                    </div>

                    {/* Prompt Display Section */}
                    {(entry.system_prompt || entry.user_prompt) && (
                      <Collapsible className="mt-3">
                        <CollapsibleTrigger asChild>
                          <Button variant="ghost" size="sm" className="gap-2 text-xs h-7">
                            <Code2 className="h-3 w-3" />
                            View Prompt
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="mt-2 space-y-3">
                          {entry.system_prompt && (
                            <div>
                              <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                                System Prompt
                              </h5>
                              <pre className="text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-[300px] overflow-y-auto whitespace-pre-wrap font-mono">
                                {entry.system_prompt}
                              </pre>
                            </div>
                          )}
                          {entry.user_prompt && (
                            <div>
                              <h5 className="text-xs font-semibold text-muted-foreground mb-1">
                                User Prompt (SKU-specific + Platform Context)
                              </h5>
                              <pre className="text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-[300px] overflow-y-auto whitespace-pre-wrap font-mono">
                                {entry.user_prompt}
                              </pre>
                            </div>
                          )}
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  )
}
