# Task: Enhance SKU Review Page with Product Images & Lifestyle Approval

## Objective

Enhance the SKU review page (`/review/[sku]`) with two critical missing features:
1. **Product Hero Image** - Display the actual product image so reviewers can see what they're reviewing
2. **Lifestyle Image Approval** - Add a proper section for reviewing and approving generated lifestyle images at the correct level (master SKU vs variant)

## Problem Statement

### Issue 1: No Product Image Displayed

Currently, reviewers see titles and descriptions but **cannot see the actual product**. This makes it difficult to:
- Verify descriptions match the product
- Confirm finish-specific content is accurate
- Assess if generated lifestyle images match the product

### Issue 2: Lifestyle Image Section Incomplete

The current lifestyle images section (`SkuReviewClient.tsx` lines 444-465):
- Only shows when images exist (no empty state guidance)
- Doesn't distinguish between master SKU vs variant-level images
- No clear workflow for which images need approval
- Missing connection to the approval workflow

## Current State Analysis

### File: `dashboard/src/components/review/SkuReviewClient.tsx`

**What exists:**
- Content comparison cards (title/description baseline vs candidate)
- Platform tabs (Google, Bing, Shopify)
- Variant selector (for finish selection)
- Approval status section
- Basic lifestyle images section (lines 444-465)

**What's missing:**
- Product hero image display
- Variant-specific image display
- Clear lifestyle image approval workflow
- Connection between variant selection and images

### File: `dashboard/src/components/review/ImageGallery.tsx`

**Current implementation:**
- Displays image thumbnails
- Click to enlarge functionality
- Selection state for choosing images

**Missing:**
- Variant-level image grouping
- Approval status per image
- Image metadata display (finish, generation date, score)

## Solution Overview

### Part 1: Add Product Hero Image

Display the product's main image prominently at the top of the review page so reviewers can see what they're working with.

### Part 2: Enhance Lifestyle Image Approval

Create a proper workflow for reviewing and approving lifestyle images that:
- Shows images at the correct level (master vs variant)
- Tracks approval status per image
- Allows selection of the best image
- Shows image quality scores

## Database Schema Enhancement

```sql
-- Enhance generated_images table for approval tracking
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS approval_status text DEFAULT 'pending';
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS approved_by text;
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS approved_at timestamptz;
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS rejection_reason text;
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS finish text; -- NULL = master SKU image
ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS finish_code text;

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_generated_images_approval
  ON generated_images(master_sku, finish, approval_status);

-- Lifestyle image selection tracking
CREATE TABLE IF NOT EXISTS lifestyle_image_selections (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  finish text, -- NULL = master SKU selection
  selected_image_id uuid REFERENCES generated_images(id),
  selection_reason text,
  selected_by text,
  selected_at timestamptz DEFAULT now(),
  UNIQUE(master_sku, finish)
);
```

## Files to Create/Modify

### New Components

- `dashboard/src/components/review/ProductHeroImage.tsx` - Product image display
- `dashboard/src/components/review/LifestyleImageReview.tsx` - Enhanced image approval
- `dashboard/src/components/review/ImageApprovalCard.tsx` - Individual image card

### Modified Files

- `dashboard/src/components/review/SkuReviewClient.tsx` - Add hero image, enhance layout
- `dashboard/src/app/(dashboard)/review/[sku]/page.tsx` - Fetch product image data
- `dashboard/src/app/api/review/images/route.ts` - Image approval API

## Implementation

### Part 1: Product Hero Image Component

