'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, X, ZoomIn } from 'lucide-react'
import { QualityScore } from '@/components/shared/QualityScore'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface ImageVariation {
  variationIndex: number
  imageUrl: string | null
  score: number | null
  selected: boolean
}

interface ImageGalleryProps {
  images: ImageVariation[]
  approved?: boolean | null
  onSelect: (variationIndex: number) => void
  onApprove?: () => void
  onReject?: () => void
  disabled?: boolean
}

export function ImageGallery({
  images,
  approved,
  onSelect,
  onApprove,
  onReject,
  disabled = false,
}: ImageGalleryProps) {
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  const getApprovalStatus = () => {
    if (approved === true) return { label: 'Approved', className: 'bg-green-100 text-green-800' }
    if (approved === false) return { label: 'Rejected', className: 'bg-red-100 text-red-800' }
    return { label: 'Pending', className: 'bg-gray-100 text-gray-800' }
  }

  const status = getApprovalStatus()
  const selectedImage = images.find(img => img.selected)

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                Lifestyle Images
                <Badge className={status.className}>{status.label}</Badge>
              </CardTitle>
              <CardDescription>
                Select the best lifestyle image for this SKU
              </CardDescription>
            </div>
            {!disabled && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className={approved === false ? 'bg-red-50 border-red-200' : 'text-red-600'}
                  onClick={onReject}
                >
                  <X className="h-4 w-4 mr-1" /> Reject
                </Button>
                <Button
                  size="sm"
                  className={approved === true ? 'bg-green-600' : 'bg-green-600 hover:bg-green-700'}
                  onClick={onApprove}
                >
                  <Check className="h-4 w-4 mr-1" /> Approve
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {images.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No lifestyle images generated for this SKU
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {images.map((image) => (
                <div
                  key={image.variationIndex}
                  className={`relative rounded-lg border-2 p-2 cursor-pointer transition-all ${
                    image.selected
                      ? 'border-primary bg-primary/5 ring-2 ring-primary/20'
                      : 'border-muted hover:border-primary/50'
                  }`}
                  onClick={() => !disabled && onSelect(image.variationIndex)}
                >
                  {/* Image Container */}
                  <div className="aspect-square bg-muted rounded overflow-hidden relative group">
                    {image.imageUrl ? (
                      <>
                        <img
                          src={image.imageUrl}
                          alt={`Variation ${image.variationIndex + 1}`}
                          className="w-full h-full object-cover"
                        />
                        <button
                          className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPreviewImage(image.imageUrl)
                          }}
                        >
                          <ZoomIn className="h-8 w-8 text-white" />
                        </button>
                      </>
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                        No Image
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Variation {image.variationIndex + 1}
                    </span>
                    {image.score !== null && (
                      <QualityScore score={image.score} size="sm" showLabel={false} />
                    )}
                  </div>

                  {/* Selected Badge */}
                  {image.selected && (
                    <Badge className="absolute top-4 right-4 bg-primary">
                      Selected
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          )}

          {selectedImage && (
            <div className="mt-4 p-3 rounded-lg bg-muted text-sm">
              <span className="font-medium">Selected: </span>
              Variation {selectedImage.variationIndex + 1}
              {selectedImage.score !== null && (
                <span className="ml-2 text-muted-foreground">
                  (Score: {selectedImage.score})
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Image Preview Dialog */}
      <Dialog open={!!previewImage} onOpenChange={() => setPreviewImage(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Image Preview</DialogTitle>
          </DialogHeader>
          {previewImage && (
            <img
              src={previewImage}
              alt="Preview"
              className="w-full h-auto rounded-lg"
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
