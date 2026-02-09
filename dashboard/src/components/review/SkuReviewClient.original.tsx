'use client'

import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, ChevronDown, ChevronRight, Code2, Loader2 } from "lucide-react"
import Link from "next/link"
import { PlatformBadge } from "@/components/shared/PlatformBadge"
import { QualityScore } from "@/components/shared/QualityScore"
import { ApprovalActions } from "@/components/review/ApprovalActions"
import { VariantSelector } from "@/components/review/VariantSelector"
import { VariantApprovalGrid } from "@/components/review/VariantApprovalGrid"
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
  // Selection tracking
  ai_selected: boolean
  user_selected: boolean
  use_for_master: boolean
  // Approval tracking
  approval_status: 'pending' | 'approved' | 'rejected'
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  // Variant association
  finish: string | null
  finish_code: string | null
  // GMC tracking
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

// Per-platform "current" content
// - Shopify: from product_catalog (what's actually live on Shopify)
// - Google/Bing: from baseline_content (previous generation)
interface CurrentContentByPlatform {
  [platform: string]: { title: string | null; description: string | null }
}

interface ApprovalRecord {
  master_sku: string
  approval_status: string
  // Can be boolean (newer DB) or 0/1 (older codepaths)
  title_approved: boolean | number | null
  description_approved: boolean | number | null
  image_approved: boolean | number | null
  notes: string | null
}

