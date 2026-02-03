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
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2 } from 'lucide-react'

interface AvailableSku {
  master_sku: string
  approval_status: string
}

interface AddSkuModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  batchId: string
  onAdded: () => void
}

export function AddSkuModal({ open, onOpenChange, batchId, onAdded }: AddSkuModalProps) {
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
      setSelectedSkus([])
      setError(null)
    }
  }, [open])

  const fetchAvailableSkus = async () => {
    setLoadingSkus(true)
    try {
      // Use exclude_batch_id to not show SKUs already in this batch
      const response = await fetch(`/api/batches/available-skus?exclude_batch_id=${batchId}`)
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
    if (selectedSkus.length === 0) {
      setError('Please select at least one SKU')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/batches', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_id: batchId,
          add_skus: selectedSkus,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to add SKUs')
      }

      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add SKUs')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add SKUs to Batch</DialogTitle>
          <DialogDescription>
            Select approved SKUs to add to this batch.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* SKU Selection */}
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label>Available SKUs</Label>
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
                No available SKUs. All approved SKUs are already assigned to active batches.
              </p>
            ) : (
              <ScrollArea className="h-[300px] border rounded-md p-3">
                <div className="space-y-2">
                  {availableSkus.map((sku) => (
                    <div key={sku.master_sku} className="flex items-center gap-3">
                      <Checkbox
                        id={`add-sku-${sku.master_sku}`}
                        checked={selectedSkus.includes(sku.master_sku)}
                        onCheckedChange={(checked) => 
                          handleSkuToggle(sku.master_sku, checked as boolean)
                        }
                        disabled={loading}
                      />
                      <Label
                        htmlFor={`add-sku-${sku.master_sku}`}
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
          <Button 
            onClick={handleSubmit} 
            disabled={loading || selectedSkus.length === 0}
          >
            {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Add {selectedSkus.length > 0 ? `${selectedSkus.length} SKU${selectedSkus.length !== 1 ? 's' : ''}` : 'SKUs'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
