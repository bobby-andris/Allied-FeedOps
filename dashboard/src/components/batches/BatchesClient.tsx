'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Plus, Play, RotateCcw, Eye } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { PublishBatch } from '@/lib/supabase/types'
import { CreateBatchModal } from './CreateBatchModal'

interface BatchStats {
  totalBatches: number
  draftCount: number
  completedCount: number
  skusPublished: number
}

interface BatchesClientProps {
  batches: PublishBatch[]
  stats: BatchStats
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  ready: 'bg-blue-100 text-blue-800',
  executing: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

export function BatchesClient({ batches, stats }: BatchesClientProps) {
  const router = useRouter()
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const handlePublish = async (batchId: string) => {
    setActionLoading(batchId)
    try {
      const response = await fetch('/api/batches', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: batchId, status: 'executing' }),
      })
      if (response.ok) {
        router.refresh()
      }
    } finally {
      setActionLoading(null)
    }
  }

  const handleBatchCreated = () => {
    setCreateModalOpen(false)
    router.refresh()
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <>
      {/* Header with Create Button */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Batch Management</h1>
          <p className="text-muted-foreground">
            Create and manage publish batches
          </p>
        </div>
        <Button onClick={() => setCreateModalOpen(true)}>
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
            <div className="text-2xl font-bold">{stats.totalBatches}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Draft</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.draftCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.completedCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">SKUs Published</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.skusPublished}</div>
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
              {batches.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No batches yet. Create your first batch to get started.
                  </TableCell>
                </TableRow>
              ) : (
                batches.map((batch) => (
                  <TableRow key={batch.batch_id}>
                    <TableCell className="font-medium">{batch.name}</TableCell>
                    <TableCell>
                      <Badge className={statusColors[batch.status] || statusColors.draft}>
                        {batch.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{batch.sku_count}</TableCell>
                    <TableCell className="text-green-600">{batch.success_count}</TableCell>
                    <TableCell className="text-red-600">{batch.failed_count}</TableCell>
                    <TableCell>{formatDate(batch.created_at)}</TableCell>
                    <TableCell>{formatDate(batch.executed_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Link href={`/batches/${batch.batch_id}`}>
                          <Button variant="outline" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        {batch.status === 'draft' && (
                          <Button 
                            size="sm"
                            onClick={() => handlePublish(batch.batch_id)}
                            disabled={actionLoading === batch.batch_id}
                          >
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
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <CreateBatchModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onCreated={handleBatchCreated}
      />
    </>
  )
}
