'use client'

import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, ChevronDown, ChevronRight, Code2, Loader2, AlertTriangle, CheckCircle2, Info } from "lucide-react"
import Link from "next/link"
import { PlatformBadge } from "@/components/shared/PlatformBadge"
import { QualityScore } from "@/components/shared/QualityScore"
import { ApprovalActions } from "@/components/review/ApprovalActions"
import { RegenerateButton } from "@/components/review/RegenerateButton"
import { RegenerationHistory } from "@/components/review/RegenerationHistory"
import { ProductHeroImage } from "@/components/review/ProductHeroImage"
import { LifestyleImageReview } from "@/components/review/LifestyleImageReview"
import { SearchInsightsCard } from "@/components/review/SearchInsightsCard"
import { PerformanceCard } from "@/components/review/PerformanceCard"
import { ContentQualityCard } from "@/components/review/ContentQualityCard"
import { VariantContentGrid } from "@/components/review/VariantContentGrid"
import { PublishButton } from "@/components/review/PublishButton"
import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { RegenerationHistory as RegenerationHistoryType, VariantIndex, VariantApproval } from "@/lib/supabase/types"

interface ContentRecord {
  id: string
  master_sku: string
  platform: string
  content_type: string
  baseline_content: string | null
  candidate_content: string | null
  quality_score: number | null
  generation_model: string | null
  created_at: string
}

interface ImageRecord {
  id: string
  master_sku: string
  variation_index: number
  image_url: string | null
  thumbnail_url: string | null
  prompt: string | null
  score: number | null
  ai_selected: boolean
  user_selected: boolean
  use_for_master: boolean
  approval_status: 'pending' | 'approved' | 'rejected'
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  finish: string | null
  finish_code: string | null
  gmc_pushed_at: string | null
  gmc_offer_id: string | null
  created_at: string
}

interface ProductImageData {
  mainImageUrl: string | null
  additionalImages: (string | null)[]
  shopifyProductUrl: string | null
  variantImages: Record<string, { mainImageUrl: string | null; additionalImages: (string | null)[] }>
}

interface CurrentContentByPlatform {
  [platform: string]: { title: string | null; description: string | null }
}

interface ApprovalRecord {
  master_sku: string
  approval_status: string
  title_approved: boolean | number | null
  description_approved: boolean | number | null
  image_approved: boolean | number | null
  notes: string | null
}

interface SkuReviewClientProps {
  sku: string
  content: ContentRecord[]
  images: ImageRecord[]
  approval: ApprovalRecord | null
  variants: VariantIndex[]
  variantApprovals: VariantApproval[]
  productImages: ProductImageData | null
  currentContentByPlatform: CurrentContentByPlatform
  variantCurrentContent: Record<string, { title: string | null; description: string | null }>
  finishSentences?: {
    google: Record<string, string> | null
    bing: Record<string, string> | null
  }
}

function getContentByPlatform(content: ContentRecord[], platform: string) {
  const platformContent = content.filter(c => c.platform === platform)
  return {
    title: platformContent.find(c => c.content_type === 'title'),
    description: platformContent.find(c => c.content_type === 'description'),
  }
}

