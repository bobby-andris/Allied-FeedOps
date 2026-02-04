'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { PlatformBadge } from "@/components/shared/PlatformBadge"
import { QualityScore } from "@/components/shared/QualityScore"
import { ApprovalActions } from "@/components/review/ApprovalActions"
import { ImageGallery } from "@/components/review/ImageGallery"
import { VariantSelector } from "@/components/review/VariantSelector"
import { VariantApprovalGrid } from "@/components/review/VariantApprovalGrid"
import { RegenerateButton } from "@/components/review/RegenerateButton"
import { RegenerationHistory } from "@/components/review/RegenerationHistory"
import { VariantIndex, VariantApproval } from "@/lib/supabase/types"

interface ContentRecord {
  id: string
  master_sku: string
  platform: string
  content_type: string
  baseline_content: string | null
  candidate_content: string | null
  quality_score: number | null
  created_at: string
}

interface ImageRecord {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  score: number | null
  selected: boolean
}

interface ApprovalRecord {
  master_sku: string
  approval_status: string
  title_approved: boolean | null
  description_approved: boolean | null
  image_approved: boolean | null
  notes: string | null
}

interface SkuReviewClientProps {
  sku: string
  content: ContentRecord[]
  images: ImageRecord[]
  approval: ApprovalRecord | null
  variants: VariantIndex[]
  variantApprovals: VariantApproval[]
}

function getContentByPlatform(content: ContentRecord[], platform: string) {
  const platformContent = content.filter(c => c.platform === platform)
  return {
    title: platformContent.find(c => c.content_type === 'title'),
    description: platformContent.find(c => c.content_type === 'description'),
  }
}

function ContentComparison({ 
  label, 
  baseline, 
  candidate, 
  score,
  sku,
  finish,
  type,
  platform
}: { 
  label: string
  baseline: string | null
  candidate: string | null
  score: number | null
  sku: string
  finish: string | null
  type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle>{label}</CardTitle>
            {score !== null && <QualityScore score={score} size="sm" />}
          </div>
          <div className="flex items-center gap-2">
            <RegenerateButton
              sku={sku}
              contentType={type}
              platform={platform}
              currentContent={candidate}
            />
            <ApprovalActions sku={sku} finish={finish} type={type} size="sm" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-medium text-muted-foreground mb-2">Baseline</div>
            <div className="p-4 rounded-lg bg-muted/50 border whitespace-pre-wrap min-h-[100px]">
              {baseline || <span className="text-muted-foreground italic">No baseline content</span>}
            </div>
            {baseline && (
              <div className="text-xs text-muted-foreground mt-2">
                {baseline.length} characters
              </div>
            )}
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground mb-2">Candidate</div>
            <div className="p-4 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800 whitespace-pre-wrap min-h-[100px]">
              {candidate || <span className="text-muted-foreground italic">No candidate content</span>}
            </div>
            {candidate && (
              <div className="text-xs text-muted-foreground mt-2">
                {candidate.length} characters
              </div>
            )}
          </div>
        </div>
        
        {/* Regeneration History */}
        <div className="mt-4 pt-4 border-t">
          <RegenerationHistory
            sku={sku}
            contentType={type}
            platform={platform}
          />
        </div>
      </CardContent>
    </Card>
  )
}

function PlatformContent({ 
  platform, 
  content,
  sku,
  finish
}: { 
  platform: string
  content: ContentRecord[]
  sku: string
  finish: string | null
}) {
  const { title, description } = getContentByPlatform(content, platform)
  
  if (!title && !description) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          No {platform} content found for this SKU
        </CardContent>
      </Card>
    )
  }
  
  return (
    <div className="space-y-6">
      {title && (
        <ContentComparison
          label="Title"
          baseline={title.baseline_content}
          candidate={title.candidate_content}
          score={title.quality_score}
          sku={sku}
          finish={finish}
          type="title"
          platform={platform as 'google' | 'bing' | 'shopify'}
        />
      )}
      {description && (
        <ContentComparison
          label="Description"
          baseline={description.baseline_content}
          candidate={description.candidate_content}
          score={description.quality_score}
          sku={sku}
          finish={finish}
          type="description"
          platform={platform as 'google' | 'bing' | 'shopify'}
        />
      )}
    </div>
  )
}

