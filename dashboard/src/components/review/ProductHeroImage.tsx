'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { VisuallyHidden } from "@radix-ui/react-visually-hidden"
import { ChevronLeft, ChevronRight, ExternalLink, ZoomIn, ImageIcon } from "lucide-react"

interface ProductHeroImageProps {
  mainImageUrl: string | null
  additionalImages: (string | null)[]
  productTitle: string
  finish?: string | null
  shopifyProductUrl?: string | null
}

export function ProductHeroImage({
  mainImageUrl,
  additionalImages,
  productTitle,
  finish,
  shopifyProductUrl,
}: ProductHeroImageProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showZoom, setShowZoom] = useState(false)

  // Filter out null images and build array
  const allImages = [mainImageUrl, ...additionalImages].filter((img): img is string => Boolean(img))

  if (allImages.length === 0) {
    return (
      <Card className="bg-muted/50">
        <CardContent className="flex flex-col items-center justify-center h-48 text-muted-foreground">
          <ImageIcon className="h-12 w-12 mb-2 opacity-50" />
          <span>No product image available</span>
        </CardContent>
      </Card>
    )
  }

  const currentImage = allImages[currentIndex]

  const goToPrevious = () => {
    setCurrentIndex((i) => (i - 1 + allImages.length) % allImages.length)
  }

  const goToNext = () => {
    setCurrentIndex((i) => (i + 1) % allImages.length)
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Product Image
          </CardTitle>
          <div className="flex items-center gap-2">
            {finish && (
              <Badge variant="outline">{finish}</Badge>
            )}
            {allImages.length > 1 && (
              <Badge variant="secondary">{currentIndex + 1} / {allImages.length}</Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Main Image with Zoom */}
          <div
            className="relative w-full h-[250px] lg:h-[300px] mx-auto cursor-zoom-in group rounded-lg overflow-hidden bg-muted/30"
            style={{ maxWidth: '600px' }}
            onClick={() => setShowZoom(true)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={currentImage}
              alt={productTitle}
              className="w-full h-full object-contain"
            />
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 rounded-lg">
              <ZoomIn className="h-8 w-8 text-white drop-shadow-lg" />
            </div>
          </div>

          {/* Navigation for multiple images */}
          {allImages.length > 1 && (
            <>
              <Button
                variant="outline"
                size="icon"
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white"
                onClick={(e) => {
                  e.stopPropagation()
                  goToPrevious()
                }}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white"
                onClick={(e) => {
                  e.stopPropagation()
                  goToNext()
                }}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              {/* Dots indicator */}
              <div className="flex justify-center gap-1 mt-4">
                {allImages.map((_, idx) => (
                  <button
                    key={idx}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      idx === currentIndex ? 'bg-primary' : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
                    }`}
                    onClick={() => setCurrentIndex(idx)}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Link to Shopify */}
        {shopifyProductUrl && (
          <div className="mt-4 text-center">
            <Button variant="outline" size="sm" asChild>
              <a href={shopifyProductUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 mr-2" />
                View on Shopify
              </a>
            </Button>
          </div>
        )}

        {/* Zoom Modal */}
        <Dialog open={showZoom} onOpenChange={setShowZoom}>
          <DialogContent className="max-w-4xl">
            <VisuallyHidden>
              <DialogTitle>Product Image Zoom</DialogTitle>
            </VisuallyHidden>
            <div className="relative">
              {/* Navigation in modal */}
              {allImages.length > 1 && (
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

              {/* Zoomed Image */}
              <div className="flex items-center justify-center bg-muted rounded-lg overflow-hidden" style={{ minHeight: '500px' }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={currentImage}
                  alt={productTitle}
                  className="max-w-full max-h-[70vh] object-contain"
                />
              </div>

              {/* Thumbnail strip */}
              {allImages.length > 1 && (
                <div className="flex gap-2 justify-center overflow-x-auto py-4">
                  {allImages.map((img, idx) => (
                    <button
                      key={idx}
                      onClick={() => setCurrentIndex(idx)}
                      className={`flex-shrink-0 w-16 h-16 rounded border-2 overflow-hidden transition-all ${
                        idx === currentIndex
                          ? 'border-primary ring-2 ring-primary/30'
                          : 'border-muted hover:border-primary/50'
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={img}
                        alt={`Thumbnail ${idx + 1}`}
                        className="w-full h-full object-cover"
                      />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
