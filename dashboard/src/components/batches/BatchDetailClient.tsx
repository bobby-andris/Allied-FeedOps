'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ArrowLeft, Play, RotateCcw, Plus, Trash2, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { PublishBatch } from '@/lib/supabase/types'
import { AddSkuModal } from './AddSkuModal'

interface BatchSkuAssignment {
  id: string
  batch_id: string
  master_sku: string
  status: 'pending' | 'success' | 'partial' | 'failed' | null
  error_message: string | null
  created_at: string
}

interface BatchDetailClientProps {
  batch: PublishBatch
  assignments: BatchSkuAssignment[]
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  pending: 'bg-blue-100 text-blue-800',
  executing: 'bg-yellow-100 text-yellow-800',
  published: 'bg-green-100 text-green-800',
  partial: 'bg-amber-100 text-amber-800',
  failed: 'bg-red-100 text-red-800',
  success: 'bg-green-100 text-green-800',
}

export function BatchDetailClient({ batch, assignments }: BatchDetailClientProps) {
  const router = useRouter()
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [removingSkus, setRemovingSkus] = useState<string[]>([])

  const handlePublish = async () => {
    setActionLoading(true)
    try {
      const response = await fetch('/api/publish/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_id: batch.batch_id,
          platforms: ['google', 'shopify'],
          environment: 'production',
        }),
      })
      if (response.ok) {
        router.refresh()
      } else {
        const payload = await response.json().catch(() => ({}))
        const error = payload.error || 'Batch publish failed'
        const action = payload.actionable_message ? ` Next step: ${payload.actionable_message}` : ''
        alert(`${error}${action}`)
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleRemoveSku = async (masterSku: string) => {
    setRemovingSkus([...removingSkus, masterSku])
    try {
      const response = await fetch('/api/batches', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          batch_id: batch.batch_id, 
          remove_skus: [masterSku] 
        }),
      })
      if (response.ok) {
        router.refresh()
      }
    } finally {
      setRemovingSkus(removingSkus.filter(s => s !== masterSku))
    }
  }

  const handleSkusAdded = () => {
    setAddModalOpen(false)
    router.refresh()
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Not yet'
    return new Date(dateString).toLocaleDateString()
  }

  const successCount = assignments.filter(a => a.status === 'success').length
  const failedCount = assignments.filter(a => a.status === 'failed').length

  return (
    <>
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
              {batch.name}
              <Badge className={statusColors[batch.status]}>
                {batch.status}
              </Badge>
            </h1>
            <p className="text-muted-foreground">
              Batch ID: {batch.batch_id}
            </p>
          </div>
          <div className="flex gap-2">
            {(batch.status === 'draft' || batch.status === 'pending' || batch.status === 'failed' || batch.status === 'partial') && (
              <>
                <Button variant="outline" onClick={() => setAddModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add SKUs
                </Button>
                <Button onClick={handlePublish} disabled={actionLoading || assignments.length === 0}>
                  {actionLoading ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  {batch.status === 'failed' || batch.status === 'partial'
                    ? 'Retry Publish'
                    : 'Publish to Production'}
                </Button>
              </>
            )}
            {batch.status === 'published' && (
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
            <div className="text-2xl font-bold">{assignments.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Successful</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{successCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{failedCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Executed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatDate(batch.executed_at)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      {batch.notes && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{batch.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* SKU List */}
      <Card>
        <CardHeader>
          <CardTitle>SKUs in Batch</CardTitle>
          <CardDescription>
            {assignments.length} SKU(s) included in this batch
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Status</TableHead>
              <TableHead>Added</TableHead>
              <TableHead>Failure Reason</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignments.length === 0 ? (
              <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                    No SKUs in this batch yet. Click &quot;Add SKUs&quot; to get started.
                  </TableCell>
              </TableRow>
            ) : (
                assignments.map((assignment) => (
                  <TableRow key={assignment.id}>
                    <TableCell className="font-medium">{assignment.master_sku}</TableCell>
                    <TableCell>
                      <Badge className={statusColors[assignment.status || 'pending']}>
                        {assignment.status || 'pending'}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatDate(assignment.created_at)}</TableCell>
                    <TableCell className="max-w-[320px] truncate text-xs text-red-700">
                      {assignment.error_message || '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      {(batch.status === 'draft' || batch.status === 'pending' || batch.status === 'failed' || batch.status === 'partial') && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="text-red-600"
                          onClick={() => handleRemoveSku(assignment.master_sku)}
                          disabled={removingSkus.includes(assignment.master_sku)}
                        >
                          {removingSkus.includes(assignment.master_sku) ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                      {batch.status === 'published' && (
                        <Link href={`/performance?sku=${assignment.master_sku}`}>
                          <Button variant="outline" size="sm">
                            View Performance
                          </Button>
                        </Link>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <AddSkuModal
        open={addModalOpen}
        onOpenChange={setAddModalOpen}
        batchId={batch.batch_id}
        onAdded={handleSkusAdded}
      />
    </>
  )
}
