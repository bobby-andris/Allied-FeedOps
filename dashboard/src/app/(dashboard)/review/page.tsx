import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Search, Filter } from "lucide-react"
import Link from "next/link"
import { createClient } from "@/lib/supabase/server"
import { skuToUrlPath } from "@/lib/sku-utils"
import { BatchRegenerateButton } from "@/components/review/BatchRegenerateButton"
import {
  buildPlatformProgress,
  computePlatformReadinessForSku,
  latestProductionPublishSnapshots,
  type PlatformProgress,
} from "@/lib/review/platform-progress"

interface SkuWithContent {
  master_sku: string
  approval_status: string | null
  title_approved: boolean | null
  description_approved: boolean | null
  image_approved: boolean | null
  content_count: number
  avg_quality_score: number | null
  platform_progress: PlatformProgress[]
}

interface GeneratedContentRow {
  master_sku: string
  quality_score: number | null
  platform: string | null
  content_type: string | null
  approved_content: string | null
}

interface VariantRow {
  master_sku: string
  finish: string | null
}

interface VariantApprovalRow {
  master_sku: string
  finish: string | null
  approval_status: string | null
  title_approved: boolean | number | string | null
  description_approved: boolean | number | string | null
}

interface VariantImageRow {
  master_sku: string
  finish: string | null
  approval_status: string | null
  user_selected: boolean | null
}

interface PublishEventRow {
  master_sku: string
  platform: string | null
  published_at: string | null
  published_title: string | null
  published_description: string | null
  content_version: number | null
}

async function getSkusWithContent(): Promise<SkuWithContent[]> {
  const supabase = await createClient()
  
  // Get generated content including per-platform approval snapshots.
  const { data: contentSkus, error: contentError } = await supabase
    .from('generated_content')
    .select('master_sku, quality_score, platform, content_type, approved_content')
  
  if (contentError) {
    console.error('Error fetching content:', contentError)
    return []
  }

  const skuList = [...new Set((contentSkus || []).map((row) => row.master_sku).filter(Boolean))]
  if (skuList.length === 0) {
    return []
  }
  
  // Get master-level approval rows.
  const { data: approvals, error: approvalsError } = await supabase
    .from('sku_approvals')
    .select('*')
    .in('master_sku', skuList)
  
  if (approvalsError) {
    console.error('Error fetching approvals:', approvalsError)
  }

  // Get variant readiness dependencies.
  const { data: variants, error: variantsError } = await supabase
    .from('variant_index')
    .select('master_sku, finish')
    .in('master_sku', skuList)

  if (variantsError) {
    console.error('Error fetching variants:', variantsError)
  }

  const { data: variantApprovals, error: variantApprovalsError } = await supabase
    .from('variant_approvals')
    .select('master_sku, finish, approval_status, title_approved, description_approved')
    .in('master_sku', skuList)

  if (variantApprovalsError) {
    console.error('Error fetching variant approvals:', variantApprovalsError)
  }

  const { data: variantImages, error: variantImagesError } = await supabase
    .from('variant_lifestyle_images')
    .select('master_sku, finish, approval_status, user_selected')
    .in('master_sku', skuList)

  if (variantImagesError) {
    console.error('Error fetching variant images:', variantImagesError)
  }

  // Get latest successful production publish snapshots.
  const { data: publishEvents, error: publishEventsError } = await supabase
    .from('publish_events')
    .select('master_sku, platform, published_at, published_title, published_description, content_version')
    .in('master_sku', skuList)
    .eq('action', 'publish')
    .eq('status', 'success')
    .eq('environment', 'production')
    .order('published_at', { ascending: false })

  if (publishEventsError) {
    console.error('Error fetching publish events:', publishEventsError)
  }
  
  const contentBySku = new Map<string, GeneratedContentRow[]>()
  const variantsBySku = new Map<string, VariantRow[]>()
  const variantApprovalsBySku = new Map<string, VariantApprovalRow[]>()
  const variantImagesBySku = new Map<string, VariantImageRow[]>()
  const publishEventsBySku = new Map<string, PublishEventRow[]>()

  for (const row of contentSkus || []) {
    const bucket = contentBySku.get(row.master_sku) || []
    bucket.push(row)
    contentBySku.set(row.master_sku, bucket)
  }

  for (const row of variants || []) {
    const bucket = variantsBySku.get(row.master_sku) || []
    bucket.push(row)
    variantsBySku.set(row.master_sku, bucket)
  }

  for (const row of variantApprovals || []) {
    const bucket = variantApprovalsBySku.get(row.master_sku) || []
    bucket.push(row)
    variantApprovalsBySku.set(row.master_sku, bucket)
  }

  for (const row of variantImages || []) {
    const bucket = variantImagesBySku.get(row.master_sku) || []
    bucket.push(row)
    variantImagesBySku.set(row.master_sku, bucket)
  }

  for (const row of publishEvents || []) {
    const bucket = publishEventsBySku.get(row.master_sku) || []
    bucket.push(row)
    publishEventsBySku.set(row.master_sku, bucket)
  }
  
  // Build result
  const approvalMap = new Map((approvals || []).map(a => [a.master_sku, a]))
  
  const result: SkuWithContent[] = []
  for (const [sku, skuContent] of contentBySku) {
    const approval = approvalMap.get(sku)
    const scores = skuContent
      .map((row) => row.quality_score)
      .filter((score): score is number => typeof score === 'number')
    const avgScore = scores.length > 0
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : null

    const readiness = computePlatformReadinessForSku({
      contentRecords: skuContent,
      variants: variantsBySku.get(sku) || [],
      variantApprovals: variantApprovalsBySku.get(sku) || [],
      variantImages: variantImagesBySku.get(sku) || [],
    })
    const publishSnapshots = latestProductionPublishSnapshots(publishEventsBySku.get(sku) || [])
    
    result.push({
      master_sku: sku,
      approval_status: approval?.approval_status || 'pending',
      title_approved: approval?.title_approved || null,
      description_approved: approval?.description_approved || null,
      image_approved: approval?.image_approved || null,
      content_count: skuContent.length,
      avg_quality_score: avgScore,
      platform_progress: buildPlatformProgress(readiness, publishSnapshots),
    })
  }
  
  // Sort by SKU
  result.sort((a, b) => a.master_sku.localeCompare(b.master_sku))
  
  return result
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'approved':
      return <Badge className="bg-green-100 text-green-800">Approved</Badge>
    case 'rejected':
      return <Badge className="bg-red-100 text-red-800">Rejected</Badge>
    case 'revision':
      return <Badge className="bg-yellow-100 text-yellow-800">Revision</Badge>
    default:
      return <Badge variant="secondary">Pending</Badge>
  }
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