// Simplified content display - vertical stacking, no side-by-side comparison
function ContentBlock({
  label,
  current,
  candidate,
  score,
  sku,
  type,
  platform,
  isTemplate,
}: {
  label: string
  current: string | null
  candidate: string | null
  score: number | null
  sku: string
  type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  isTemplate: boolean
}) {
  const [showHistory, setShowHistory] = useState(false)

  return (
    <div className="border-l-4 border-blue-500 pl-4 space-y-3">
      {/* Header with score and actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">{label}</h3>
          {score !== null && <QualityScore score={score} />}
          {isTemplate && (
            <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-300">
              Template
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RegenerateButton
            sku={sku}
            contentType={type}
            platform={platform}
            currentContent={candidate}
          />
        </div>
      </div>

      {/* New content (prominent) */}
      <div>
        <div className="text-xs font-semibold text-green-700 dark:text-green-400 mb-1 uppercase tracking-wide">
          New Content {candidate && `(${candidate.length} chars)`}
        </div>
        <div className="p-4 rounded-lg bg-green-50 border-2 border-green-200 dark:bg-green-900/20 dark:border-green-700 text-sm leading-relaxed whitespace-pre-wrap">
          {candidate || <span className="text-muted-foreground italic">No candidate content</span>}
        </div>
      </div>

      {/* Current content (reference) */}
      {current && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            Compare with current ({current.length} chars)
          </summary>
          <div className="mt-2 p-3 rounded bg-muted/50 text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {current}
          </div>
        </details>
      )}

      {/* Regeneration history */}
      <details open={showHistory}>
        <summary
          className="cursor-pointer text-sm text-muted-foreground hover:text-foreground flex items-center gap-2"
          onClick={(e) => { e.preventDefault(); setShowHistory(!showHistory); }}
        >
          {showHistory ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <span>History & prompt</span>
        </summary>
        {showHistory && (
          <div className="mt-2 space-y-2">
            <RegenerationHistory
              sku={sku}
              contentType={type}
              platform={platform}
            />
          </div>
        )}
      </details>
    </div>
  )
}

// Status banner at top showing approval readiness
function ApprovalStatusBanner({ approval, titleScore, descScore }: {
  approval: ApprovalRecord | null
  titleScore: number | null
  descScore: number | null
}) {
  const isApproved = approval?.approval_status === 'approved'
  const hasPoorQuality = (titleScore !== null && titleScore < 70) || (descScore !== null && descScore < 70)

  if (isApproved) {
    return (
      <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
        <CheckCircle2 className="h-5 w-5 text-green-600" />
        <span className="font-medium text-green-900 dark:text-green-100">Approved and ready to publish</span>
      </div>
    )
  }

  if (hasPoorQuality) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
        <AlertTriangle className="h-5 w-5 text-red-600" />
        <span className="font-medium text-red-900 dark:text-red-100">Quality score below 70% - needs revision</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
      <Info className="h-5 w-5 text-blue-600" />
      <span className="font-medium text-blue-900 dark:text-blue-100">Pending review</span>
    </div>
  )
}

// Badge showing which pipeline generated the content
function GenerationSourceBadge({
  generationModel
}: {
  generationModel: string | null
}) {
  if (!generationModel) return null

  const isAgentPipeline = generationModel.includes('6-agent-pipeline')

  return (
    <span className={`
      inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
      ${isAgentPipeline
        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
        : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      }
    `}>
      {isAgentPipeline ? (
        <>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-3a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v3h-3zM4.75 12.094A5.973 5.973 0 004 15v3H1v-3a3 3 0 013.75-2.906z"/>
          </svg>
          6-Agent Pipeline
        </>
      ) : (
        <>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/>
          </svg>
          Cloud Run
        </>
      )}
    </span>
  )
}

