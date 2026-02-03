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
import { createClient } from "@/lib/supabase/server"
import { notFound } from "next/navigation"

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

async function getSkuData(sku: string) {
  const supabase = await createClient()
  
  // Get content for all platforms
  const { data: content, error: contentError } = await supabase
    .from('generated_content')
    .select('*')
    .eq('master_sku', sku)
    .order('platform')
    .order('content_type')
  
  if (contentError) {
    console.error('Error fetching content:', contentError)
  }
  
  // Get images
  const { data: images, error: imagesError } = await supabase
    .from('generated_images')
    .select('*')
    .eq('master_sku', sku)
    .order('variation_index')
  
  if (imagesError) {
    console.error('Error fetching images:', imagesError)
  }
  
  // Get approval status
  const { data: approval, error: approvalError } = await supabase
    .from('sku_approvals')
    .select('*')
    .eq('master_sku', sku)
    .single()
  
  if (approvalError && approvalError.code !== 'PGRST116') {
    console.error('Error fetching approval:', approvalError)
  }
  
  return {
    content: (content || []) as ContentRecord[],
    images: (images || []) as ImageRecord[],
    approval: approval as ApprovalRecord | null,
  }
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
  type
}: { 
  label: string
  baseline: string | null
  candidate: string | null
  score: number | null
  sku: string
  type: 'title' | 'description'
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle>{label}</CardTitle>
            {score !== null && <QualityScore score={score} size="sm" />}
          </div>
          <ApprovalActions sku={sku} type={type} size="sm" />
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
      </CardContent>
    </Card>
  )
}

function PlatformContent({ 
  platform, 
  content,
  sku
}: { 
  platform: string
  content: ContentRecord[]
  sku: string
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
          type="title"
        />
      )}
      {description && (
        <ContentComparison
          label="Description"
          baseline={description.baseline_content}
          candidate={description.candidate_content}
          score={description.quality_score}
          sku={sku}
          type="description"
        />
      )}
    </div>
  )
}

export default async function SkuReviewPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = await params
  const { content, images, approval } = await getSkuData(sku)
  
  if (content.length === 0) {
    notFound()
  }
  
  // Get unique platforms and calculate overall score
  const platforms = [...new Set(content.map(c => c.platform))]
  const scores = content.filter(c => c.quality_score !== null).map(c => c.quality_score!)
  const avgScore = scores.length > 0 
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) 
    : null

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
              <Badge variant={approval?.approval_status === 'approved' ? 'default' : 'secondary'}>
                {approval?.approval_status || 'pending'}
              </Badge>
            </h1>
            <p className="text-muted-foreground">
              {content.length} content items across {platforms.length} platform(s)
            </p>
          </div>
          <div className="flex items-center gap-4">
            {avgScore !== null && <QualityScore score={avgScore} size="lg" />}
            <ApprovalActions sku={sku} type="all" />
          </div>
        </div>
      </div>

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
            <PlatformContent platform="google" content={content} sku={sku} />
          </TabsContent>
        )}

        {platforms.includes('bing') && (
          <TabsContent value="bing" className="space-y-6">
            <PlatformContent platform="bing" content={content} sku={sku} />
          </TabsContent>
        )}

        {platforms.includes('shopify') && (
          <TabsContent value="shopify" className="space-y-6">
            <PlatformContent platform="shopify" content={content} sku={sku} />
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
                <ApprovalActions sku={sku} type="image" size="sm" />
              </div>
            </CardHeader>
            <CardContent>
              <ImageGallery images={images} sku={sku} />
            </CardContent>
          </Card>
        </>
      )}

      {/* Approval Status */}
      {approval && (
        <>
          <Separator className="my-8" />
          <Card>
            <CardHeader>
              <CardTitle>Approval Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Title:</span>
                  {approval.title_approved === true && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {approval.title_approved === false && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {approval.title_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Description:</span>
                  {approval.description_approved === true && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {approval.description_approved === false && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {approval.description_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Image:</span>
                  {approval.image_approved === true && <Badge className="bg-green-100 text-green-800">Approved</Badge>}
                  {approval.image_approved === false && <Badge className="bg-red-100 text-red-800">Rejected</Badge>}
                  {approval.image_approved === null && <Badge variant="secondary">Pending</Badge>}
                </div>
              </div>
              {approval.notes && (
                <div className="mt-4 p-4 bg-muted rounded-lg">
                  <div className="text-sm font-medium mb-1">Notes</div>
                  <p className="text-sm text-muted-foreground">{approval.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
