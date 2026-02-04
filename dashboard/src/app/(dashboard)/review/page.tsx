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

interface SkuWithContent {
  master_sku: string
  approval_status: string | null
  title_approved: boolean | null
  description_approved: boolean | null
  image_approved: boolean | null
  content_count: number
  avg_quality_score: number | null
}

async function getSkusWithContent(): Promise<SkuWithContent[]> {
  const supabase = await createClient()
  
  // Get all unique SKUs from generated_content with aggregated data
  const { data: contentSkus, error: contentError } = await supabase
    .from('generated_content')
    .select('master_sku, quality_score')
  
  if (contentError) {
    console.error('Error fetching content:', contentError)
    return []
  }
  
  // Get all approvals
  const { data: approvals, error: approvalsError } = await supabase
    .from('sku_approvals')
    .select('*')
  
  if (approvalsError) {
    console.error('Error fetching approvals:', approvalsError)
  }
  
  // Aggregate by SKU
  const skuMap = new Map<string, { scores: number[], count: number }>()
  
  for (const content of contentSkus || []) {
    const existing = skuMap.get(content.master_sku) || { scores: [], count: 0 }
    existing.count++
    if (content.quality_score) {
      existing.scores.push(content.quality_score)
    }
    skuMap.set(content.master_sku, existing)
  }
  
  // Build result
  const approvalMap = new Map((approvals || []).map(a => [a.master_sku, a]))
  
  const result: SkuWithContent[] = []
  for (const [sku, data] of skuMap) {
    const approval = approvalMap.get(sku)
    const avgScore = data.scores.length > 0 
      ? Math.round(data.scores.reduce((a, b) => a + b, 0) / data.scores.length)
      : null
    
    result.push({
      master_sku: sku,
      approval_status: approval?.approval_status || 'pending',
      title_approved: approval?.title_approved || null,
      description_approved: approval?.description_approved || null,
      image_approved: approval?.image_approved || null,
      content_count: data.count,
      avg_quality_score: avgScore,
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

export default async function ReviewPage() {
  const skus = await getSkusWithContent()
  
  const pendingSkus = skus.filter(s => s.approval_status === 'pending')
  const approvedSkus = skus.filter(s => s.approval_status === 'approved')
  const revisionSkus = skus.filter(s => s.approval_status === 'revision')
  
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Review Queue</h1>
        <p className="text-muted-foreground">
          Review and approve generated content for {skus.length} product SKUs
        </p>
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
