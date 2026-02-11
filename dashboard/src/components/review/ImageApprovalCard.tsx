'use client'

import { useState } from 'react'
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Check, X, Star, ZoomIn, Loader2, Sparkles, Upload, Home } from "lucide-react"
import { VisuallyHidden } from "@radix-ui/react-visually-hidden"
import { QualityScore } from "@/components/shared/QualityScore"

// Convert local file path to GitHub raw URL for archived images
function getImageUrl(imagePath: string | null): string | null {
  if (!imagePath) return null
  if (imagePath.startsWith('http')) return imagePath
  return `https://raw.githubusercontent.com/bobby-andris/Allied-FeedOps/archive/full-snapshot-2026-02-03/${imagePath}`
}

// Flexible image type to accommodate various data sources
interface ImageData {
  id: string
  image_url: string | null
  thumbnail_url: string | null
  variation_index: number
  score: number | null
  prompt?: string | null
  approval_status?: 'pending' | 'approved' | 'rejected' | string | null
  rejection_reason?: string | null
}

interface ImageApprovalCardProps {
  image: ImageData
  // Selection states
  isAiSelected: boolean
  isUserSelected: boolean
  isUseForMaster: boolean
  gmcPushedAt?: string | null
  // Actions
  onApprove: () => Promise<void>
  onReject: (reason?: string) => Promise<void>
  onUserSelect: () => Promise<void>
  onUseForMaster?: () => Promise<void>
  showMasterSelectionAction?: boolean
}