function PromptUsed({
  sku,
  contentType,
  platform,
  currentCandidate,
}: {
  sku: string
  contentType: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  currentCandidate: string | null
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<RegenerationHistoryType[]>([])

  const matchingEntry = useMemo(() => {
    if (history.length === 0) return null
    if (currentCandidate) {
      const match = history.find(h => h.new_content === currentCandidate)
      if (match) return match
    }
    return history[0]
  }, [history, currentCandidate])

  useEffect(() => {
    if (!isOpen) return
    ;(async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams({
          sku,
          content_type: contentType,
          platform,
          limit: '20',
        })
        const res = await fetch(`/api/regenerate/history?${params}`)
        const data = await res.json()
        if (!res.ok) throw new Error(data?.error || 'Failed to load prompt')
        setHistory(data?.history || [])
      } catch {
        setHistory([])
      } finally {
        setLoading(false)
      }
    })()
  }, [isOpen, sku, contentType, platform])

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 w-full justify-start">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Code2 className="h-4 w-4" />
          Prompt used
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Generation Prompt</CardTitle>
          </CardHeader>
          <CardContent className="py-0 pb-4 space-y-3">
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : !matchingEntry ? (
              <p className="text-sm text-muted-foreground py-2">
                No stored prompt found for this content yet. Regenerate once to capture it.
              </p>
            ) : (
              <>
                <div className="text-xs text-muted-foreground">
                  {matchingEntry.model_version ? `Model: ${matchingEntry.model_version}` : null}
                  {matchingEntry.prompt_hash ? ` • Hash: ${matchingEntry.prompt_hash.slice(0, 10)}…` : null}
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">System prompt</div>
                  <pre className="text-xs whitespace-pre-wrap rounded-lg border bg-muted/40 p-3 max-h-64 overflow-auto">
                    {matchingEntry.system_prompt || '—'}
                  </pre>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">User prompt</div>
                  <pre className="text-xs whitespace-pre-wrap rounded-lg border bg-muted/40 p-3 max-h-64 overflow-auto">
                    {matchingEntry.user_prompt || '—'}
                  </pre>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface PerformanceBaseline {
  master_sku: string
  platform: string
  avg_impressions: number | null
  avg_clicks: number | null
  avg_ctr: number | null
  avg_conversions: number | null
  avg_cvr: number | null
  avg_conversion_value: number | null
  baseline_start_date: string
  baseline_end_date: string
  created_at: string
}

interface PerformanceSnapshot {
  id: string
  master_sku: string
  platform: string
  snapshot_date: string
  impressions: number | null
  clicks: number | null
  ctr: number | null
  conversions: number | null
  cvr: number | null
  conversion_value: number | null
  days_since_publish: number | null
  fetched_at: string
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
  /** Product+finish tailored sentences for Google and Bing */
  finishSentences?: {
    google: Record<string, string> | null
    bing: Record<string, string> | null
  }
  performanceBaselines: PerformanceBaseline[]
  performanceSnapshots: PerformanceSnapshot[]
}

function getContentByPlatform(content: ContentRecord[], platform: string) {
  const platformContent = content.filter(c => c.platform === platform)
  return {
    title: platformContent.find(c => c.content_type === 'title'),
    description: platformContent.find(c => c.content_type === 'description'),
  }
}

/**
 * Preview content by substituting placeholders with sample values.
 * - {FINISH_NAME} → "Polished Chrome"
 * - {FINISH_SENTENCE} → sample finish sentence
 * Returns both the preview text and whether the content is a template.
 */
function previewWithSampleFinish(content: string | null): { preview: string | null; isTemplate: boolean } {
  if (!content) return { preview: null, isTemplate: false }

  const hasFinishName = content.includes('{FINISH_NAME}')
  const hasFinishSentence = content.includes('{FINISH_SENTENCE}')
  const isTemplate = hasFinishName || hasFinishSentence

  if (isTemplate) {
    let preview = content
    if (hasFinishName) {
      preview = preview.replace(/\{FINISH_NAME\}/g, 'Polished Chrome')
    }
    if (hasFinishSentence) {
      // Use a sample sentence that describes how a finish relates to the product
      preview = preview.replace(/\{FINISH_SENTENCE\}/g, 'Polished Chrome offers timeless versatility with a bright, reflective surface that matches most fixtures.')
    }
    return { preview, isTemplate: true }
  }
  return { preview: content, isTemplate: false }
}

function ContentComparison({
  label,
  currentLive,
  liveLabel,
  candidate,
  score,
  sku,
  finish,
  type,
  platform
}: {
  label: string
  currentLive: string | null
  liveLabel: string
  candidate: string | null
  score: number | null
  sku: string
  finish: string | null
  type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
}) {
  // Preview candidate with sample finish substituted
  const { preview: candidatePreview, isTemplate } = previewWithSampleFinish(candidate)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle>{label}</CardTitle>
            {score !== null && <QualityScore score={score} size="sm" />}
            {isTemplate && (
              <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700">
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
            <ApprovalActions sku={sku} finish={finish} type={type} size="sm" />
          </div>
        </div>
        {isTemplate && (
          <CardDescription className="text-xs mt-1">
            Preview shows &quot;Polished Chrome&quot; as sample finish. Actual finish name will be substituted for each variant.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-medium text-muted-foreground mb-2">{liveLabel}</div>
            <div className="p-4 rounded-lg bg-muted/50 border whitespace-pre-wrap min-h-[100px]">
              {currentLive || <span className="text-muted-foreground italic">No current content found</span>}
            </div>
            {currentLive && (
              <div className="text-xs text-muted-foreground mt-2">
                {currentLive.length} characters
              </div>
            )}
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground mb-2">
              Candidate {isTemplate && <span className="text-purple-600 dark:text-purple-400">(Preview)</span>}
            </div>
            <div className="p-4 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800 whitespace-pre-wrap min-h-[100px]">
              {candidatePreview || <span className="text-muted-foreground italic">No candidate content</span>}
            </div>
            {candidate && (
              <div className="text-xs text-muted-foreground mt-2">
                {candidate.length} characters{isTemplate && ' (template)'}
              </div>
            )}
          </div>
        </div>

        {/* Prompt used */}
        <div className="mt-4 pt-4 border-t">
          <PromptUsed
            sku={sku}
            contentType={type}
            platform={platform}
            currentCandidate={candidate}
          />
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
  finish,
  currentContent,
  liveLabel,
  performanceBaselines,
  performanceSnapshots,
}: {
  platform: string
  content: ContentRecord[]
  sku: string
  finish: string | null
  currentContent: { title: string | null; description: string | null } | undefined
  liveLabel: string
  performanceBaselines: PerformanceBaseline[]
  performanceSnapshots: PerformanceSnapshot[]
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
    <div className="grid grid-cols-[1fr_320px] gap-6">
      {/* Left: Content comparison cards */}
      <div className="space-y-6">
        {title && (
          <ContentComparison
            label="Title"
            currentLive={currentContent?.title || null}
            liveLabel={liveLabel}
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
            currentLive={currentContent?.description || null}
            liveLabel={liveLabel}
            candidate={description.candidate_content}
            score={description.quality_score}
            sku={sku}
            finish={finish}
            type="description"
            platform={platform as 'google' | 'bing' | 'shopify'}
          />
        )}
      </div>

      {/* Right: Insight Cards sidebar */}
      <div className="sticky top-4 self-start space-y-4">
        <SearchInsightsCard
          masterSku={sku}
          currentTitle={title?.candidate_content ?? undefined}
          currentDescription={description?.candidate_content ?? undefined}
        />
        <PerformanceCard
          sku={sku}
          platform={platform as 'google' | 'bing' | 'shopify'}
          baselines={performanceBaselines}
          snapshots={performanceSnapshots}
        />
        <ContentQualityCard
          title={title?.candidate_content || ''}
          description={description?.candidate_content || ''}
          platform={platform as 'google' | 'bing' | 'shopify'}
          masterSku={sku}
        />
      </div>
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
  productImages,
  currentContentByPlatform,
  variantCurrentContent,
  finishSentences,
  performanceBaselines,
  performanceSnapshots,
}: SkuReviewClientProps) {
  const [selectedFinish, setSelectedFinish] = useState<string | null>(null)
  const router = useRouter()
  
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
            <PublishButton
              sku={sku}
              approvalStatus={currentStatus}
              hasGoogleContent={platforms.includes('google')}
              hasShopifyContent={platforms.includes('shopify')}
            />
          </div>
        </div>
      </div>

      {/* Product Hero Image */}
      {productImages && (
        <div className="mb-6">
          <ProductHeroImage
            mainImageUrl={
              selectedFinish && productImages.variantImages[selectedFinish]
                ? productImages.variantImages[selectedFinish].mainImageUrl
                : productImages.mainImageUrl
            }
            additionalImages={
              selectedFinish && productImages.variantImages[selectedFinish]
                ? productImages.variantImages[selectedFinish].additionalImages
                : productImages.additionalImages
            }
            productTitle={`SKU ${sku}`}
            finish={selectedFinish}
            shopifyProductUrl={productImages.shopifyProductUrl}
          />
        </div>
      )}

      {/* Variant Selector */}
      {hasVariants && (
        <div className="mb-6 pb-4 border-b">
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
      <Tabs defaultValue={platforms.includes('google') ? 'google' : platforms[0] || 'google'} className="space-y-6">
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
            <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <PlatformBadge platform="google" />
              <span className="font-medium">Google Shopping Content</span>
              <span className="text-sm text-muted-foreground ml-auto">
                Template uses &#123;FINISH_NAME&#125; for 28 variants
              </span>
            </div>
            <PlatformContent platform="google" content={content} sku={sku} finish={selectedFinish} currentContent={currentContentByPlatform['google']} liveLabel="Previous Version" performanceBaselines={performanceBaselines} performanceSnapshots={performanceSnapshots} />
            {/* All Variants Grid for Google */}
            {hasVariants && (
              <VariantContentGrid
                sku={sku}
                platform="google"
                baseTitle={getContentByPlatform(content, 'google').title?.candidate_content || null}
                baseDescription={getContentByPlatform(content, 'google').description?.candidate_content || null}
                variants={variants
                  .filter(v => v.finish && v.finish_code && v.option_sku)
                  .map(v => ({ option_sku: v.option_sku!, finish: v.finish!, finish_code: v.finish_code! }))}
                variantApprovals={variantApprovals}
                variantCurrentContent={variantCurrentContent}
                finishSentences={finishSentences?.google}
                onApprovalChange={() => router.refresh()}
              />
            )}
          </TabsContent>
        )}

        {platforms.includes('bing') && (
          <TabsContent value="bing" className="space-y-6">
            <div className="flex items-center gap-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
              <PlatformBadge platform="bing" />
              <span className="font-medium">Bing Shopping Content</span>
              <span className="text-sm text-muted-foreground ml-auto">
                Template uses &#123;FINISH_NAME&#125; for 28 variants
              </span>
            </div>
            <PlatformContent platform="bing" content={content} sku={sku} finish={selectedFinish} currentContent={currentContentByPlatform['bing']} liveLabel="Previous Version" performanceBaselines={performanceBaselines} performanceSnapshots={performanceSnapshots} />
            {/* All Variants Grid for Bing */}
            {hasVariants && (
              <VariantContentGrid
                sku={sku}
                platform="bing"
                baseTitle={getContentByPlatform(content, 'bing').title?.candidate_content || null}
                baseDescription={getContentByPlatform(content, 'bing').description?.candidate_content || null}
                variants={variants
                  .filter(v => v.finish && v.finish_code && v.option_sku)
                  .map(v => ({ option_sku: v.option_sku!, finish: v.finish!, finish_code: v.finish_code! }))}
                variantApprovals={variantApprovals}
                variantCurrentContent={variantCurrentContent}
                finishSentences={finishSentences?.bing}
                onApprovalChange={() => router.refresh()}
              />
            )}
          </TabsContent>
        )}

        {platforms.includes('shopify') && (
          <TabsContent value="shopify" className="space-y-6">
            <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
              <PlatformBadge platform="shopify" />
              <span className="font-medium">Shopify Product Page</span>
              <span className="text-sm text-muted-foreground ml-auto">
                No finish placeholder - content applies to all variants
              </span>
            </div>
            <PlatformContent platform="shopify" content={content} sku={sku} finish={selectedFinish} currentContent={currentContentByPlatform['shopify']} liveLabel="Current (Live)" performanceBaselines={performanceBaselines} performanceSnapshots={performanceSnapshots} />
          </TabsContent>
        )}
      </Tabs>

      {/* Lifestyle Images Section */}
      <Separator className="my-8" />
      <LifestyleImageReview
        sku={sku}
        images={images}
        variants={variants
          .filter(v => v.finish && v.finish_code)
          .map(v => ({ finish: v.finish!, finish_code: v.finish_code! }))}
        selectedFinish={selectedFinish}
        onRefresh={() => router.refresh()}
      />

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