```tsx
// dashboard/src/components/review/ProductHeroImage.tsx

'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, ExternalLink, ZoomIn } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from '@/components/ui/dialog'

interface ProductHeroImageProps {
  mainImageUrl: string | null
  additionalImages?: string[]
  productTitle: string
  finish?: string | null
  shopifyProductUrl?: string | null
}

export function ProductHeroImage({
  mainImageUrl,
  additionalImages = [],
  productTitle,
  finish,
  shopifyProductUrl,
}: ProductHeroImageProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const allImages = mainImageUrl ? [mainImageUrl, ...additionalImages] : additionalImages

  if (allImages.length === 0) {
    return (
      <Card className="bg-muted/50">
        <CardContent className="flex items-center justify-center h-48 text-muted-foreground">
          No product image available
        </CardContent>
      </Card>
    )
  }

  const currentImage = allImages[currentIndex]

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Product Image</CardTitle>
          {finish && (
            <Badge variant="outline">{finish}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Main Image with Zoom */}
          <Dialog>
            <DialogTrigger asChild>
              <div className="relative aspect-square w-full max-w-md mx-auto cursor-zoom-in group">
                <Image
                  src={currentImage}
                  alt={productTitle}
                  fill
                  className="object-contain rounded-lg"
                />
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 rounded-lg">
                  <ZoomIn className="h-8 w-8 text-white drop-shadow-lg" />
                </div>
              </div>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <div className="relative aspect-square w-full">
                <Image
                  src={currentImage}
                  alt={productTitle}
                  fill
                  className="object-contain"
                />
              </div>
            </DialogContent>
          </Dialog>

          {/* Navigation for multiple images */}
          {allImages.length > 1 && (
            <>
              <Button
                variant="outline"
                size="icon"
                className="absolute left-2 top-1/2 -translate-y-1/2"
                onClick={() => setCurrentIndex((i) => (i - 1 + allImages.length) % allImages.length)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setCurrentIndex((i) => (i + 1) % allImages.length)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              {/* Dots indicator */}
              <div className="flex justify-center gap-1 mt-4">
                {allImages.map((_, idx) => (
                  <button
                    key={idx}
                    className={`w-2 h-2 rounded-full ${
                      idx === currentIndex ? 'bg-primary' : 'bg-muted-foreground/30'
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
      </CardContent>
    </Card>
  )
}
```

### Part 2: Enhanced Lifestyle Image Review Component

```tsx
// dashboard/src/components/review/LifestyleImageReview.tsx

'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApprovalActions } from '@/components/review/ApprovalActions'
import { ImageApprovalCard } from '@/components/review/ImageApprovalCard'
import { Check, X, Image as ImageIcon, RefreshCw } from 'lucide-react'

interface LifestyleImage {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  score: number | null
  selected: boolean
  approval_status: 'pending' | 'approved' | 'rejected'
  finish: string | null // NULL = master SKU image
  finish_code: string | null
  generation_prompt?: string
  generated_at?: string
}

interface VariantInfo {
  finish: string
  finish_code: string
}

interface LifestyleImageReviewProps {
  sku: string
  images: LifestyleImage[]
  variants: VariantInfo[]
  selectedFinish: string | null
  onImageSelect: (imageId: string) => void
  onApprovalChange: (imageId: string, status: 'approved' | 'rejected', reason?: string) => void
}

