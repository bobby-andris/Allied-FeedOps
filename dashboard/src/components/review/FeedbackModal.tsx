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
import { Checkbox } from '@/components/ui/checkbox'
import { Sparkles, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import { FeedbackPreset } from '@/lib/supabase/types'

type ToneStyle = 'formal' | 'conversational' | 'technical' | 'aspirational'
type EmphasisOption = 'finish' | 'dimensions' | 'use_case' | 'compatibility' | 'luxury'
type LengthPreference = 'shorter' | 'standard' | 'longer'

export interface StructuredFeedback {
  tone_style?: ToneStyle
  emphasis?: EmphasisOption[]
  length_preference?: LengthPreference
  save_as_correction?: boolean
}

interface FeedbackModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  contentType: 'title' | 'description'
  currentContent: string
  onSubmit: (feedback: string, feedbackType?: FeedbackPreset, structured?: StructuredFeedback) => void
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

const TONE_OPTIONS: { id: ToneStyle; label: string; description: string }[] = [
  { id: 'formal', label: 'Formal', description: 'Professional, authoritative tone' },
  { id: 'conversational', label: 'Conversational', description: 'Friendly, approachable tone' },
  { id: 'technical', label: 'Technical', description: 'Precise, specification-focused' },
  { id: 'aspirational', label: 'Aspirational', description: 'Luxury, lifestyle-oriented' },
]

const EMPHASIS_OPTIONS: { id: EmphasisOption; label: string }[] = [
  { id: 'finish', label: 'Finish Details' },
  { id: 'dimensions', label: 'Dimensions / Size' },
  { id: 'use_case', label: 'Use Case' },
  { id: 'compatibility', label: 'Compatibility' },
  { id: 'luxury', label: 'Luxury Positioning' },
]

const LENGTH_OPTIONS: { id: LengthPreference; label: string }[] = [
  { id: 'shorter', label: 'Shorter' },
  { id: 'standard', label: 'Standard' },
  { id: 'longer', label: 'Longer' },
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
  // Structured feedback state
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [toneStyle, setToneStyle] = useState<ToneStyle | undefined>()
  const [emphasis, setEmphasis] = useState<EmphasisOption[]>([])
  const [lengthPreference, setLengthPreference] = useState<LengthPreference | undefined>()
  const [saveAsCorrection, setSaveAsCorrection] = useState(false)

  const hasAnyInput = feedback.trim() || toneStyle || emphasis.length > 0 || lengthPreference

  const handlePresetClick = (preset: FeedbackPreset) => {
    setSelectedPreset(preset)
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

  const handleEmphasisToggle = (option: EmphasisOption) => {
    setEmphasis(prev =>
      prev.includes(option)
        ? prev.filter(e => e !== option)
        : [...prev, option]
    )
  }

  const handleSubmit = () => {
    if (!hasAnyInput) return
    const structured: StructuredFeedback = {
      ...(toneStyle ? { tone_style: toneStyle } : {}),
      ...(emphasis.length > 0 ? { emphasis } : {}),
      ...(lengthPreference ? { length_preference: lengthPreference } : {}),
      ...(saveAsCorrection ? { save_as_correction: true } : {}),
    }
    onSubmit(feedback, selectedPreset, Object.keys(structured).length > 0 ? structured : undefined)
  }

  const handleClose = () => {
    if (!isLoading) {
      setFeedback('')
      setSelectedPreset(undefined)
      setToneStyle(undefined)
      setEmphasis([])
      setLengthPreference(undefined)
      setSaveAsCorrection(false)
      setShowAdvanced(false)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[620px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Improve {contentType === 'title' ? 'Title' : 'Description'}</DialogTitle>
          <DialogDescription>
            Provide feedback on what to change. Use quick options, structured controls, or free-text.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Current content display */}
          <div className="bg-muted p-4 rounded-lg">
            <Label className="text-sm text-muted-foreground">
              Current {contentType}:
            </Label>
            <p className="mt-2 text-sm whitespace-pre-wrap max-h-[120px] overflow-y-auto">
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
              rows={3}
              className="mt-2"
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Be specific about what you want changed
            </p>
          </div>

          {/* Advanced Feedback — collapsible */}
          <div className="border rounded-lg">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between p-3 text-sm font-medium hover:bg-muted/50 rounded-lg transition-colors"
              disabled={isLoading}
            >
              <span className="flex items-center gap-2">
                {showAdvanced ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Advanced Feedback Controls
              </span>
              <span className="text-xs text-muted-foreground font-normal">
                {[toneStyle, emphasis.length > 0 && `${emphasis.length} emphasis`, lengthPreference]
                  .filter(Boolean)
                  .join(' · ') || 'Optional'}
              </span>
            </button>

            {showAdvanced && (
              <div className="px-4 pb-4 space-y-4 border-t pt-4">
                {/* Tone / Style */}
                <div>
                  <Label className="text-sm font-medium mb-2 block">Tone / Style</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {TONE_OPTIONS.map((option) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => setToneStyle(toneStyle === option.id ? undefined : option.id)}
                        disabled={isLoading}
                        className={`text-left px-3 py-2 rounded-md border text-sm transition-colors ${
                          toneStyle === option.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        <div className="font-medium">{option.label}</div>
                        <div className={`text-xs mt-0.5 ${toneStyle === option.id ? 'text-primary-foreground/80' : 'text-muted-foreground'}`}>
                          {option.description}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Content Emphasis */}
                <div>
                  <Label className="text-sm font-medium mb-2 block">Content Emphasis</Label>
                  <div className="flex flex-wrap gap-2">
                    {EMPHASIS_OPTIONS.map((option) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => handleEmphasisToggle(option.id)}
                        disabled={isLoading}
                        className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                          emphasis.includes(option.id)
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Length */}
                <div>
                  <Label className="text-sm font-medium mb-2 block">Length</Label>
                  <div className="flex gap-2">
                    {LENGTH_OPTIONS.map((option) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => setLengthPreference(lengthPreference === option.id ? undefined : option.id)}
                        disabled={isLoading}
                        className={`flex-1 px-3 py-2 rounded-md border text-sm font-medium transition-colors ${
                          lengthPreference === option.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Save as persistent correction */}
                <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <Checkbox
                    id="save-as-correction"
                    checked={saveAsCorrection}
                    onCheckedChange={(checked) => setSaveAsCorrection(Boolean(checked))}
                    disabled={isLoading || !hasAnyInput}
                    className="mt-0.5"
                  />
                  <div>
                    <label
                      htmlFor="save-as-correction"
                      className="text-sm font-medium cursor-pointer"
                    >
                      Remember this correction for future regenerations
                    </label>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Saves this feedback as a persistent correction. All future regenerations for this SKU will automatically include it.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!hasAnyInput || isLoading}
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
