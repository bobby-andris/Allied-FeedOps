import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, Play, RotateCcw, Plus, Trash2 } from "lucide-react"
import Link from "next/link"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// Placeholder data
const batchData = {
  id: "batch-001",
  name: "Pilot Batch 1",
  status: "completed",
  notes: "First production publish of optimized content",
  createdAt: "2026-02-03",
  executedAt: "2026-02-03",
  skus: [
    { sku: "1051", name: "Paper Towel Holders", platforms: ["google", "shopify"], status: "success" },
  ],
}

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  ready: "bg-blue-100 text-blue-800",
  executing: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  success: "bg-green-100 text-green-800",
}

export default async function BatchDetailPage({
  params,
}: {
  params: Promise<{ batchId: string }>
}) {
  const { batchId } = await params

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          href="/batches" 
          className="flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Batches
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              {batchData.name}
              <Badge className={statusColors[batchData.status]}>
                {batchData.status}
              </Badge>
            </h1>
            <p className="text-muted-foreground">
              Batch ID: {batchId}
            </p>
          </div>
          <div className="flex gap-2">
            {batchData.status === 'draft' && (
              <>
                <Button variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Add SKUs
                </Button>
                <Button>
                  <Play className="h-4 w-4 mr-2" />
                  Publish to Staging
                </Button>
              </>
            )}
            {batchData.status === 'completed' && (
              <Button variant="outline" className="text-yellow-600">
                <RotateCcw className="h-4 w-4 mr-2" />
                Rollback
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Batch Info */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total SKUs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{batchData.skus.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Successful</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {batchData.skus.filter(s => s.status === 'success').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {batchData.skus.filter(s => s.status === 'failed').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Executed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {batchData.executedAt || 'Not yet'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      {batchData.notes && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{batchData.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* SKU List */}
      <Card>
        <CardHeader>
          <CardTitle>SKUs in Batch</CardTitle>
          <CardDescription>
            {batchData.skus.length} SKU(s) included in this batch
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Product Name</TableHead>
                <TableHead>Platforms</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batchData.skus.map((sku) => (
                <TableRow key={sku.sku}>
                  <TableCell className="font-medium">{sku.sku}</TableCell>
                  <TableCell>{sku.name}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {sku.platforms.map((platform) => (
                        <PlatformBadge 
                          key={platform} 
                          platform={platform as 'google' | 'bing' | 'shopify'} 
                        />
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge className={statusColors[sku.status]}>
                      {sku.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {batchData.status === 'draft' && (
                      <Button variant="ghost" size="sm" className="text-red-600">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                    {batchData.status === 'completed' && (
                      <Link href={`/performance?sku=${sku.sku}`}>
                        <Button variant="outline" size="sm">
                          View Performance
                        </Button>
                      </Link>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
