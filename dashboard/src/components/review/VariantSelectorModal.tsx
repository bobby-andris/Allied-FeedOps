'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export interface VariantDataEntry {
  finish: string
  finish_code: string
  total_impressions: number
  has_lifestyle_image: boolean
}

interface VariantSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  variants: VariantDataEntry[]
  selectedFinishCode: string | null
  onSelect: (finishCode: string, finishName: string) => void
}

export function VariantSelectorModal({
  isOpen,
  onClose,
  variants,
  selectedFinishCode,
  onSelect,
}: VariantSelectorModalProps) {
  const [localSelected, setLocalSelected] = useState<string | null>(
    selectedFinishCode
  )

  const handleConfirm = () => {
    if (!localSelected) return
    const entry = variants.find((v) => v.finish_code === localSelected)
    if (entry) {
      onSelect(entry.finish_code, entry.finish)
    }
    onClose()
  }

  const formatSelectItemLabel = (entry: VariantDataEntry): string => {
    const impressions =
      entry.total_impressions > 0
        ? `${entry.total_impressions.toLocaleString()} impressions`
        : '0 impressions'
    const imageStatus = entry.has_lifestyle_image ? ' \u2713 has image' : ''
    return `${entry.finish} \u2014 ${impressions}${imageStatus}`
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Select Finish for Image Generation</DialogTitle>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          Choose which finish variant to use. The system will generate lifestyle
          images featuring that specific finish.
        </p>

        {variants.length === 0 ? (
          <div className="py-4 text-center text-sm text-muted-foreground">
            No finish variants available.
          </div>
        ) : (
          <div className="space-y-4">
            <Select
              value={localSelected ?? ''}
              onValueChange={(val) => setLocalSelected(val)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a finish..." />
              </SelectTrigger>
              <SelectContent>
                {variants.map((entry) => (
                  <SelectItem key={entry.finish_code} value={entry.finish_code}>
                    <span className="flex items-center gap-2">
                      {formatSelectItemLabel(entry)}
                      {entry.has_lifestyle_image && (
                        <Badge variant="secondary" className="text-xs ml-1">
                          has image
                        </Badge>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleConfirm} disabled={!localSelected}>
                Confirm Selection
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