export function ImageApprovalCard({
  image,
  isAiSelected,
  isUserSelected,
  isUseForMaster,
  gmcPushedAt,
  onApprove,
  onReject,
  onUserSelect,
  onUseForMaster,
  showMasterSelectionAction = false,
}: ImageApprovalCardProps) {
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectDialog, setShowRejectDialog] = useState(false)
  const [showZoom, setShowZoom] = useState(false)
  const [isApproving, setIsApproving] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)
  const [isSelecting, setIsSelecting] = useState(false)
  const [isSettingMaster, setIsSettingMaster] = useState(false)

  const handleApprove = async () => {
    setIsApproving(true)
    try {
      await onApprove()
    } finally {
      setIsApproving(false)
    }
  }

  const handleReject = async () => {
    setIsRejecting(true)
    try {
      await onReject(rejectReason || undefined)
      setShowRejectDialog(false)
      setRejectReason('')
    } finally {
      setIsRejecting(false)
    }
  }

  const handleUserSelect = async () => {
    setIsSelecting(true)
    try {
      await onUserSelect()
    } finally {
      setIsSelecting(false)
    }
  }

  const handleUseForMaster = async () => {
    if (!onUseForMaster) return
    setIsSettingMaster(true)
    try {
      await onUseForMaster()
    } finally {
      setIsSettingMaster(false)
    }
  }

  const imageUrl = getImageUrl(image.image_url) || getImageUrl(image.thumbnail_url)
  const approvalStatus = image.approval_status || 'pending'
  const isApproved = approvalStatus === 'approved'
  const isPending = approvalStatus === 'pending'
  const isRejected = approvalStatus === 'rejected'

  // Determine card border style
  let cardClass = 'relative'
  if (isUserSelected) {
    cardClass += ' ring-2 ring-green-500'
  } else if (isAiSelected) {
    cardClass += ' ring-2 ring-yellow-400'
  }

  return (
    <Card className={cardClass}>
      {/* Top badges row */}
      <div className="absolute top-2 left-2 right-2 z-10 flex justify-between items-start">
        {/* Left: Selection badges */}
        <div className="flex flex-col gap-1">
          {isAiSelected && (
            <Badge className="bg-yellow-500 text-yellow-950">
              <Sparkles className="h-3 w-3 mr-1" />
              AI Pick
            </Badge>
          )}
          {isUserSelected && (
            <Badge className="bg-green-600">
              <Check className="h-3 w-3 mr-1" />
              Selected
            </Badge>
          )}
          {isUseForMaster && (
            <Badge className="bg-blue-600">
              <Home className="h-3 w-3 mr-1" />
              Master
            </Badge>
          )}
        </div>

        {/* Right: Status and GMC badges */}
        <div className="flex flex-col gap-1 items-end">
          <Badge
            className={
              isApproved
                ? 'bg-green-100 text-green-800 border-green-200'
                : isRejected
                ? 'bg-red-100 text-red-800 border-red-200'
                : 'bg-yellow-100 text-yellow-800 border-yellow-200'
            }
          >
            {approvalStatus}
          </Badge>
          {gmcPushedAt && (
            <Badge className="bg-purple-600">
              <Upload className="h-3 w-3 mr-1" />
              GMC
            </Badge>
          )}
        </div>
      </div>

      <CardContent className="p-3 pt-14">
        {/* Image with zoom trigger */}
        <div
          className="relative aspect-video cursor-zoom-in group mb-3"
          onClick={() => setShowZoom(true)}
        >
          {imageUrl ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={`Variation ${image.variation_index + 1}`}
                className="w-full h-full object-cover rounded"
              />
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20 rounded">
                <ZoomIn className="h-6 w-6 text-white" />
              </div>
            </>
          ) : (
            <div className="w-full h-full bg-muted rounded flex items-center justify-center">
              <span className="text-muted-foreground">No image</span>
            </div>
          )}
        </div>

        {/* Metadata */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-muted-foreground">
            Variation {image.variation_index + 1}
          </span>
          {image.score !== null && (
            <QualityScore score={Number(image.score)} size="sm" />
          )}
        </div>

        {/* Action buttons */}
        <div className="space-y-2">
          {/* Approval row - only for pending */}
          {isPending && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={handleApprove}
                disabled={isApproving}
              >
                {isApproving ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 mr-1" />
                )}
                Approve
              </Button>

              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => setShowRejectDialog(true)}
                disabled={isRejecting}
              >
                <X className="h-4 w-4 mr-1" />
                Reject
              </Button>
            </div>
          )}

          {/* Selection row - only for approved, not yet selected */}
          {isApproved && !isUserSelected && (
            <Button
              variant="default"
              size="sm"
              className="w-full"
              onClick={handleUserSelect}
              disabled={isSelecting}
            >
              {isSelecting ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Star className="h-4 w-4 mr-1" />
              )}
              Select for Variant
            </Button>
          )}

          {/* Use for Master - only for approved and selected */}
          {showMasterSelectionAction && isApproved && isUserSelected && !isUseForMaster && onUseForMaster && (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={handleUseForMaster}
              disabled={isSettingMaster}
            >
              {isSettingMaster ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Home className="h-4 w-4 mr-1" />
              )}
              Use for Master SKU
            </Button>
          )}

          {/* Already selected indicator */}
          {isUserSelected && (
            <div className="text-center">
              <span className="text-xs text-green-600 font-medium">
                ✓ Selected for this variant
              </span>
            </div>
          )}

          {/* Rejected state */}
          {isRejected && (
            <div className="w-full text-center">
              <span className="text-xs text-muted-foreground">
                {image.rejection_reason || 'Rejected'}
              </span>
            </div>
          )}
        </div>

        {/* Zoom Modal */}
        <Dialog open={showZoom} onOpenChange={setShowZoom}>
          <DialogContent className="max-w-4xl">
            <VisuallyHidden>
              <DialogTitle>Image Zoom - Variation {image.variation_index + 1}</DialogTitle>
            </VisuallyHidden>
            <div className="relative aspect-video w-full">
              {imageUrl && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={imageUrl}
                  alt={`Variation ${image.variation_index + 1}`}
                  className="w-full h-full object-contain"
                />
              )}
            </div>
            {image.prompt && (
              <div className="mt-4 p-3 bg-muted rounded-lg">
                <p className="text-sm font-medium mb-1">Generation Prompt</p>
                <p className="text-xs text-muted-foreground">{image.prompt}</p>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Reject Dialog */}
        <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Reject Image</DialogTitle>
              <DialogDescription>
                Optionally provide a reason for rejection to help improve future generations.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="Reason for rejection (optional)"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRejectDialog(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={isRejecting}
              >
                {isRejecting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Reject Image
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
