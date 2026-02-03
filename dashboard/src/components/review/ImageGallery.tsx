'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check, X, ChevronLeft, ChevronRight, ZoomIn, Loader2 } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

interface ImageRecord {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  score: number | null
  selected: boolean
}

interface ImageGalleryProps {
  images: ImageRecord[]
  sku: string
}

// Convert local file path to GitHub raw URL
function getImageUrl(imagePath: string | null): string | null {
  if (!imagePath) return null
  if (imagePath.startsWith('http')) return imagePath
  return `https://raw.githubusercontent.com/bobby-andris/Allied-FeedOps/master/${imagePath}`
}

export function ImageGallery({ images, sku }: ImageGalleryProps) {
  const [selectedImage, setSelectedImage] = useState<ImageRecord | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectingImage, setSelectingImage] = useState<string | null>(null)
  const router = useRouter()

  const openModal = (image: ImageRecord, index: number) => {
    setSelectedImage(image)
    setCurrentIndex(index)
  }

  const closeModal = () => {
    setSelectedImage(null)
  }

  const goToPrevious = () => {
    const newIndex = currentIndex > 0 ? currentIndex - 1 : images.length - 1
    setCurrentIndex(newIndex)
    setSelectedImage(images[newIndex])
  }

  const goToNext = () => {
    const newIndex = currentIndex < images.length - 1 ? currentIndex + 1 : 0
    setCurrentIndex(newIndex)
    setSelectedImage(images[newIndex])
  }

  const handleSelectImage = async (imageId: string) => {
    setSelectingImage(imageId)
    try {
      const response = await fetch('/api/images', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          image_id: imageId,
          master_sku: sku,
          selected: true 
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to select image')
      }

      toast.success('Image selected successfully')
      router.refresh()
      closeModal()
    } catch (error) {
      console.error('Select image error:', error)
      toast.error('Failed to select image')
    } finally {
      setSelectingImage(null)
    }
  }

  return (
    <>
      <div className="grid grid-cols-3 gap-4">
        {images.map((image, index) => (
          <div 
            key={image.id || index} 
            className={`relative rounded-lg border-2 p-2 cursor-pointer transition-all hover:shadow-lg ${
              image.selected ? 'border-primary bg-primary/5' : 'border-muted hover:border-primary/50'
            }`}
            onClick={() => openModal(image, index)}
          >
            <div className="aspect-square bg-muted rounded flex items-center justify-center text-muted-foreground overflow-hidden relative group">
              {image.image_url ? (
                <>
                  <img 
                    src={getImageUrl(image.image_url) || ''} 
                    alt={`Variation ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <ZoomIn className="h-8 w-8 text-white" />
                  </div>
                </>
              ) : (
                <span>Image {index + 1}</span>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Variation {index + 1}</span>
              {image.score && (
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  image.score >= 80 ? 'bg-green-100 text-green-800' :
                  image.score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {image.score}
                </span>
              )}
            </div>
            {image.selected && (
              <Badge className="absolute top-4 right-4 bg-primary">Selected</Badge>
            )}
          </div>
        ))}
      </div>

      <Dialog open={selectedImage !== null} onOpenChange={() => closeModal()}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>Image Variation {currentIndex + 1} of {images.length}</span>
              {selectedImage?.selected && (
                <Badge className="bg-primary">Currently Selected</Badge>
              )}
            </DialogTitle>
          </DialogHeader>
          
          <div className="relative">
            {/* Navigation arrows */}
            {images.length > 1 && (
              <>
                <Button
                  variant="outline"
                  size="icon"
                  className="absolute left-2 top-1/2 -translate-y-1/2 z-10 bg-white/90 hover:bg-white"
                  onClick={goToPrevious}
                >
                  <ChevronLeft className="h-6 w-6" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="absolute right-2 top-1/2 -translate-y-1/2 z-10 bg-white/90 hover:bg-white"
                  onClick={goToNext}
                >
                  <ChevronRight className="h-6 w-6" />
                </Button>
              </>
            )}

            {/* Image */}
            <div className="flex items-center justify-center bg-muted rounded-lg overflow-hidden" style={{ minHeight: '500px' }}>
              {selectedImage?.image_url ? (
                <img 
                  src={getImageUrl(selectedImage.image_url) || ''} 
                  alt={`Variation ${currentIndex + 1}`}
                  className="max-w-full max-h-[70vh] object-contain"
                />
              ) : (
                <span className="text-muted-foreground">No image available</span>
              )}
            </div>
          </div>

          {/* Thumbnail strip */}
          <div className="flex gap-2 justify-center overflow-x-auto py-2">
            {images.map((image, index) => (
              <button
                key={image.id || index}
                onClick={() => {
                  setCurrentIndex(index)
                  setSelectedImage(image)
                }}
                className={`flex-shrink-0 w-16 h-16 rounded border-2 overflow-hidden transition-all ${
                  index === currentIndex 
                    ? 'border-primary ring-2 ring-primary/30' 
                    : 'border-muted hover:border-primary/50'
                }`}
              >
                {image.image_url ? (
                  <img 
                    src={getImageUrl(image.image_url) || ''} 
                    alt={`Thumbnail ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-muted flex items-center justify-center text-xs">
                    {index + 1}
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Actions */}
          <div className="flex justify-between items-center pt-4 border-t">
            <div className="text-sm text-muted-foreground">
              {selectedImage?.score && (
                <span>Quality Score: <strong>{selectedImage.score}</strong></span>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={closeModal}>
                Close
              </Button>
              {!selectedImage?.selected && (
                <Button 
                  className="bg-green-600 hover:bg-green-700"
                  onClick={() => selectedImage && handleSelectImage(selectedImage.id)}
                  disabled={selectingImage !== null}
                >
                  {selectingImage === selectedImage?.id ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4 mr-2" />
                  )}
                  Select This Image
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
