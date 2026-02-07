'use client'

import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, ChevronDown, ChevronRight, Code2, Loader2, Sparkles, TrendingUp, Activity } from "lucide-react"
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
        <Button variant="ghost" size="sm" className="gap-2 w-full justify-start hover:bg-zinc-100/50 dark:hover:bg-zinc-800/50 transition-colors">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Code2 className="h-4 w-4" />
          <span className="text-sm font-medium">Prompt used</span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3">
        <Card className="border-zinc-200/60 dark:border-zinc-700/60 bg-gradient-to-br from-zinc-50/50 to-zinc-100/30 dark:from-zinc-900/50 dark:to-zinc-800/30">
          <CardHeader className="py-4 px-5">
            <CardTitle className="text-sm font-semibold tracking-tight">Generation Prompt</CardTitle>
          </CardHeader>
          <CardContent className="py-0 pb-5 px-5 space-y-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
              </div>
            ) : !matchingEntry ? (
              <p className="text-sm text-zinc-500 dark:text-zinc-400 py-3 italic">
                No stored prompt found for this content yet. Regenerate once to capture it.
              </p>
            ) : (
              <>
                <div className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                  {matchingEntry.model_version ? `Model: ${matchingEntry.model_version}` : null}
                  {matchingEntry.prompt_hash ? ` • Hash: ${matchingEntry.prompt_hash.slice(0, 10)}…` : null}
                </div>
                <div>
                  <div className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 mb-2 uppercase tracking-wide">System prompt</div>
                  <pre className="text-xs whitespace-pre-wrap rounded-lg border border-zinc-200/60 dark:border-zinc-700/60 bg-white/60 dark:bg-zinc-900/60 p-4 max-h-64 overflow-auto font-mono leading-relaxed">
                    {matchingEntry.system_prompt || '—'}
                  </pre>
                </div>
                <div>
                  <div className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 mb-2 uppercase tracking-wide">User prompt</div>
                  <pre className="text-xs whitespace-pre-wrap rounded-lg border border-zinc-200/60 dark:border-zinc-700/60 bg-white/60 dark:bg-zinc-900/60 p-4 max-h-64 overflow-auto font-mono leading-relaxed">
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
  const { preview: candidatePreview, isTemplate } = previewWithSampleFinish(candidate)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setIsVisible(true)
  }, [])

  return (
    <Card className={`border-zinc-200/60 dark:border-zinc-700/60 overflow-hidden transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
      <CardHeader className="bg-gradient-to-r from-zinc-50/80 via-white/50 to-zinc-50/80 dark:from-zinc-900/80 dark:via-zinc-900/50 dark:to-zinc-900/80 border-b border-zinc-200/60 dark:border-zinc-700/60">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-xl font-serif tracking-tight">{label}</CardTitle>
            {score !== null && <QualityScore score={score} size="sm" />}
            {isTemplate && (
              <Badge variant="outline" className="bg-violet-50 text-violet-700 border-violet-300/60 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-700/60 font-medium">
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
          <CardDescription className="text-xs mt-2 text-zinc-600 dark:text-zinc-400">
            Preview shows &quot;Polished Chrome&quot; as sample finish. Actual finish name will be substituted for each variant.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="p-6">
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wide">{liveLabel}</div>
              {currentLive && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                  {currentLive.length} chars
                </div>
              )}
            </div>
            <div className="p-5 rounded-xl bg-zinc-100/60 border border-zinc-200/60 dark:bg-zinc-800/60 dark:border-zinc-700/60 whitespace-pre-wrap break-words leading-relaxed shadow-sm overflow-auto">
              {currentLive || <span className="text-zinc-400 dark:text-zinc-500 italic">No current content found</span>}
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
                Candidate {isTemplate && <span className="text-violet-600 dark:text-violet-400 normal-case">(Preview)</span>}
              </div>
              {candidate && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                  {candidate.length} chars{isTemplate && ' (tmpl)'}
                </div>
              )}
            </div>
            <div className="p-5 rounded-xl bg-gradient-to-br from-emerald-50/80 to-teal-50/60 border border-emerald-200/60 dark:from-emerald-900/20 dark:to-teal-900/20 dark:border-emerald-700/60 whitespace-pre-wrap break-words leading-relaxed shadow-sm overflow-auto">
              {candidatePreview || <span className="text-zinc-400 dark:text-zinc-500 italic">No candidate content</span>}
            </div>
          </div>
        </div>

        <div className="mt-6 pt-6 border-t border-zinc-200/60 dark:border-zinc-700/60">
          <PromptUsed
            sku={sku}
            contentType={type}
            platform={platform}
            currentCandidate={candidate}
          />
        </div>

        <div className="mt-4 pt-4 border-t border-zinc-200/60 dark:border-zinc-700/60">
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
}: {
  platform: string
  content: ContentRecord[]
  sku: string
  finish: string | null
  currentContent: { title: string | null; description: string | null } | undefined
  liveLabel: string
}) {
  const { title, description } = getContentByPlatform(content, platform)

  if (!title && !description) {
    return (
      <Card className="border-zinc-200/60 dark:border-zinc-700/60">
        <CardContent className="p-12 text-center text-zinc-400 dark:text-zinc-500">
          <p className="text-sm italic">No {platform} content found for this SKU</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-8">
      <div className="space-y-8">
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

      {/* Insights sidebar */}
      <aside className="space-y-6">
        <div className="lg:sticky lg:top-6 space-y-6">
          <Card className="border-zinc-200/60 dark:border-zinc-700/60 bg-gradient-to-br from-blue-50/40 via-indigo-50/30 to-violet-50/40 dark:from-blue-950/20 dark:via-indigo-950/20 dark:to-violet-950/20 overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                Search Insights
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-auto max-h-[600px]">
              <SearchInsightsCard
                masterSku={sku}
                currentTitle={title?.candidate_content ?? undefined}
                currentDescription={description?.candidate_content ?? undefined}
              />
            </CardContent>
          </Card>

          <Card className="border-zinc-200/60 dark:border-zinc-700/60 bg-gradient-to-br from-emerald-50/40 via-teal-50/30 to-cyan-50/40 dark:from-emerald-950/20 dark:via-teal-950/20 dark:to-cyan-950/20 overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                Performance
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-auto max-h-[600px]">
              <PerformanceCard sku={sku} platform={platform as 'google' | 'bing' | 'shopify'} />
            </CardContent>
          </Card>

          <Card className="border-zinc-200/60 dark:border-zinc-700/60 bg-gradient-to-br from-amber-50/40 via-orange-50/30 to-rose-50/40 dark:from-amber-950/20 dark:via-orange-950/20 dark:to-rose-950/20 overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Activity className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                Content Quality
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-auto max-h-[600px]">
              <ContentQualityCard
                title={title?.candidate_content || ''}
                description={description?.candidate_content || ''}
                platform={platform as 'google' | 'bing' | 'shopify'}
                masterSku={sku}
              />
            </CardContent>
          </Card>
        </div>
      </aside>
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
}: SkuReviewClientProps) {
  const router = useRouter()
  const [selectedPlatform, setSelectedPlatform] = useState<'google' | 'bing' | 'shopify'>('google')
  const [selectedFinish, setSelectedFinish] = useState<string | null>(null)

  const masterSku = content[0]?.master_sku || sku
  const hasGoogleContent = content.some(c => c.platform === 'google')
  const hasBingContent = content.some(c => c.platform === 'bing')
  const hasShopifyContent = content.some(c => c.platform === 'shopify')

  const liveLabel = selectedPlatform === 'shopify' ? 'Current (Shopify)' : 'Previous generation'

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 via-white to-zinc-100/50 dark:from-zinc-950 dark:via-zinc-900 dark:to-zinc-950/50">
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&display=swap');

        .font-serif {
          font-family: 'Crimson Pro', Georgia, serif;
        }

        @keyframes grain {
          0%, 100% { transform: translate(0, 0); }
          10% { transform: translate(-5%, -10%); }
          20% { transform: translate(-15%, 5%); }
          30% { transform: translate(7%, -25%); }
          40% { transform: translate(-5%, 25%); }
          50% { transform: translate(-15%, 10%); }
          60% { transform: translate(15%, 0%); }
          70% { transform: translate(0%, 15%); }
          80% { transform: translate(3%, 35%); }
          90% { transform: translate(-10%, 10%); }
        }

        .grain::before {
          content: '';
          position: fixed;
          top: -50%;
          left: -50%;
          right: -50%;
          bottom: -50%;
          width: 200%;
          height: 200%;
          background: url('data:image/svg+xml;utf8,<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><filter id="noise"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="4" stitchTiles="stitch"/></filter><rect width="100%" height="100%" filter="url(%23noise)" opacity="0.05"/></svg>');
          animation: grain 8s steps(10) infinite;
          pointer-events: none;
          z-index: 1;
        }
      `}</style>

      <div className="grain" />

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-zinc-200/60 dark:border-zinc-700/60 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-xl supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-zinc-900/60">
        <div className="container mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.back()}
                className="gap-2 hover:bg-zinc-100/60 dark:hover:bg-zinc-800/60"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Back</span>
              </Button>
              <div>
                <h1 className="text-3xl font-serif font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                  {masterSku}
                </h1>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">Content Review & Optimization</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <PublishButton sku={masterSku} approvalStatus={approval?.approval_status || 'pending'} />
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8 relative z-10">
        {/* Product images section */}
        {productImages && (
          <section className="mb-10">
            <div className="grid grid-cols-2 gap-8">
              <ProductHeroImage
                mainImageUrl={productImages.mainImageUrl}
                additionalImages={productImages.additionalImages}
                productTitle={masterSku}
                shopifyProductUrl={productImages.shopifyProductUrl}
              />
              <LifestyleImageReview
                sku={masterSku}
                images={images}
                variants={variants.filter(v => v.finish && v.finish_code).map(v => ({ finish: v.finish!, finish_code: v.finish_code! }))}
                selectedFinish={selectedFinish}
                onRefresh={() => router.refresh()}
              />
            </div>
          </section>
        )}

        {/* Platform content tabs */}
        <section className="mb-10">
          <Tabs value={selectedPlatform} onValueChange={(v) => setSelectedPlatform(v as 'google' | 'bing' | 'shopify')} className="w-full">
            <TabsList className="bg-zinc-100/60 dark:bg-zinc-800/60 border border-zinc-200/60 dark:border-zinc-700/60 p-1.5">
              {hasGoogleContent && (
                <TabsTrigger value="google" className="data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-900 data-[state=active]:shadow-sm transition-all">
                  <PlatformBadge platform="google" className="text-sm" />
                </TabsTrigger>
              )}
              {hasBingContent && (
                <TabsTrigger value="bing" className="data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-900 data-[state=active]:shadow-sm transition-all">
                  <PlatformBadge platform="bing" className="text-sm" />
                </TabsTrigger>
              )}
              {hasShopifyContent && (
                <TabsTrigger value="shopify" className="data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-900 data-[state=active]:shadow-sm transition-all">
                  <PlatformBadge platform="shopify" className="text-sm" />
                </TabsTrigger>
              )}
            </TabsList>

            {hasGoogleContent && (
              <TabsContent value="google" className="mt-8">
                <PlatformContent
                  platform="google"
                  content={content}
                  sku={masterSku}
                  finish={selectedFinish}
                  currentContent={currentContentByPlatform['google']}
                  liveLabel={liveLabel}
                />
              </TabsContent>
            )}
            {hasBingContent && (
              <TabsContent value="bing" className="mt-8">
                <PlatformContent
                  platform="bing"
                  content={content}
                  sku={masterSku}
                  finish={selectedFinish}
                  currentContent={currentContentByPlatform['bing']}
                  liveLabel={liveLabel}
                />
              </TabsContent>
            )}
            {hasShopifyContent && (
              <TabsContent value="shopify" className="mt-8">
                <PlatformContent
                  platform="shopify"
                  content={content}
                  sku={masterSku}
                  finish={selectedFinish}
                  currentContent={currentContentByPlatform['shopify']}
                  liveLabel={liveLabel}
                />
              </TabsContent>
            )}
          </Tabs>
        </section>

        {/* Variant content section - only for Google and Bing */}
        {variants && variants.length > 0 && (selectedPlatform === 'google' || selectedPlatform === 'bing') && (
          <section className="mb-10">
            <Card className="border-zinc-200/60 dark:border-zinc-700/60 overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-zinc-50/80 via-white/50 to-zinc-50/80 dark:from-zinc-900/80 dark:via-zinc-900/50 dark:to-zinc-900/80 border-b border-zinc-200/60 dark:border-zinc-700/60">
                <CardTitle className="text-2xl font-serif font-bold tracking-tight">Variant Content</CardTitle>
                <CardDescription className="text-sm text-zinc-600 dark:text-zinc-400">
                  Review and approve content for all {variants.length} product finishes
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6">
                <VariantContentGrid
                  sku={masterSku}
                  platform={selectedPlatform}
                  baseTitle={getContentByPlatform(content, selectedPlatform).title?.candidate_content || null}
                  baseDescription={getContentByPlatform(content, selectedPlatform).description?.candidate_content || null}
                  variants={variants.filter(v => v.option_sku && v.finish && v.finish_code).map(v => ({ option_sku: v.option_sku!, finish: v.finish!, finish_code: v.finish_code! }))}
                  variantApprovals={variantApprovals}
                  variantCurrentContent={variantCurrentContent}
                  finishSentences={finishSentences?.[selectedPlatform] || null}
                  onApprovalChange={() => router.refresh()}
                />
              </CardContent>
            </Card>
          </section>
        )}
      </main>
    </div>
  )
}
