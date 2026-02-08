'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ImageApprovalCard } from "@/components/review/ImageApprovalCard"
import { Check, Image as ImageIcon, RefreshCw, Sparkles, Upload, ExternalLink } from "lucide-react"
import { toast } from "sonner"

// Convert local file path to GitHub raw URL for archived images
function getImageUrl(imagePath: string | null): string | null {
  if (!imagePath) return null
  if (imagePath.startsWith('http')) return imagePath
  return `https://raw.githubusercontent.com/bobby-andris/Allied-FeedOps/archive/full-snapshot-2026-02-03/${imagePath}`
}

// Updated interface to match new database schema
interface LifestyleImage {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  prompt?: string | null
  score: number | null
  // Selection tracking
  ai_selected: boolean
  user_selected: boolean
  use_for_master: boolean
  // Approval tracking
  approval_status?: 'pending' | 'approved' | 'rejected' | string | null
  approved_by?: string | null
  approved_at?: string | null
  rejection_reason?: string | null
  // Variant association
  finish?: string | null
  finish_code?: string | null
  // GMC tracking
  gmc_pushed_at?: string | null
  gmc_offer_id?: string | null
  created_at?: string
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
  onRefresh: () => void
}

export function LifestyleImageReview({
  sku,
  images,
  variants,
  selectedFinish,
  onRefresh,
}: LifestyleImageReviewProps) {
  const [activeTab, setActiveTab] = useState<'variant' | 'master'>('variant')

  // All images are variant images (associated with a finish)
  // Master SKU images are variant images with use_for_master=true
  const variantImages = images.filter(img => img.finish)
  const masterImage = images.find(img => img.use_for_master && img.user_selected)

  // Group variant images by finish
  const imagesByFinish = variantImages.reduce((acc, img) => {
    const finish = img.finish || 'Unknown'
    if (!acc[finish]) acc[finish] = []
    acc[finish].push(img)
    return acc
  }, {} as Record<string, LifestyleImage[]>)

  // Get images for currently selected finish (default to first finish with images)
  const availableFinishes = Object.keys(imagesByFinish)
  const currentFinish = selectedFinish && imagesByFinish[selectedFinish]
    ? selectedFinish
    : availableFinishes[0] || null
  const currentFinishImages = currentFinish ? imagesByFinish[currentFinish] || [] : []

  // Count stats
  const pendingCount = variantImages.filter(i => i.approval_status === 'pending' || !i.approval_status).length
  const approvedCount = variantImages.filter(i => i.approval_status === 'approved').length
  const userSelectedCount = variantImages.filter(i => i.user_selected).length
  const pushedToGmcCount = variantImages.filter(i => i.gmc_pushed_at).length

  // API handlers
  const handleImageApprove = async (imageId: string, imageType: 'product' | 'variant') => {
    const response = await fetch('/api/review/images/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageId, status: 'approved', imageType }),
    })

    if (!response.ok) {
      throw new Error('Failed to approve image')
    }

    toast.success('Image approved')
    onRefresh()
  }

  const handleImageReject = async (imageId: string, imageType: 'product' | 'variant', reason?: string) => {
    const response = await fetch('/api/review/images/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageId, status: 'rejected', imageType, reason }),
    })

    if (!response.ok) {
      throw new Error('Failed to reject image')
    }

    toast.success('Image rejected')
    onRefresh()
  }

  const handleUserSelect = async (imageId: string, finish: string) => {
    const response = await fetch('/api/review/images/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        imageId,
        masterSku: sku,
        finish,
        userSelected: true,
      }),
    })

    if (!response.ok) {
      throw new Error('Failed to select image')
    }

    toast.success('Image selected for this variant')
    onRefresh()
  }

  const handleUseForMaster = async (imageId: string) => {
    const response = await fetch('/api/review/images/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        imageId,
        masterSku: sku,
        useForMaster: true,
      }),
    })

    if (!response.ok) {
      throw new Error('Failed to set as master image')
    }

    toast.success('Image will be used for Master SKU')
    onRefresh()
  }

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
              Review AI recommendations, approve, and select images for publishing
            </CardDescription>
          </div>

          {/* Summary stats */}
          <div className="flex gap-4 text-center">
            <div>
              <div className="text-2xl font-bold">{variantImages.length}</div>
              <div className="text-xs text-muted-foreground">Total</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">{approvedCount}</div>
              <div className="text-xs text-muted-foreground">Approved</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-600">{userSelectedCount}</div>
              <div className="text-xs text-muted-foreground">Selected</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-600">{pushedToGmcCount}</div>
              <div className="text-xs text-muted-foreground">In GMC</div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {images.length === 0 ? (
          <EmptyImageState sku={sku} />
        ) : (
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'variant' | 'master')}>
            <TabsList className="mb-4">
              <TabsTrigger value="variant" className="gap-2">
                Variant Images
                {pendingCount > 0 && (
                  <Badge variant="secondary" className="ml-1">{pendingCount} pending</Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="master" className="gap-2">
                Master SKU
                {masterImage ? (
                  <Badge variant="default" className="ml-1 bg-green-600">Set</Badge>
                ) : (
                  <Badge variant="secondary" className="ml-1">Not set</Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="variant">
              <VariantImageSection
                imagesByFinish={imagesByFinish}
                currentFinish={currentFinish}
                currentFinishImages={currentFinishImages}
                sku={sku}
                onApprove={handleImageApprove}
                onReject={handleImageReject}
                onUserSelect={handleUserSelect}
                onUseForMaster={handleUseForMaster}
              />
            </TabsContent>

            <TabsContent value="master">
              <MasterImageSection
                masterImage={masterImage}
                variantImages={variantImages}
                sku={sku}
                onUseForMaster={handleUseForMaster}
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
        Lifestyle images haven&apos;t been generated for SKU {sku} yet.
      </p>
      <Button variant="outline">
        <RefreshCw className="h-4 w-4 mr-2" />
        Generate Lifestyle Images
      </Button>
    </div>
  )
}

function VariantImageSection({
  imagesByFinish,
  currentFinish,
  currentFinishImages,
  sku,
  onApprove,
  onReject,
  onUserSelect,
  onUseForMaster,
}: {
  imagesByFinish: Record<string, LifestyleImage[]>
  currentFinish: string | null
  currentFinishImages: LifestyleImage[]
  sku: string
  onApprove: (imageId: string, imageType: 'product' | 'variant') => Promise<void>
  onReject: (imageId: string, imageType: 'product' | 'variant', reason?: string) => Promise<void>
  onUserSelect: (imageId: string, finish: string) => Promise<void>
  onUseForMaster: (imageId: string) => Promise<void>
}) {
  const finishesWithImages = Object.keys(imagesByFinish)

  // Find AI recommended and user selected for current finish
  const aiRecommended = currentFinishImages.find(i => i.ai_selected)
  const userSelected = currentFinishImages.find(i => i.user_selected)

  return (
    <div className="space-y-4">
      {/* Explanation */}
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-800">
        <p className="text-sm">
          <strong>Variant Images</strong> are used for Google Merchant Center feeds where each
          finish has its own listing. Review the AI recommendation, then select your preferred image.
        </p>
      </div>

      {/* Current finish display */}
      {currentFinish && (
        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
          <Badge variant="outline" className="text-base px-3 py-1">
            {currentFinish}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {currentFinishImages.length} image(s) generated
          </span>
          {userSelected?.gmc_pushed_at && (
            <Badge variant="default" className="bg-purple-600">
              <Upload className="h-3 w-3 mr-1" />
              In GMC
            </Badge>
          )}
        </div>
      )}

      {/* Status summary for current finish */}
      {currentFinish && currentFinishImages.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {/* AI Recommendation */}
          <div className={`p-4 rounded-lg border-2 ${aiRecommended ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20' : 'border-dashed border-muted'}`}>
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-yellow-600" />
              <span className="font-medium text-sm">AI Recommendation</span>
            </div>
            {aiRecommended ? (
              <p className="text-sm text-muted-foreground">
                Variation {aiRecommended.variation_index + 1}
                {aiRecommended.score && ` (Score: ${aiRecommended.score})`}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">No AI recommendation</p>
            )}
          </div>

          {/* User Selection */}
          <div className={`p-4 rounded-lg border-2 ${userSelected ? 'border-green-300 bg-green-50 dark:bg-green-900/20' : 'border-dashed border-muted'}`}>
            <div className="flex items-center gap-2 mb-2">
              <Check className="h-4 w-4 text-green-600" />
              <span className="font-medium text-sm">Your Selection</span>
            </div>
            {userSelected ? (
              <p className="text-sm text-muted-foreground">
                Variation {userSelected.variation_index + 1}
                {userSelected.approval_status === 'approved' && ' (Approved)'}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Select an approved image below</p>
            )}
          </div>
        </div>
      )}

      {/* Image grid */}
      {currentFinish && currentFinishImages.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {currentFinishImages.map((image) => (
            <ImageApprovalCard
              key={image.id}
              image={image}
              isAiSelected={image.ai_selected}
              isUserSelected={image.user_selected}
              isUseForMaster={image.use_for_master}
              gmcPushedAt={image.gmc_pushed_at}
              onApprove={() => onApprove(image.id, 'variant')}
              onReject={(reason) => onReject(image.id, 'variant', reason)}
              onUserSelect={() => onUserSelect(image.id, currentFinish)}
              onUseForMaster={() => onUseForMaster(image.id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 border-2 border-dashed rounded-lg">
          <p className="text-muted-foreground">
            {finishesWithImages.length > 0
              ? 'Select a finish to review its images'
              : 'No variant images generated yet'
            }
          </p>
        </div>
      )}

      {/* Other finishes quick view */}
      {finishesWithImages.length > 1 && (
        <div className="mt-6">
          <h4 className="font-medium text-sm mb-3">Other Finishes with Images</h4>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {finishesWithImages
              .filter(f => f !== currentFinish)
              .slice(0, 4)
              .map((finish) => {
                const finishImages = imagesByFinish[finish]
                const selected = finishImages.find(i => i.user_selected)
                const approved = finishImages.filter(i => i.approval_status === 'approved').length
                const firstImage = finishImages[0]

                return (
                  <div key={finish} className="border rounded-lg p-2 opacity-75 hover:opacity-100 transition-opacity">
                    {(firstImage?.thumbnail_url || firstImage?.image_url) && (
                      <div className="relative aspect-video mb-2">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={getImageUrl(firstImage.thumbnail_url) || getImageUrl(firstImage.image_url) || ''}
                          alt={finish}
                          className="w-full h-full object-cover rounded"
                        />
                        {selected && (
                          <div className="absolute top-1 right-1">
                            <Badge className="bg-green-600 text-xs">Selected</Badge>
                          </div>
                        )}
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium truncate">{finish}</span>
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

function MasterImageSection({
  masterImage,
  variantImages,
  sku,
  onUseForMaster,
}: {
  masterImage: LifestyleImage | undefined
  variantImages: LifestyleImage[]
  sku: string
  onUseForMaster: (imageId: string) => Promise<void>
}) {
  // Get approved images that could be used for master
  const approvedImages = variantImages.filter(i =>
    i.approval_status === 'approved' && i.user_selected
  )

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 dark:bg-blue-900/20 dark:border-blue-800">
        <p className="text-sm">
          <strong>Master SKU Image</strong> is used for Shopify product pages where all finishes
          share one page. Select an approved variant image to use as the master.
        </p>
      </div>

      {/* Current master image */}
      {masterImage ? (
        <div className="p-4 rounded-lg border-2 border-green-300 bg-green-50 dark:bg-green-900/20">
          <div className="flex items-center gap-2 mb-3">
            <Check className="h-5 w-5 text-green-600" />
            <span className="font-medium">Current Master SKU Image</span>
            <Badge variant="outline">{masterImage.finish}</Badge>
          </div>
          <div className="flex gap-4">
            {(masterImage.thumbnail_url || masterImage.image_url) && (
              <div className="w-48 aspect-video">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getImageUrl(masterImage.thumbnail_url) || getImageUrl(masterImage.image_url) || ''}
                  alt="Master SKU image"
                  className="w-full h-full object-cover rounded"
                />
              </div>
            )}
            <div className="flex-1">
              <p className="text-sm text-muted-foreground mb-2">
                Variation {masterImage.variation_index + 1} from {masterImage.finish}
              </p>
              <p className="text-sm text-muted-foreground">
                This image will be used on the Shopify product page for SKU {sku}.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-lg border-2 border-dashed border-muted">
          <div className="flex items-center gap-2 mb-2">
            <ImageIcon className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium text-muted-foreground">No Master Image Set</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Select an approved variant image below to use as the master SKU image.
          </p>
        </div>
      )}

      {/* Available images to choose from */}
      <div>
        <h4 className="font-medium text-sm mb-3">
          Available Images ({approvedImages.length} approved & selected)
        </h4>
        {approvedImages.length === 0 ? (
          <div className="text-center py-8 border-2 border-dashed rounded-lg">
            <p className="text-muted-foreground text-sm">
              No approved images available. Approve and select variant images first.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {approvedImages.map((image) => (
              <div
                key={image.id}
                className={`border rounded-lg p-3 ${image.use_for_master ? 'ring-2 ring-green-500' : ''}`}
              >
                {(image.thumbnail_url || image.image_url) && (
                  <div className="relative aspect-video mb-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={getImageUrl(image.thumbnail_url) || getImageUrl(image.image_url) || ''}
                      alt={`${image.finish} variation ${image.variation_index + 1}`}
                      className="w-full h-full object-cover rounded"
                    />
                    {image.use_for_master && (
                      <div className="absolute top-1 right-1">
                        <Badge className="bg-green-600">Master</Badge>
                      </div>
                    )}
                  </div>
                )}
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" className="text-xs">{image.finish}</Badge>
                  <span className="text-xs text-muted-foreground">
                    Var {image.variation_index + 1}
                  </span>
                </div>
                {!image.use_for_master && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => onUseForMaster(image.id)}
                  >
                    Use for Master SKU
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