export function SkuReviewClient({
  sku,
  content,
  images,
  approval,
  variants,
  variantApprovals,
  productImages,
  currentContentByPlatform,
  variantCurrentContent,
  finishSentences,
}: SkuReviewClientProps) {
  const router = useRouter()
  const [selectedPlatform, setSelectedPlatform] = useState<'google' | 'bing' | 'shopify'>('google')

  const masterSku = content[0]?.master_sku || sku
  const hasGoogleContent = content.some(c => c.platform === 'google')
  const hasBingContent = content.some(c => c.platform === 'bing')
  const hasShopifyContent = content.some(c => c.platform === 'shopify')

  const { title, description } = getContentByPlatform(content, selectedPlatform)
  const currentContent = currentContentByPlatform[selectedPlatform]

  const titleIsTemplate = title?.candidate_content?.includes('{FINISH_NAME}') || false
  const descIsTemplate = description?.candidate_content?.includes('{FINISH_NAME}') || false

  return (
    <div className="min-h-screen bg-background">
      {/* Simplified header */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.back()}
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold">{masterSku}</h1>
                  <GenerationSourceBadge generationModel={
                    content.find(c => c.content_type === 'title')?.generation_model ?? null
                  } />
                </div>
                <p className="text-sm text-muted-foreground">Content Review</p>
              </div>
            </div>
            <PublishButton sku={masterSku} approvalStatus={approval?.approval_status || 'pending'} />
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 max-w-5xl">
        {/* Status banner */}
        <ApprovalStatusBanner
          approval={approval}
          titleScore={title?.quality_score || null}
          descScore={description?.quality_score || null}
        />

        {/* Platform tabs */}
        <Tabs value={selectedPlatform} onValueChange={(v) => setSelectedPlatform(v as any)} className="mt-6">
          <TabsList>
            {hasGoogleContent && <TabsTrigger value="google"><PlatformBadge platform="google" /></TabsTrigger>}
            {hasBingContent && <TabsTrigger value="bing"><PlatformBadge platform="bing" /></TabsTrigger>}
            {hasShopifyContent && <TabsTrigger value="shopify"><PlatformBadge platform="shopify" /></TabsTrigger>}
          </TabsList>

          {/* Content */}
          <TabsContent value={selectedPlatform} className="mt-6 space-y-6">
            {/* Row 1: Hero Image + Quality Metrics */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {productImages && (
                <ProductHeroImage
                  mainImageUrl={productImages.mainImageUrl}
                  additionalImages={productImages.additionalImages}
                  productTitle={masterSku}
                  shopifyProductUrl={productImages.shopifyProductUrl}
                />
              )}

              <ContentQualityCard
                title={title?.candidate_content || ''}
                description={description?.candidate_content || ''}
                platform={selectedPlatform}
                masterSku={masterSku}
              />
            </div>

            {/* Row 2: Search Insights + Performance */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SearchInsightsCard
                masterSku={masterSku}
                currentTitle={title?.candidate_content ?? undefined}
                currentDescription={description?.candidate_content ?? undefined}
              />

              <PerformanceCard sku={masterSku} platform={selectedPlatform} />
            </div>

            {/* Content blocks - vertical layout */}
            <div className="space-y-6">
              {title && (
                <ContentBlock
                  label="Title"
                  current={currentContent?.title || null}
                  candidate={title.candidate_content}
                  score={title.quality_score}
                  sku={masterSku}
                  type="title"
                  platform={selectedPlatform}
                  isTemplate={titleIsTemplate}
                />
              )}

              {description && (
                <ContentBlock
                  label="Description"
                  current={currentContent?.description || null}
                  candidate={description.candidate_content}
                  score={description.quality_score}
                  sku={masterSku}
                  type="description"
                  platform={selectedPlatform}
                  isTemplate={descIsTemplate}
                />
              )}
            </div>

            {/* Approval actions */}
            <div className="flex items-center justify-between border-t pt-6">
              <div className="text-sm text-muted-foreground">
                Review content quality and approve when ready
              </div>
              <ApprovalActions sku={masterSku} finish={null} type="title" />
            </div>

            {/* Variant content */}
            {variants && variants.length > 0 && (selectedPlatform === 'google' || selectedPlatform === 'bing') && (
              <details className="mt-8">
                <summary className="cursor-pointer text-lg font-semibold mb-4">
                  Variant Content ({variants.length} finishes)
                </summary>
                <VariantContentGrid
                  sku={masterSku}
                  platform={selectedPlatform}
                  baseTitle={title?.candidate_content || null}
                  baseDescription={description?.candidate_content || null}
                  variants={variants.filter(v => v.option_sku && v.finish && v.finish_code).map(v => ({ option_sku: v.option_sku!, finish: v.finish!, finish_code: v.finish_code! }))}
                  variantApprovals={variantApprovals}
                  variantCurrentContent={variantCurrentContent}
                  finishSentences={finishSentences?.[selectedPlatform] || null}
                  onApprovalChange={() => router.refresh()}
                />
              </details>
            )}

            {/* Lifestyle Images - expanded by default */}
            <section className="mt-8">
              <h3 className="text-lg font-semibold mb-4">Lifestyle Images</h3>
              <LifestyleImageReview
                sku={masterSku}
                images={images}
                variants={variants.filter(v => v.finish && v.finish_code).map(v => ({ finish: v.finish!, finish_code: v.finish_code! }))}
                selectedFinish={null}
                onRefresh={() => router.refresh()}
              />
            </section>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
