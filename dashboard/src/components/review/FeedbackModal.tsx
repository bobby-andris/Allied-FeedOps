'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Sparkles, Loader2 } from 'lucide-react'
import { FeedbackPreset } from '@/lib/supabase/types'

interface FeedbackModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  contentType: 'title' | 'description'
  currentContent: string
  onSubmit: (feedback: string, feedbackType?: FeedbackPreset) => void
  isLoading?: boolean
}

const FEEDBACK_PRESETS: { id: FeedbackPreset; label: string }[] = [
  { id: 'shorter', label: 'Make Shorter' },
  { id: 'longer', label: 'Add More Detail' },
  { id: 'more_specific', label: 'More Specific' },
  { id: 'different_angle', label: 'Different Angle' },
  { id: 'better_hook', label: 'Better Hook' },
  { id: 'more_keywords', label: 'More Keywords' },
  { id: 'less_promotional', label: 'Less Promotional' },
]

export function FeedbackModal({
  open,
  onOpenChange,
  contentType,
  currentContent,
  onSubmit,
  isLoading = false,
}: FeedbackModalProps) {
  const [feedback, setFeedback] = useState('')
  const [selectedPreset, setSelectedPreset] = useState<FeedbackPreset | undefined>()

  const handlePresetClick = (preset: FeedbackPreset) => {
    setSelectedPreset(preset)
    // Optionally prepopulate textarea with preset description
    const presetDescriptions: Record<FeedbackPreset, string> = {
      shorter: 'Make this shorter and more concise while keeping key information.',
      longer: 'Expand this with more detail and product benefits.',
      more_specific: 'Replace vague claims with specific, verifiable details.',
      different_angle: 'Take a different approach - emphasize different benefits or features.',
      more_keywords: 'Include more relevant search keywords naturally.',
      less_promotional: 'Remove promotional language, make it more factual.',
      better_hook: 'Improve the opening to be more compelling.',
    }
    if (!feedback.trim()) {
      setFeedback(presetDescriptions[preset])
    }
  }

  const handleSubmit = () => {
    if (!feedback.trim()) return
    onSubmit(feedback, selectedPreset)
  }

  const handleClose = () => {
    if (!isLoading) {
      setFeedback('')
      setSelectedPreset(undefined)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Improve {contentType === 'title' ? 'Title' : 'Description'}</DialogTitle>
          <DialogDescription>
            Provide feedback on what to change. The AI will use your feedback to generate improved content.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Current content display */}
          <div className="bg-muted p-4 rounded-lg">
            <Label className="text-sm text-muted-foreground">
              Current {contentType}:
            </Label>
            <p className="mt-2 text-sm whitespace-pre-wrap max-h-[150px] overflow-y-auto">
              {currentContent || 'No content'}
            </p>
          </div>

          {/* Quick feedback presets */}
          <div>
            <Label className="text-sm text-muted-foreground mb-2 block">
              Quick options:
            </Label>
            <div className="flex flex-wrap gap-2">
              {FEEDBACK_PRESETS.map((preset) => (
                <Button
                  key={preset.id}
                  variant={selectedPreset === preset.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handlePresetClick(preset.id)}
                  disabled={isLoading}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Custom feedback textarea */}
          <div>
            <Label htmlFor="feedback">Your feedback</Label>
            <Textarea
              id="feedback"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={`E.g., "Emphasize the solid brass construction more" or "Make the opening more compelling for homeowners"`}
              rows={4}
              className="mt-2"
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Be specific about what you want changed
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!feedback.trim() || isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Regenerating...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Regenerate with Feedback
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
