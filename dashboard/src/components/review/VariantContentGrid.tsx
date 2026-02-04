'use client'

import { useState, useMemo } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Check, X, Clock, Loader2, CheckCircle2, XCircle } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { VariantApproval } from "@/lib/supabase/types"
import {
  generateVariantTitle,
  generateVariantDescription,
  truncateForPreview,
} from "@/lib/variant-content"

interface VariantContentGridProps {
  sku: string
  platform: 'google' | 'bing'
  baseTitle: string | null
  baseDescription: string | null
  variants: Array<{ finish: string; finish_code: string }>
  variantApprovals: VariantApproval[]
  onApprovalChange: () => void
}

export function VariantContentGrid({
  sku,
  platform,
  baseTitle,
  baseDescription,
  variants,
  variantApprovals,
  onApprovalChange,
}: VariantContentGridProps) {
  const [selectedFinishes, setSelectedFinishes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject' | null>(null)
  const router = useRouter()

  // Create approval lookup map
  const approvalMap = useMemo(() => {
    const map = new Map<string, VariantApproval>()
    variantApprovals.forEach(va => {
      map.set(va.finish, va)
    })
    return map
  }, [variantApprovals])

  // Compute stats
  const stats = useMemo(() => {
    const total = variants.length
    const approved = variantApprovals.filter(va => va.approval_status === 'approved').length
    const rejected = variantApprovals.filter(va => va.approval_status === 'rejected').length
    const pending = total - approved - rejected
    return { total, approved, rejected, pending }
  }, [variants, variantApprovals])

  // Handle select all toggle
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedFinishes(new Set(variants.map(v => v.finish)))
    } else {
      setSelectedFinishes(new Set())
    }
  }

  // Handle individual checkbox toggle
  const handleSelectOne = (finish: string, checked: boolean) => {
    const newSelected = new Set(selectedFinishes)
    if (checked) {
      newSelected.add(finish)
    } else {
      newSelected.delete(finish)
    }
    setSelectedFinishes(newSelected)
  }

  // Check if all are selected
  const allSelected = variants.length > 0 && selectedFinishes.size === variants.length
  const someSelected = selectedFinishes.size > 0 && selectedFinishes.size < variants.length

  // Bulk approve selected variants
  const handleBulkApprove = async () => {
    if (selectedFinishes.size === 0) {
      toast.error('No variants selected')
      return
    }

    setLoading(true)
    setBulkAction('approve')
    try {
      const response = await fetch('/api/variants/approvals/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          finish_codes: variants
            .filter(v => selectedFinishes.has(v.finish))
            .map(v => v.finish_code),
          finishes: Array.from(selectedFinishes),
          action: 'approve',
          title_approved: true,
          description_approved: true,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to approve variants')
      }

      toast.success(`Approved ${selectedFinishes.size} variant(s)`)
      setSelectedFinishes(new Set())
      router.refresh()
      onApprovalChange()
    } catch (error) {
      console.error('Error approving variants:', error)
      toast.error('Failed to approve variants')
    } finally {
      setLoading(false)
      setBulkAction(null)
    }
  }

  // Bulk reject selected variants
  const handleBulkReject = async () => {
    if (selectedFinishes.size === 0) {
      toast.error('No variants selected')
      return
    }

    setLoading(true)
    setBulkAction('reject')
    try {
      const response = await fetch('/api/variants/approvals/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          finish_codes: variants
            .filter(v => selectedFinishes.has(v.finish))
            .map(v => v.finish_code),
          finishes: Array.from(selectedFinishes),
          action: 'reject',
          title_approved: false,
          description_approved: false,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to reject variants')
      }

      toast.success(`Rejected ${selectedFinishes.size} variant(s)`)
      setSelectedFinishes(new Set())
      router.refresh()
      onApprovalChange()
    } catch (error) {
      console.error('Error rejecting variants:', error)
      toast.error('Failed to reject variants')
    } finally {
      setLoading(false)
      setBulkAction(null)
    }
  }

  // Approve all variants
  const handleApproveAll = async () => {
    setLoading(true)
    setBulkAction('approve')
    try {
      const response = await fetch('/api/variants/approvals/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          finish_codes: variants.map(v => v.finish_code),
          finishes: variants.map(v => v.finish),
          action: 'approve',
          title_approved: true,
          description_approved: true,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to approve all variants')
      }

      toast.success(`Approved all ${variants.length} variants`)
      router.refresh()
      onApprovalChange()
    } catch (error) {
      console.error('Error approving all:', error)
      toast.error('Failed to approve all variants')
    } finally {
      setLoading(false)
      setBulkAction(null)
    }
  }

  // Get status badge for a variant
  const getStatusBadge = (approval: VariantApproval | undefined) => {
    const status = approval?.approval_status
    switch (status) {
      case 'approved':
        return (
          <Badge className="bg-green-100 text-green-800 border-green-200">
            <Check className="h-3 w-3 mr-1" />
            Approved
          </Badge>
        )
      case 'rejected':
        return (
          <Badge className="bg-red-100 text-red-800 border-red-200">
            <X className="h-3 w-3 mr-1" />
            Rejected
          </Badge>
        )
      default:
        return (
          <Badge variant="secondary" className="bg-gray-100 text-gray-600">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </Badge>
        )
    }
  }

  // Get row background color based on status
  const getRowClassName = (approval: VariantApproval | undefined) => {
    const status = approval?.approval_status
    switch (status) {
      case 'approved':
        return 'bg-green-50/50 hover:bg-green-50 border-l-4 border-l-green-500'
      case 'rejected':
        return 'bg-red-50/50 hover:bg-red-50 border-l-4 border-l-red-500'
      default:
        return 'hover:bg-muted/50 border-l-4 border-l-gray-300'
    }
  }

  if (variants.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          No variants found for this SKU
        </CardContent>
      </Card>
    )
  }

  if (!baseTitle && !baseDescription) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          No base content found for {platform.toUpperCase()}. Generate content first.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              All Variants Content
              <Badge variant="outline">{platform.toUpperCase()}</Badge>
            </CardTitle>
            <CardDescription>
              {stats.approved}/{stats.total} approved
              {stats.rejected > 0 && ` • ${stats.rejected} rejected`}
              {stats.pending > 0 && ` • ${stats.pending} pending`}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {selectedFinishes.size > 0 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBulkReject}
                  disabled={loading}
                  className="text-red-600 hover:text-red-700"
                >
                  {loading && bulkAction === 'reject' ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <XCircle className="h-4 w-4 mr-2" />
                  )}
                  Reject Selected ({selectedFinishes.size})
                </Button>
                <Button
                  size="sm"
                  onClick={handleBulkApprove}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {loading && bulkAction === 'approve' ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                  )}
                  Approve Selected ({selectedFinishes.size})
                </Button>
              </>
            )}
            {selectedFinishes.size === 0 && (
              <Button
                size="sm"
                onClick={handleApproveAll}
                disabled={loading}
                className="bg-green-600 hover:bg-green-700"
              >
                {loading && bulkAction === 'approve' ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Approve All ({stats.total})
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Base content preview */}
        <div className="mb-4 p-3 bg-muted/50 rounded-lg text-sm">
          <div className="font-medium text-muted-foreground mb-1">Base Template</div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Title: </span>
              <span className="text-foreground">{truncateForPreview(baseTitle, 80) || 'N/A'}</span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Description: </span>
              <span className="text-foreground">{truncateForPreview(baseDescription, 80) || 'N/A'}</span>
            </div>
          </div>
        </div>

        <TooltipProvider>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={allSelected}
                    ref={(el) => {
                      if (el) {
                        // Set indeterminate state for "some selected"
                        (el as HTMLButtonElement & { indeterminate?: boolean }).indeterminate = someSelected
                      }
                    }}
                    onCheckedChange={handleSelectAll}
                    aria-label="Select all variants"
                  />
                </TableHead>
                <TableHead className="w-40">Finish</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-28 text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {variants.map((variant) => {
                const approval = approvalMap.get(variant.finish)
                const variantTitle = generateVariantTitle(baseTitle, variant.finish, platform)
                const variantDesc = generateVariantDescription(baseDescription, variant.finish)
                const isSelected = selectedFinishes.has(variant.finish)

                return (
                  <TableRow
                    key={variant.finish_code}
                    className={getRowClassName(approval)}
                  >
                    <TableCell>
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={(checked) => handleSelectOne(variant.finish, checked as boolean)}
                        aria-label={`Select ${variant.finish}`}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      {variant.finish}
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help text-sm">
                            {truncateForPreview(variantTitle, 50)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-md">
                          <p className="text-sm">{variantTitle}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help text-sm text-muted-foreground">
                            {truncateForPreview(variantDesc, 60)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-lg">
                          <p className="text-sm">{variantDesc}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell className="text-center">
                      {getStatusBadge(approval)}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TooltipProvider>
      </CardContent>
    </Card>
  )
}
