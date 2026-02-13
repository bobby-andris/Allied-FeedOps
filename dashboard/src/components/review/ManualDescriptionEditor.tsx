'use client'

import { useMemo, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Loader2, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import {
  FINISH_SENTENCE_TOKEN,
  composeDescriptionTemplate,
  deriveEditableDescriptionTemplateParts,
  validateManualVariantDescriptionTemplate,
} from '@/lib/review/manual-description'

interface ManualDescriptionEditorProps {
  sku: string
  platform: 'google' | 'bing'
  currentDescription: string
  onSaved: (description: string) => void
}

type SaveResponse = {
  success?: boolean
  description?: string
  state?: 'updated' | 'no_change'
  error?: string
  validation_errors?: string[]
}

export function ManualDescriptionEditor({
  sku,
  platform,
  currentDescription,
  onSaved,
}: ManualDescriptionEditorProps) {
  const [open, setOpen] = useState(false)
  const [prefix, setPrefix] = useState('')
  const [suffix, setSuffix] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const previewDescription = useMemo(() => composeDescriptionTemplate(prefix, suffix), [prefix, suffix])
  const validation = useMemo(
    () => validateManualVariantDescriptionTemplate(previewDescription),
    [previewDescription],
  )

  const initializeFromCurrentDescription = () => {
    const parts = deriveEditableDescriptionTemplateParts(currentDescription)
    setPrefix(parts.prefix)
    setSuffix(parts.suffix)
    setError(null)
  }

  const handleOpenChange = (next: boolean) => {
    if (next) {
      initializeFromCurrentDescription()
    }
    if (!saving) {
      setOpen(next)
    }
  }

  const handleSave = async () => {
    if (!validation.ok) {
      setError(validation.errors[0] || 'Description template is invalid.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/review/manual-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          platform,
          description: validation.normalizedDescription,
        }),
      })

      const payload = (await response.json().catch(() => ({}))) as SaveResponse
      if (!response.ok) {
        const message = payload.validation_errors?.[0] || payload.error || 'Failed to save description.'
        setError(message)
        toast.error(message)
        return
      }

      const savedDescription = payload.description || validation.normalizedDescription
      onSaved(savedDescription)
      toast.success(
        payload.state === 'no_change'
          ? 'Description already matches current template.'
          : `${platform.toUpperCase()} base description updated and applied to all variants.`,
      )
      setOpen(false)
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : 'Failed to save description.'
      setError(message)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => handleOpenChange(true)}>
        <Pencil className="h-4 w-4 mr-2" />
        Edit Base Description
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[760px]">
          <DialogHeader>
            <DialogTitle>Edit {platform.toUpperCase()} Base Description</DialogTitle>
            <DialogDescription>
              This updates the base description template for this platform and applies to all finish variants.
              The finish sentence token is locked to prevent hardcoded finish edits.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="description-prefix">Description Prefix</Label>
              <Textarea
                id="description-prefix"
                value={prefix}
                onChange={(event) => setPrefix(event.target.value)}
                disabled={saving}
                placeholder="Text before finish sentence token"
                rows={5}
              />
            </div>

            <div className="space-y-2">
              <Label>Finish Sentence Token (Locked)</Label>
              <div className="rounded-md border bg-muted/40 px-3 py-2">
                <Badge variant="outline">{FINISH_SENTENCE_TOKEN}</Badge>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description-suffix">Description Suffix</Label>
              <Textarea
                id="description-suffix"
                value={suffix}
                onChange={(event) => setSuffix(event.target.value)}
                disabled={saving}
                placeholder="Text after finish sentence token"
                rows={5}
              />
            </div>

            <div className="space-y-2">
              <Label>Preview</Label>
              <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm whitespace-pre-wrap">
                {previewDescription}
              </div>
            </div>

            {!validation.ok && (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {validation.errors[0]}
              </div>
            )}

            {error && (
              <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving || !validation.ok}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save and Apply to All Variants'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
