'use client'

import { useState, useEffect } from 'react'
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
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2 } from 'lucide-react'

interface AvailableSku {
  master_sku: string
  approval_status: string
}

interface CreateBatchModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export function CreateBatchModal({ open, onOpenChange, onCreated }: CreateBatchModalProps) {
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [selectedSkus, setSelectedSkus] = useState<string[]>([])
  const [availableSkus, setAvailableSkus] = useState<AvailableSku[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingSkus, setLoadingSkus] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch available SKUs when modal opens
  useEffect(() => {
    if (open) {
      fetchAvailableSkus()
    } else {
      // Reset form when modal closes
      setName('')
      setNotes('')
      setSelectedSkus([])
      setError(null)
    }
  }, [open])

  const fetchAvailableSkus = async () => {
    setLoadingSkus(true)
    try {
      const response = await fetch('/api/batches/available-skus')
      if (response.ok) {
        const data = await response.json()
        setAvailableSkus(data.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch available SKUs:', err)
    } finally {
      setLoadingSkus(false)
    }
  }

  const handleSkuToggle = (sku: string, checked: boolean) => {
    if (checked) {
      setSelectedSkus([...selectedSkus, sku])
    } else {
      setSelectedSkus(selectedSkus.filter(s => s !== sku))
    }
  }

  const handleSelectAll = () => {
    if (selectedSkus.length === availableSkus.length) {
      setSelectedSkus([])
    } else {
      setSelectedSkus(availableSkus.map(s => s.master_sku))
    }
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Batch name is required')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          notes: notes.trim() || null,
          skus: selectedSkus.length > 0 ? selectedSkus : undefined,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to create batch')
      }

      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create batch')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create New Batch</DialogTitle>
          <DialogDescription>
            Create a new publish batch and optionally add approved SKUs.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Batch Name */}
          <div className="grid gap-2">
            <Label htmlFor="name">Batch Name *</Label>
            <Input
              id="name"
              placeholder="e.g., Pilot Batch 3"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
            />
          </div>

          {/* Notes */}
          <div className="grid gap-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              placeholder="Optional notes about this batch..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={loading}
              rows={3}
            />
          </div>

          {/* SKU Selection */}
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label>Select SKUs (Optional)</Label>
              {availableSkus.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAll}
                  disabled={loading}
                >
                  {selectedSkus.length === availableSkus.length ? 'Deselect All' : 'Select All'}
                </Button>
              )}
            </div>
            
            {loadingSkus ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : availableSkus.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No approved SKUs available. SKUs must be approved before they can be added to a batch.
              </p>
            ) : (
              <ScrollArea className="h-[200px] border rounded-md p-3">
                <div className="space-y-2">
                  {availableSkus.map((sku) => (
                    <div key={sku.master_sku} className="flex items-center gap-3">
                      <Checkbox
                        id={`sku-${sku.master_sku}`}
                        checked={selectedSkus.includes(sku.master_sku)}
                        onCheckedChange={(checked) => 
                          handleSkuToggle(sku.master_sku, checked as boolean)
                        }
                        disabled={loading}
                      />
                      <Label
                        htmlFor={`sku-${sku.master_sku}`}
                        className="text-sm font-normal cursor-pointer"
                      >
                        {sku.master_sku}
                      </Label>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
            
            {selectedSkus.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {selectedSkus.length} SKU{selectedSkus.length !== 1 ? 's' : ''} selected
              </p>
            )}
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Create Batch
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