export function LifestyleImageReview({
  sku,
  images,
  variants,
  selectedFinish,
  onImageSelect,
  onApprovalChange,
}: LifestyleImageReviewProps) {
  const [activeTab, setActiveTab] = useState<'master' | 'variants'>('master')

  // Separate master SKU images from variant-specific images
  const masterImages = images.filter(img => !img.finish)
  const variantImages = images.filter(img => img.finish)

  // Group variant images by finish
  const imagesByFinish = variantImages.reduce((acc, img) => {
    const finish = img.finish || 'Unknown'
    if (!acc[finish]) acc[finish] = []
    acc[finish].push(img)
    return acc
  }, {} as Record<string, LifestyleImage[]>)

  // Get images for currently selected finish
  const currentFinishImages = selectedFinish ? imagesByFinish[selectedFinish] || [] : []

  // Count approval stats
  const masterApproved = masterImages.filter(i => i.approval_status === 'approved').length
  const masterPending = masterImages.filter(i => i.approval_status === 'pending').length
  const variantApproved = variantImages.filter(i => i.approval_status === 'approved').length
  const variantPending = variantImages.filter(i => i.approval_status === 'pending').length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              Lifestyle Images
            </CardTitle>
            <CardDescription>
              Review and approve generated lifestyle images
            </CardDescription>
          </div>

          {/* Summary badges */}
          <div className="flex gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{masterImages.length}</div>
              <div className="text-xs text-muted-foreground">Master SKU</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{variantImages.length}</div>
              <div className="text-xs text-muted-foreground">Variant</div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {images.length === 0 ? (
          <EmptyImageState sku={sku} />
        ) : (
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'master' | 'variants')}>
            <TabsList className="mb-4">
              <TabsTrigger value="master" className="gap-2">
                Master SKU Images
                {masterPending > 0 && (
                  <Badge variant="secondary" className="ml-1">{masterPending} pending</Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="variants" className="gap-2">
                Variant Images
                {variantPending > 0 && (
                  <Badge variant="secondary" className="ml-1">{variantPending} pending</Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="master">
              <MasterImageSection
                images={masterImages}
                sku={sku}
                onImageSelect={onImageSelect}
                onApprovalChange={onApprovalChange}
              />
            </TabsContent>

            <TabsContent value="variants">
              <VariantImageSection
                imagesByFinish={imagesByFinish}
                variants={variants}
                selectedFinish={selectedFinish}
                currentFinishImages={currentFinishImages}
                sku={sku}
                onImageSelect={onImageSelect}
                onApprovalChange={onApprovalChange}
              />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  )
}

function EmptyImageState({ sku }: { sku: string }) {
  return (
    <div className="text-center py-12 border-2 border-dashed rounded-lg">
      <ImageIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
      <h3 className="font-medium mb-2">No Lifestyle Images Generated</h3>
      <p className="text-muted-foreground text-sm mb-4">
        Lifestyle images haven't been generated for SKU {sku} yet.
      </p>
      <Button variant="outline">
        <RefreshCw className="h-4 w-4 mr-2" />
        Generate Lifestyle Images
      </Button>
    </div>
  )
}

function MasterImageSection({
  images,
  sku,
  onImageSelect,
  onApprovalChange,
}: {
  images: LifestyleImage[]
  sku: string
  onImageSelect: (id: string) => void
  onApprovalChange: (id: string, status: 'approved' | 'rejected', reason?: string) => void
}) {
  const selectedImage = images.find(i => i.selected)

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 dark:bg-blue-900/20 dark:border-blue-800">
        <p className="text-sm">
          <strong>Master SKU Images</strong> are used for Shopify product pages where all finishes
          share one page. These should be finish-neutral or show the most popular finish.
        </p>
      </div>

      {/* Selected image highlight */}
      {selectedImage && (
        <div className="p-4 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800">
          <div className="flex items-center gap-2 mb-2">
            <Check className="h-4 w-4 text-green-600" />
            <span className="font-medium">Selected for publishing</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Variation {selectedImage.variation_index + 1} will be used for the Shopify product page.
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {images.map((image) => (
          <ImageApprovalCard
            key={image.id}
            image={image}
            isSelected={image.selected}
            onSelect={() => onImageSelect(image.id)}
            onApprove={() => onApprovalChange(image.id, 'approved')}
            onReject={(reason) => onApprovalChange(image.id, 'rejected', reason)}
          />
        ))}
      </div>

      {/* Bulk approval actions */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <ApprovalActions sku={sku} finish={null} type="image" size="sm" />
      </div>
    </div>
  )
}

function VariantImageSection({
  imagesByFinish,
  variants,
  selectedFinish,
  currentFinishImages,
  sku,
  onImageSelect,
  onApprovalChange,
}: {
  imagesByFinish: Record<string, LifestyleImage[]>
  variants: VariantInfo[]
  selectedFinish: string | null
  currentFinishImages: LifestyleImage[]
  sku: string
  onImageSelect: (id: string) => void
  onApprovalChange: (id: string, status: 'approved' | 'rejected', reason?: string) => void
}) {
  const finishesWithImages = Object.keys(imagesByFinish)
  const finishesWithoutImages = variants
    .filter(v => !finishesWithImages.includes(v.finish))
    .map(v => v.finish)

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-800">
        <p className="text-sm">
          <strong>Variant Images</strong> are used for Google and Bing Shopping feeds where each
          finish has its own listing. These should show the specific finish in a lifestyle context.
        </p>
      </div>

      {/* Coverage summary */}
      <div className="flex gap-4 text-sm">
        <div>
          <Badge variant="default" className="mr-2">{finishesWithImages.length}</Badge>
          finishes with images
        </div>
        <div>
          <Badge variant="secondary" className="mr-2">{finishesWithoutImages.length}</Badge>
          finishes need images
        </div>
      </div>

      {/* Show selected finish images or overview */}
      {selectedFinish ? (
        <div>
          <h4 className="font-medium mb-3 flex items-center gap-2">
            <Badge variant="outline">{selectedFinish}</Badge>
            {currentFinishImages.length} image(s)
          </h4>

          {currentFinishImages.length === 0 ? (
            <div className="text-center py-8 border-2 border-dashed rounded-lg">
              <p className="text-muted-foreground mb-4">
                No lifestyle images generated for {selectedFinish} yet.
              </p>
              <Button variant="outline" size="sm">
                <RefreshCw className="h-4 w-4 mr-2" />
                Generate for {selectedFinish}
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {currentFinishImages.map((image) => (
                <ImageApprovalCard
                  key={image.id}
                  image={image}
                  isSelected={image.selected}
                  onSelect={() => onImageSelect(image.id)}
                  onApprove={() => onApprovalChange(image.id, 'approved')}
                  onReject={(reason) => onApprovalChange(image.id, 'rejected', reason)}
                />
              ))}
            </div>
          )}

          {/* Approval actions for this finish */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            <ApprovalActions sku={sku} finish={selectedFinish} type="image" size="sm" />
          </div>
        </div>
      ) : (
        <div>
          <p className="text-muted-foreground mb-4">
            Select a finish from the variant selector above to review its images.
          </p>

          {/* Quick overview grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {finishesWithImages.slice(0, 8).map((finish) => {
              const finishImages = imagesByFinish[finish]
              const approved = finishImages.filter(i => i.approval_status === 'approved').length
              const firstImage = finishImages[0]

              return (
                <div key={finish} className="border rounded-lg p-2">
                  {firstImage?.thumbnail_url && (
                    <div className="relative aspect-video mb-2">
                      <Image
                        src={firstImage.thumbnail_url}
                        alt={finish}
                        fill
                        className="object-cover rounded"
                      />
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">{finish}</span>
                    <Badge variant={approved > 0 ? 'default' : 'secondary'} className="text-xs">
                      {approved}/{finishImages.length}
                    </Badge>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
```

### Part 3: Individual Image Approval Card

```tsx
// dashboard/src/components/review/ImageApprovalCard.tsx

'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Check, X, Star, ZoomIn, MessageSquare } from 'lucide-react'
import { QualityScore } from '@/components/shared/QualityScore'

interface ImageApprovalCardProps {
  image: {
    id: string
    image_url: string | null
    thumbnail_url: string | null
    score: number | null
    variation_index: number
    approval_status: 'pending' | 'approved' | 'rejected'
    generation_prompt?: string
    generated_at?: string
  }
  isSelected: boolean
  onSelect: () => void
  onApprove: () => void
  onReject: (reason?: string) => void
}

export function ImageApprovalCard({
  image,
  isSelected,
  onSelect,
  onApprove,
  onReject,
}: ImageApprovalCardProps) {
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectDialog, setShowRejectDialog] = useState(false)

  const handleReject = () => {
    onReject(rejectReason || undefined)
    setShowRejectDialog(false)
    setRejectReason('')
  }

  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    approved: 'bg-green-100 text-green-800 border-green-200',
    rejected: 'bg-red-100 text-red-800 border-red-200',
  }

  return (
    <Card className={`relative ${isSelected ? 'ring-2 ring-primary' : ''}`}>
      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute top-2 left-2 z-10">
          <Badge className="bg-primary">
            <Star className="h-3 w-3 mr-1" />
            Selected
          </Badge>
        </div>
      )}

      {/* Status badge */}
      <div className="absolute top-2 right-2 z-10">
        <Badge className={statusColors[image.approval_status]}>
          {image.approval_status}
        </Badge>
      </div>

      <CardContent className="p-3">
        {/* Image with zoom dialog */}
        <Dialog>
          <DialogTrigger asChild>
            <div className="relative aspect-video cursor-zoom-in group mb-3">
              {image.thumbnail_url || image.image_url ? (
                <>
                  <Image
                    src={image.thumbnail_url || image.image_url!}
                    alt={`Variation ${image.variation_index + 1}`}
                    fill
                    className="object-cover rounded"
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
          </DialogTrigger>
          <DialogContent className="max-w-4xl">
            <div className="relative aspect-video w-full">
              <Image
                src={image.image_url || image.thumbnail_url!}
                alt={`Variation ${image.variation_index + 1}`}
                fill
                className="object-contain"
              />
            </div>
            {image.generation_prompt && (
              <div className="mt-4 p-3 bg-muted rounded-lg">
                <p className="text-sm font-medium mb-1">Generation Prompt</p>
                <p className="text-xs text-muted-foreground">{image.generation_prompt}</p>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Metadata */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-muted-foreground">
            Variation {image.variation_index + 1}
          </span>
          {image.score !== null && (
            <QualityScore score={image.score} size="sm" />
          )}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {image.approval_status === 'pending' && (
            <>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={onApprove}
              >
                <Check className="h-4 w-4 mr-1" />
                Approve
              </Button>

              <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="flex-1">
                    <X className="h-4 w-4 mr-1" />
                    Reject
                  </Button>
                </DialogTrigger>
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
                    <Button variant="destructive" onClick={handleReject}>
                      Reject Image
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          )}

          {image.approval_status !== 'pending' && !isSelected && (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={onSelect}
            >
              <Star className="h-4 w-4 mr-1" />
              Select for Publishing
            </Button>
          )}

          {isSelected && (
            <Button
              variant="secondary"
              size="sm"
              className="w-full"
              disabled
            >
              <Check className="h-4 w-4 mr-1" />
              Selected
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
```

### Part 4: Updated SkuReviewClient Integration

```tsx
// dashboard/src/components/review/SkuReviewClient.tsx (partial - key changes)

import { ProductHeroImage } from '@/components/review/ProductHeroImage'
import { LifestyleImageReview } from '@/components/review/LifestyleImageReview'

// Add to props interface
interface SkuReviewClientProps {
  sku: string
  content: ContentRecord[]
  images: ImageRecord[]
  approval: ApprovalRecord | null
  variants: VariantIndex[]
  variantApprovals: VariantApproval[]
  // NEW: Product image data
  productImage: {
    mainImageUrl: string | null
    additionalImages: string[]
    shopifyProductUrl: string | null
  } | null
}

export function SkuReviewClient({
  sku,
  content,
  images,
  approval,
  variants,
  variantApprovals,
  productImage, // NEW
}: SkuReviewClientProps) {
  // ... existing state ...

  // NEW: Image approval handlers
  async function handleImageSelect(imageId: string) {
    await fetch('/api/review/images/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageId, masterSku: sku, finish: selectedFinish }),
    })
    // Refresh data
  }

  async function handleImageApprovalChange(
    imageId: string,
    status: 'approved' | 'rejected',
    reason?: string
  ) {
    await fetch('/api/review/images/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageId, status, reason }),
    })
    // Refresh data
  }

  return (
    <div className="p-8">
      {/* Header */}
      {/* ... existing header code ... */}

      {/* NEW: Product Hero Image - prominently displayed */}
      {productImage && (
        <div className="mb-6">
          <ProductHeroImage
            mainImageUrl={productImage.mainImageUrl}
            additionalImages={productImage.additionalImages}
            productTitle={`SKU ${sku}`}
            finish={selectedFinish}
            shopifyProductUrl={productImage.shopifyProductUrl}
          />
        </div>
      )}

      {/* Variant Selector */}
      {/* ... existing variant selector ... */}

      {/* Platform Tabs */}
      {/* ... existing platform tabs ... */}

      {/* UPDATED: Lifestyle Images Section */}
      <Separator className="my-8" />
      <LifestyleImageReview
        sku={sku}
        images={images}
        variants={variants.map(v => ({ finish: v.finish, finish_code: v.finish_code }))}
        selectedFinish={selectedFinish}
        onImageSelect={handleImageSelect}
        onApprovalChange={handleImageApprovalChange}
      />

      {/* Approval Status */}
      {/* ... existing approval status ... */}

      {/* Variant Approval Grid */}
      {/* ... existing variant approval grid ... */}
    </div>
  )
}
```

### Part 5: Page Data Fetching Update

```typescript
// dashboard/src/app/(dashboard)/review/[sku]/page.tsx (updated)

export default async function SkuReviewPage({ params }: { params: { sku: string } }) {
  const supabase = await createClient()
  const { sku } = params

  // ... existing queries ...

  // NEW: Fetch product image data
  const { data: productData } = await supabase
    .from('product_catalog')
    .select('main_image_url, additional_images, shopify_product_id')
    .eq('master_sku', sku)
    .single()

  // Build Shopify product URL if we have the ID
  const shopifyProductUrl = productData?.shopify_product_id
    ? `https://admin.shopify.com/store/allied-brass/products/${productData.shopify_product_id}`
    : null

  // NEW: Fetch enhanced image data with approval status
  const { data: images } = await supabase
    .from('generated_images')
    .select('*, approval_status, finish, finish_code')
    .eq('master_sku', sku)
    .order('variation_index')

  return (
    <SkuReviewClient
      sku={sku}
      content={content || []}
      images={images || []}
      approval={approval}
      variants={variants || []}
      variantApprovals={variantApprovals || []}
      productImage={productData ? {
        mainImageUrl: productData.main_image_url,
        additionalImages: productData.additional_images || [],
        shopifyProductUrl,
      } : null}
    />
  )
}
```

## API Endpoints

### Image Approval API

```typescript
// dashboard/src/app/api/review/images/approve/route.ts

import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const { imageId, status, reason } = await request.json()

  const supabase = createAdminClient()

  const { error } = await supabase
    .from('generated_images')
    .update({
      approval_status: status,
      rejection_reason: status === 'rejected' ? reason : null,
      approved_at: status === 'approved' ? new Date().toISOString() : null,
    })
    .eq('id', imageId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ success: true })
}
```

### Image Selection API

```typescript
// dashboard/src/app/api/review/images/select/route.ts

import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const { imageId, masterSku, finish } = await request.json()

  const supabase = createAdminClient()

  // Clear previous selection for this SKU/finish
  await supabase
    .from('generated_images')
    .update({ selected: false })
    .eq('master_sku', masterSku)
    .eq('finish', finish || null)

  // Set new selection
  const { error } = await supabase
    .from('generated_images')
    .update({ selected: true })
    .eq('id', imageId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  // Also record in lifestyle_image_selections for audit
  await supabase
    .from('lifestyle_image_selections')
    .upsert({
      master_sku: masterSku,
      finish: finish || null,
      selected_image_id: imageId,
      selected_at: new Date().toISOString(),
    })

  return NextResponse.json({ success: true })
}
```

## Success Criteria

### Product Hero Image
1. [ ] Product image displayed prominently at top of review page
2. [ ] Multiple images navigable with arrows
3. [ ] Click to zoom/enlarge
4. [ ] Finish badge shown when variant selected
5. [ ] Link to Shopify admin for product

### Lifestyle Image Approval
1. [ ] Clear separation of master SKU vs variant images
2. [ ] Approval status badges (pending/approved/rejected)
3. [ ] Approve/reject buttons with optional reason
4. [ ] Select for publishing functionality
5. [ ] Empty state with generate action
6. [ ] Coverage summary (X finishes with images, Y need images)
7. [ ] Quick overview grid showing all finishes

### Integration
1. [ ] Variant selector affects which images are shown
2. [ ] Approval actions work at correct level (master vs variant)
3. [ ] Image selection persists and connects to publishing workflow
4. [ ] Image approval status reflects in variant approval grid

## Testing Checklist

Use Playwright MCP to verify:

1. [ ] Navigate to `/review/1051`
2. [ ] Verify product hero image displays
3. [ ] Click through multiple product images
4. [ ] Click image to zoom/enlarge
5. [ ] Navigate to Lifestyle Images section
6. [ ] Switch between "Master SKU Images" and "Variant Images" tabs
7. [ ] Select a finish from variant selector
8. [ ] Verify images update for selected finish
9. [ ] Approve an image
10. [ ] Reject an image with reason
11. [ ] Select an image for publishing
12. [ ] Verify approval status updates

## Related Prompts

- **Prompt 16**: Multi-Variant Images - generates the lifestyle images
- **Prompt 19**: Fix Description Generation Quality - needs product image context
- **Prompt 17**: Description Quality Analyzer - validates content quality
