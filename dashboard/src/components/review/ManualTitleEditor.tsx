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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Loader2, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import {
  FINISH_TOKEN,
  composeTemplateTitle,
  deriveEditableTemplateParts,
  validateManualTitleForPlatform,
  type ManualTitlePlatform,
} from '@/lib/review/manual-title'

interface ManualTitleEditorProps {
  sku: string
  platform: ManualTitlePlatform
  currentTitle: string
  onSaved: (title: string) => void
}

type SaveResponse = {
  success?: boolean
  title?: string
  state?: 'updated' | 'no_change'
  error?: string
  validation_errors?: string[]
}

export function ManualTitleEditor({ sku, platform, currentTitle, onSaved }: ManualTitleEditorProps) {
  const [open, setOpen] = useState(false)
  const [prefix, setPrefix] = useState('')
  const [suffix, setSuffix] = useState('')
  const [shopifyTitle, setShopifyTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isVariantTemplatePlatform = platform === 'google' || platform === 'bing'
  const previewTitle = useMemo(
    () => (isVariantTemplatePlatform ? composeTemplateTitle(prefix, suffix) : shopifyTitle.trim()),
    [isVariantTemplatePlatform, prefix, shopifyTitle, suffix],
  )
  const validation = useMemo(
    () => validateManualTitleForPlatform(previewTitle, platform),
    [platform, previewTitle],
  )

  const initializeFromCurrentTitle = () => {
    if (isVariantTemplatePlatform) {
      const parts = deriveEditableTemplateParts(currentTitle)
      setPrefix(parts.prefix)
      setSuffix(parts.suffix)
    } else {
      setShopifyTitle(currentTitle)
    }
    setError(null)
  }

  const handleOpenChange = (next: boolean) => {
    if (next) {
      initializeFromCurrentTitle()
    }
    if (!saving) {
      setOpen(next)
    }
  }

  const handleSave = async () => {
    if (!validation.ok) {
      setError(validation.errors[0] || 'Title template is invalid.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/review/manual-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          platform,
          title: validation.normalizedTitle,
        }),
      })

      const payload = (await response.json().catch(() => ({}))) as SaveResponse
      if (!response.ok) {
        const message = payload.validation_errors?.[0] || payload.error || 'Failed to save title.'
        setError(message)
        toast.error(message)
        return
      }

      const savedTitle = payload.title || validation.normalizedTitle
      onSaved(savedTitle)
      if (payload.state === 'no_change') {
        toast.success('Title already matches current content.')
      } else if (isVariantTemplatePlatform) {
        toast.success(`${platform.toUpperCase()} base title updated and applied to all variants.`)
      } else {
        toast.success('Shopify title updated.')
      }
      setOpen(false)
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : 'Failed to save title.'
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
        {isVariantTemplatePlatform ? 'Edit Base Title' : 'Edit Title'}
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[680px]">
          <DialogHeader>
            <DialogTitle>
              {isVariantTemplatePlatform ? `Edit ${platform.toUpperCase()} Base Title` : 'Edit Shopify Title'}
            </DialogTitle>
            <DialogDescription>
              {isVariantTemplatePlatform
                ? 'This updates the base title template for this platform and applies to all finish variants. The finish token is locked to prevent hardcoded finish edits.'
                : 'This updates the Shopify product-level title. Finish names and placeholders are blocked to keep Shopify content finish-agnostic.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {isVariantTemplatePlatform ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="title-prefix">Title Prefix</Label>
                  <Input
                    id="title-prefix"
                    value={prefix}
                    onChange={(event) => setPrefix(event.target.value)}
                    disabled={saving}
                    placeholder="Text before finish token"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Finish Token (Locked)</Label>
                  <div className="rounded-md border bg-muted/40 px-3 py-2">
                    <Badge variant="outline">{FINISH_TOKEN}</Badge>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="title-suffix">Title Suffix</Label>
                  <Input
                    id="title-suffix"
                    value={suffix}
                    onChange={(event) => setSuffix(event.target.value)}
                    disabled={saving}
                    placeholder="Text after finish token"
                  />
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="shopify-title">Shopify Title</Label>
                <Input
                  id="shopify-title"
                  value={shopifyTitle}
                  onChange={(event) => setShopifyTitle(event.target.value)}
                  disabled={saving}
                  placeholder="Product-level title for Shopify"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label>Preview</Label>
              <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm">{previewTitle}</div>
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
              ) : isVariantTemplatePlatform ? 'Save and Apply to All Variants' : 'Save Title'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
