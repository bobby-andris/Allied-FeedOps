'use client'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Check, X, RotateCcw, Save } from 'lucide-react'
import { useState } from 'react'

interface ApprovalControlsProps {
  sku: string
  currentStatus: 'pending' | 'approved' | 'revision' | 'rejected'
  titleApproved: boolean | null
  descriptionApproved: boolean | null
  imageApproved: boolean | null
  notes?: string | null
  onApproveAll: () => Promise<void>
  onReject: () => Promise<void>
  onRequestRevision: (notes: string) => Promise<void>
  onSaveNotes: (notes: string) => Promise<void>
  loading?: boolean
}

export function ApprovalControls({
  sku,
  currentStatus: _currentStatus,
  titleApproved,
  descriptionApproved,
  imageApproved,
  notes: initialNotes,
  onApproveAll,
  onReject,
  onRequestRevision,
  onSaveNotes,
  loading = false,
}: ApprovalControlsProps) {
  const [notes, setNotes] = useState(initialNotes || '')
  const [saving, setSaving] = useState(false)

  const allApproved = titleApproved === true && descriptionApproved === true && imageApproved === true
  const anyRejected = titleApproved === false || descriptionApproved === false || imageApproved === false

  const handleApproveAll = async () => {
    setSaving(true)
    try {
      await onApproveAll()
    } finally {
      setSaving(false)
    }
  }

  const handleReject = async () => {
    setSaving(true)
    try {
      await onReject()
    } finally {
      setSaving(false)
    }
  }

  const handleRequestRevision = async () => {
    if (!notes.trim()) {
      alert('Please add revision notes before requesting a revision.')
      return
    }
    setSaving(true)
    try {
      await onRequestRevision(notes)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveNotes = async () => {
    setSaving(true)
    try {
      await onSaveNotes(notes)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Approval Actions</CardTitle>
        <CardDescription>
          Review all elements and take action on SKU {sku}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              {titleApproved === true ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : titleApproved === false ? (
                <X className="h-4 w-4 text-red-600" />
              ) : (
                <span className="h-4 w-4 rounded-full bg-gray-300" />
              )}
              <span className="text-sm">Title</span>
            </div>
            <div className="flex items-center gap-1">
              {descriptionApproved === true ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : descriptionApproved === false ? (
                <X className="h-4 w-4 text-red-600" />
              ) : (
                <span className="h-4 w-4 rounded-full bg-gray-300" />
              )}
              <span className="text-sm">Description</span>
            </div>
            <div className="flex items-center gap-1">
              {imageApproved === true ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : imageApproved === false ? (
                <X className="h-4 w-4 text-red-600" />
              ) : (
                <span className="h-4 w-4 rounded-full bg-gray-300" />
              )}
              <span className="text-sm">Image</span>
            </div>
          </div>
          <div>
            {allApproved && (
              <span className="text-sm text-green-600 font-medium">All elements approved</span>
            )}
            {anyRejected && (
              <span className="text-sm text-red-600 font-medium">Some elements rejected</span>
            )}
          </div>
        </div>

        {/* Notes */}
        <div className="space-y-2">
          <Label htmlFor="notes">Revision Notes</Label>
          <Textarea
            id="notes"
            placeholder="Add notes for revision requests or general comments..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveNotes}
            disabled={saving || loading}
          >
            <Save className="h-4 w-4 mr-1" />
            Save Notes
          </Button>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            variant="outline"
            className="text-red-600 hover:bg-red-50 hover:text-red-700"
            onClick={handleReject}
            disabled={saving || loading}
          >
            <X className="h-4 w-4 mr-2" />
            Reject All
          </Button>
          <Button
            variant="outline"
            className="text-yellow-600 hover:bg-yellow-50 hover:text-yellow-700"
            onClick={handleRequestRevision}
            disabled={saving || loading || !notes.trim()}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Request Revision
          </Button>
          <Button
            className="bg-green-600 hover:bg-green-700 ml-auto"
            onClick={handleApproveAll}
            disabled={saving || loading}
          >
            <Check className="h-4 w-4 mr-2" />
            Approve All
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
