import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Plus, Play, RotateCcw, Eye } from "lucide-react"
import Link from "next/link"

// Placeholder data - will be fetched from Supabase
const batches = [
  {
    id: "batch-001",
    name: "Pilot Batch 1",
    status: "completed",
    skuCount: 1,
    successCount: 1,
    failedCount: 0,
    createdAt: "2026-02-03",
    executedAt: "2026-02-03",
  },
  {
    id: "batch-002",
    name: "Pilot Batch 2",
    status: "draft",
    skuCount: 5,
    successCount: 0,
    failedCount: 0,
    createdAt: "2026-02-03",
    executedAt: null,
  },
]

const statusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  ready: "bg-blue-100 text-blue-800",
  executing: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
}

export default function BatchesPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Batch Management</h1>
          <p className="text-muted-foreground">
            Create and manage publish batches
          </p>
        </div>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Create Batch
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Batches</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{batches.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Draft</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {batches.filter(b => b.status === 'draft').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {batches.filter(b => b.status === 'completed').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">SKUs Published</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {batches.reduce((acc, b) => acc + b.successCount, 0)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Batches Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Batches</CardTitle>
          <CardDescription>
            View and manage your publish batches
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Batch Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>SKUs</TableHead>
                <TableHead>Success</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Executed</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batches.map((batch) => (
                <TableRow key={batch.id}>
                  <TableCell className="font-medium">{batch.name}</TableCell>
                  <TableCell>
                    <Badge className={statusColors[batch.status]}>
                      {batch.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{batch.skuCount}</TableCell>
                  <TableCell className="text-green-600">{batch.successCount}</TableCell>
                  <TableCell className="text-red-600">{batch.failedCount}</TableCell>
                  <TableCell>{batch.createdAt}</TableCell>
                  <TableCell>{batch.executedAt || '-'}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Link href={`/batches/${batch.id}`}>
                        <Button variant="outline" size="sm">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </Link>
                      {batch.status === 'draft' && (
                        <Button size="sm">
                          <Play className="h-4 w-4 mr-1" />
                          Publish
                        </Button>
                      )}
                      {batch.status === 'completed' && (
                        <Button variant="outline" size="sm" className="text-yellow-600">
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
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
