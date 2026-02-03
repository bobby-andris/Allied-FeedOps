'use client'

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Check, X, Clock, Loader2, Copy } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { VariantIndex, VariantApproval } from "@/lib/supabase/types"

interface VariantApprovalGridProps {
  sku: string
  variants: VariantIndex[]
  variantApprovals: VariantApproval[]
  masterApproval: {
    approval_status: string
    title_approved: boolean | null
    description_approved: boolean | null
    image_approved: boolean | null
  } | null
  onVariantSelect?: (finish: string) => void
}

export function VariantApprovalGrid({
  sku,
  variants,
  variantApprovals,
  masterApproval,
  onVariantSelect,
}: VariantApprovalGridProps) {
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  // Get unique finishes from variants
  const finishes = [...new Set(variants.map(v => v.finish).filter(Boolean))] as string[]

  // Create a map of finish -> approval
  const approvalMap = new Map<string, VariantApproval>()
  variantApprovals.forEach(va => {
    approvalMap.set(va.finish, va)
  })

  // Count stats
  const stats = {
    total: finishes.length,
    approved: variantApprovals.filter(va => va.approval_status === 'approved').length,
    rejected: variantApprovals.filter(va => va.approval_status === 'rejected').length,
    pending: finishes.length - variantApprovals.filter(va => 
      va.approval_status === 'approved' || va.approval_status === 'rejected'
    ).length,
  }

  // Get approval status icon
  const getStatusIcon = (approved: boolean | number | null | undefined) => {
    if (approved === true || approved === 1) {
      return <Check className="h-4 w-4 text-green-600" />
    } else if (approved === false || approved === 0) {
      return <X className="h-4 w-4 text-red-600" />
    }
    return <Clock className="h-4 w-4 text-muted-foreground" />
  }

  // Get status badge
  const getStatusBadge = (status: string | undefined) => {
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

  // Copy master approval to all variants
  const handleCopyMasterToAll = async () => {
    if (!masterApproval) {
      toast.error('No master approval to copy')
      return
    }

    setLoading(true)
    try {
      // Copy to each finish
      const promises = finishes.map(async (finish) => {
        const response = await fetch('/api/variants/approvals', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            master_sku: sku,
            finish,
            title_approved: masterApproval.title_approved,
            description_approved: masterApproval.description_approved,
            image_approved: masterApproval.image_approved,
          }),
        })
        if (!response.ok) throw new Error(`Failed for ${finish}`)
        return response.json()
      })

      await Promise.all(promises)
      toast.success(`Copied master approval to ${finishes.length} variants`)
      router.refresh()
    } catch (error) {
      console.error('Error copying approvals:', error)
      toast.error('Failed to copy approvals to all variants')
    } finally {
      setLoading(false)
    }
  }

  // Approve all variants
  const handleApproveAll = async () => {
    setLoading(true)
    try {
      const promises = finishes.map(async (finish) => {
        const response = await fetch('/api/variants/approvals', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            master_sku: sku,
            finish,
            title_approved: true,
            description_approved: true,
            image_approved: true,
          }),
        })
        if (!response.ok) throw new Error(`Failed for ${finish}`)
        return response.json()
      })

      await Promise.all(promises)
      toast.success(`Approved all ${finishes.length} variants`)
      router.refresh()
    } catch (error) {
      console.error('Error approving all:', error)
      toast.error('Failed to approve all variants')
    } finally {
      setLoading(false)
    }
  }

  if (finishes.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Variant Approval Status</CardTitle>
            <CardDescription>
              {stats.approved}/{stats.total} variants approved
              {stats.rejected > 0 && ` | ${stats.rejected} rejected`}
              {stats.pending > 0 && ` | ${stats.pending} pending`}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {masterApproval && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyMasterToAll}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Copy className="h-4 w-4 mr-2" />
                )}
                Copy Master to All
              </Button>
            )}
            <Button
              size="sm"
              className="bg-green-600 hover:bg-green-700"
              onClick={handleApproveAll}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              Approve All Variants
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Finish</TableHead>
              <TableHead className="text-center w-20">Title</TableHead>
              <TableHead className="text-center w-20">Desc</TableHead>
              <TableHead className="text-center w-20">Image</TableHead>
              <TableHead className="text-center w-28">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {finishes.map((finish) => {
              const approval = approvalMap.get(finish)
              return (
                <TableRow 
                  key={finish}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onVariantSelect?.(finish)}
                >
                  <TableCell className="font-medium">{finish}</TableCell>
                  <TableCell className="text-center">
                    {getStatusIcon(approval?.title_approved)}
                  </TableCell>
                  <TableCell className="text-center">
                    {getStatusIcon(approval?.description_approved)}
                  </TableCell>
                  <TableCell className="text-center">
                    {getStatusIcon(approval?.image_approved)}
                  </TableCell>
                  <TableCell className="text-center">
                    {getStatusBadge(approval?.approval_status)}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