function formatPublishTimestamp(timestamp: string | null): string | null {
  if (!timestamp) return null
  try {
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(timestamp))
  } catch {
    return null
  }
}

function getPlatformLabel(platform: PlatformProgress['platform']): string {
  if (platform === 'google') return 'Google'
  if (platform === 'bing') return 'Bing'
  return 'Shopify'
}

function PlatformProgressRow({ progress }: { progress: PlatformProgress[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {progress.map((item) => {
        const publishedDate = formatPublishTimestamp(item.publishedSnapshot?.publishedAt ?? null)
        const labelPrefix = getPlatformLabel(item.platform)
        const label = item.state === 'published'
          ? `${labelPrefix}: Published${publishedDate ? ` (${publishedDate})` : ''}`
          : item.state === 'ready'
            ? `${labelPrefix}: Ready`
            : `${labelPrefix}: Needs action`

        const className = item.state === 'published'
          ? 'bg-green-100 text-green-800'
          : item.state === 'ready'
            ? 'bg-blue-100 text-blue-800'
            : 'bg-gray-100 text-gray-700'

        return (
          <Badge key={`${item.platform}-${item.state}`} className={className} title={item.blockerSummary || undefined}>
            {label}
          </Badge>
        )
      })}
    </div>
  )
}

export default async function ReviewPage() {
  const skus = await getSkusWithContent()
  
  const pendingSkus = skus.filter(s => s.approval_status === 'pending')
  const approvedSkus = skus.filter(s => s.approval_status === 'approved')
  const revisionSkus = skus.filter(s => s.approval_status === 'revision')
  
  return (
    <div className="p-8">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Review Queue</h1>
          <p className="text-muted-foreground">
            Review and approve generated content for {skus.length} product SKUs
          </p>
        </div>
        <BatchRegenerateButton totalSkus={skus.length} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search SKUs..." className="pl-9" />
        </div>
        
        <Select defaultValue="all">
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="revision">Needs Revision</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
        
        <Button variant="outline" size="icon">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {/* Status Tabs */}
      <Tabs defaultValue="pending" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pending">
            Pending <Badge variant="secondary" className="ml-2">{pendingSkus.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="approved">
            Approved <Badge variant="secondary" className="ml-2">{approvedSkus.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="revision">
            Revision <Badge variant="secondary" className="ml-2">{revisionSkus.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="all">All ({skus.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="space-y-4">
          {pendingSkus.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No SKUs pending review
              </CardContent>
            </Card>
          ) : (
            pendingSkus.map((sku) => (
              <Card key={sku.master_sku} className="hover:bg-muted/50 transition-colors">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        SKU {sku.master_sku}
                        <Badge variant="outline">{sku.content_count} items</Badge>
                      </CardTitle>
                      <CardDescription>
                        {sku.title_approved === null && sku.description_approved === null 
                          ? 'Not yet reviewed' 
                          : `Title: ${sku.title_approved ? '✓' : '○'} | Desc: ${sku.description_approved ? '✓' : '○'} | Image: ${sku.image_approved ? '✓' : '○'}`
                        }
                      </CardDescription>
                      <PlatformProgressRow progress={sku.platform_progress} />
                    </div>
                    <div className="flex items-center gap-4">
                      {sku.avg_quality_score !== null && (
                        <div className="text-right">
                          <div className="text-sm text-muted-foreground">Quality Score</div>
                          <div className={`text-2xl font-bold ${getScoreColor(sku.avg_quality_score)}`}>
                            {sku.avg_quality_score}
                          </div>
                        </div>
                      )}
                      <Link href={`/review/${skuToUrlPath(sku.master_sku)}`}>
                        <Button>Review</Button>
                      </Link>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="approved" className="space-y-4">
          {approvedSkus.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No approved SKUs yet
              </CardContent>
            </Card>
          ) : (
            approvedSkus.map((sku) => (
              <Card key={sku.master_sku}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        SKU {sku.master_sku}
                        {getStatusBadge(sku.approval_status || 'pending')}
                      </CardTitle>
                      <CardDescription>{sku.content_count} content items</CardDescription>
                      <PlatformProgressRow progress={sku.platform_progress} />
                    </div>
                    <Link href={`/review/${skuToUrlPath(sku.master_sku)}`}>
                      <Button variant="outline">View Details</Button>
                    </Link>
                  </div>
                </CardHeader>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="revision" className="space-y-4">
          {revisionSkus.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No SKUs need revision
              </CardContent>
            </Card>
          ) : (
            revisionSkus.map((sku) => (
              <Card key={sku.master_sku}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        SKU {sku.master_sku}
                        {getStatusBadge('revision')}
                      </CardTitle>
                      <CardDescription>{sku.content_count} content items</CardDescription>
                      <PlatformProgressRow progress={sku.platform_progress} />
                    </div>
                    <Link href={`/review/${skuToUrlPath(sku.master_sku)}`}>
                      <Button>Review</Button>
                    </Link>
                  </div>
                </CardHeader>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="all" className="space-y-4">
          {skus.map((sku) => (
            <Card key={sku.master_sku}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      SKU {sku.master_sku}
                      {getStatusBadge(sku.approval_status || 'pending')}
                    </CardTitle>
                    <CardDescription>{sku.content_count} content items</CardDescription>
                    <PlatformProgressRow progress={sku.platform_progress} />
                  </div>
                  <div className="flex items-center gap-4">
                    {sku.avg_quality_score !== null && (
                      <div className={`text-xl font-bold ${getScoreColor(sku.avg_quality_score)}`}>
                        {sku.avg_quality_score}
                      </div>
                    )}
                    <Link href={`/review/${skuToUrlPath(sku.master_sku)}`}>
                      <Button variant={sku.approval_status === 'approved' ? 'outline' : 'default'}>
                        {sku.approval_status === 'approved' ? 'View' : 'Review'}
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  )
}