export function SkuReviewClient({
  sku,
  content,
  images,
  approval,
  variants,
  variantApprovals,
}: SkuReviewClientProps) {
  const [selectedFinish, setSelectedFinish] = useState<string | null>(null)
  
  // Get unique platforms and calculate overall score
  const platforms = [...new Set(content.map(c => c.platform))]
  const scores = content.filter(c => c.quality_score !== null).map(c => c.quality_score!)
  const avgScore = scores.length > 0 
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) 
    : null

  // Get the current approval based on selected finish
  const currentApproval = selectedFinish
    ? variantApprovals.find(va => va.finish === selectedFinish)
    : approval

  // Get current approval status for display
  const currentStatus = currentApproval?.approval_status || 'pending'

  // Determine if we should show variant selector
  const hasVariants = variants.length > 0

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          href="/review" 
          className="flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Review Queue
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              SKU {sku}
              <Badge variant={currentStatus === 'approved' ? 'default' : 'secondary'}>
                {currentStatus}
              </Badge>
              {selectedFinish && (
                <Badge variant="outline" className="font-normal">
                  {selectedFinish}
                </Badge>
              )}
            </h1>
            <p className="text-muted-foreground">
              {content.length} content items across {platforms.length} platform(s)
              {hasVariants && ` | ${variants.length} variants`}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {avgScore !== null && <QualityScore score={avgScore} size="lg" />}
            <ApprovalActions sku={sku} finish={selectedFinish} type="all" />
          </div>
        </div>
      </div>

      {/* Variant Selector */}
      {hasVariants && (
        <div className="mb-6">
          <VariantSelector
            variants={variants}
            variantApprovals={variantApprovals}
            masterApprovalStatus={approval?.approval_status}
            selectedFinish={selectedFinish}
            onSelect={setSelectedFinish}
          />
        </div>
      )}

      {/* Platform Tabs */}
      <Tabs defaultValue={platforms[0] || 'google'} className="space-y-6">
        <TabsList>
          {platforms.includes('google') && (
            <TabsTrigger value="google">
              <PlatformBadge platform="google" className="mr-2" />
              Google
            </TabsTrigger>
          )}
          {platforms.includes('bing') && (
            <TabsTrigger value="bing">
              <PlatformBadge platform="bing" className="mr-2" />
              Bing
            </TabsTrigger>
          )}
          {platforms.includes('shopify') && (
            <TabsTrigger value="shopify">
              <PlatformBadge platform="shopify" className="mr-2" />
              Shopify
            </TabsTrigger>
          )}
        </TabsList>

        {platforms.includes('google') && (
          <TabsContent value="google" className="space-y-6">
            <PlatformContent platform="google" content={content} sku={sku} finish={selectedFinish} />
          </TabsContent>
        )}

        {platforms.includes('bing') && (
          <TabsContent value="bing" className="space-y-6">
            <PlatformContent platform="bing" content={content} sku={sku} finish={selectedFinish} />
          </TabsContent>
        )}

        {platforms.includes('shopify') && (
          <TabsContent value="shopify" className="space-y-6">
            <PlatformContent platform="shopify" content={content} sku={sku} finish={selectedFinish} />
          </TabsContent>
        )}
      </Tabs>

      {/* Lifestyle Images Section */}
      {images && images.length > 0 && (
        <>
          <Separator className="my-8" />
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Lifestyle Images</CardTitle>
                  <CardDescription>
                    {images.length} image variation(s) available - Click to enlarge and select
                  </CardDescription>
                </div>
                <ApprovalActions sku={sku} finish={selectedFinish} type="image" size="sm" />
              </div>
            </CardHeader>
            <CardContent>
              <ImageGallery images={images} sku={sku} />
            </CardContent>
          </Card>
        </>
      )}

      {/* Approval Status */}
      {currentApproval && (
        <>
          <Separator className="my-8" />
          <Card>
            <CardHeader>
              <CardTitle>
                Approval Status
                {selectedFinish && (
                  <span className="font-normal text-muted-foreground ml-2">
                    ({selectedFinish})
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Title:</span>
                  {(currentApproval.title_approved === true || currentApproval.title_approved === 1) && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {(currentApproval.title_approved === false || currentApproval.title_approved === 0) && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {currentApproval.title_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Description:</span>
                  {(currentApproval.description_approved === true || currentApproval.description_approved === 1) && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {(currentApproval.description_approved === false || currentApproval.description_approved === 0) && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {currentApproval.description_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Image:</span>
                  {(currentApproval.image_approved === true || currentApproval.image_approved === 1) && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {(currentApproval.image_approved === false || currentApproval.image_approved === 0) && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {currentApproval.image_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
              </div>
              {currentApproval.notes && (
                <div className="mt-4 p-4 bg-muted rounded-lg">
                  <div className="text-sm font-medium mb-1">Notes</div>
                  <p className="text-sm text-muted-foreground">{currentApproval.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Variant Approval Grid */}
      {hasVariants && (
        <>
          <Separator className="my-8" />
          <VariantApprovalGrid
            sku={sku}
            variants={variants}
            variantApprovals={variantApprovals}
            masterApproval={approval}
            onVariantSelect={setSelectedFinish}
          />
        </>
      )}
    </div>
  )
}
