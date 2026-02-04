'use client'

import { useState, useMemo } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Check, X, Clock, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronRight } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { VariantApproval } from "@/lib/supabase/types"
import {
  generateVariantTitle,
  generateVariantDescription,
} from "@/lib/variant-content"

interface VariantContentGridProps {
  sku: string
  platform: 'google' | 'bing'
  baseTitle: string | null
  baseDescription: string | null
  variants: Array<{ option_sku: string; finish: string; finish_code: string }>
  variantApprovals: VariantApproval[]
  variantCurrentContent: Record<string, { title: string | null; description: string | null }>
  onApprovalChange: () => void
}

export function VariantContentGrid({
  sku,
  platform,
  baseTitle,
  baseDescription,
  variants,
  variantApprovals,
  variantCurrentContent,
  onApprovalChange,
}: VariantContentGridProps) {
  const [selectedVariants, setSelectedVariants] = useState<Set<string>>(new Set())
  const [expandedVariants, setExpandedVariants] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject' | null>(null)
  const router = useRouter()

  // Create approval lookup map by finish
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

  // Toggle selection
  const toggleSelection = (optionSku: string) => {
    const newSelected = new Set(selectedVariants)
    if (newSelected.has(optionSku)) {
      newSelected.delete(optionSku)
    } else {
      newSelected.add(optionSku)
    }
    setSelectedVariants(newSelected)
  }

  // Select all / none
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedVariants(new Set(variants.map(v => v.option_sku)))
    } else {
      setSelectedVariants(new Set())
    }
  }

  // Toggle expanded
  const toggleExpanded = (optionSku: string) => {
    const newExpanded = new Set(expandedVariants)
    if (newExpanded.has(optionSku)) {
      newExpanded.delete(optionSku)
    } else {
      newExpanded.add(optionSku)
    }
    setExpandedVariants(newExpanded)
  }

  // Expand all / collapse all
  const expandAll = () => setExpandedVariants(new Set(variants.map(v => v.option_sku)))
  const collapseAll = () => setExpandedVariants(new Set())

  // Check states
  const allSelected = variants.length > 0 && selectedVariants.size === variants.length
  const someSelected = selectedVariants.size > 0 && selectedVariants.size < variants.length

  // Bulk approve
  const handleBulkApprove = async (finishes: string[]) => {
    if (finishes.length === 0) {
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
          finishes,
          action: 'approve',
          title_approved: true,
          description_approved: true,
        }),
      })

      if (!response.ok) throw new Error('Failed to approve variants')

      toast.success(`Approved ${finishes.length} variant(s)`)
      setSelectedVariants(new Set())
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

  // Bulk reject
  const handleBulkReject = async (finishes: string[]) => {
    if (finishes.length === 0) {
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
          finishes,
          action: 'reject',
          title_approved: false,
          description_approved: false,
        }),
      })

      if (!response.ok) throw new Error('Failed to reject variants')

      toast.success(`Rejected ${finishes.length} variant(s)`)
      setSelectedVariants(new Set())
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

  // Get selected finishes
  const getSelectedFinishes = () => {
    return variants
      .filter(v => selectedVariants.has(v.option_sku))
      .map(v => v.finish)
  }

  // Get status badge
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

  // Get row style based on status
  const getRowStyle = (approval: VariantApproval | undefined) => {
    const status = approval?.approval_status
    switch (status) {
      case 'approved':
        return 'border-l-4 border-l-green-500 bg-green-50/30'
      case 'rejected':
        return 'border-l-4 border-l-red-500 bg-red-50/30'
      default:
        return 'border-l-4 border-l-gray-300 bg-white'
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
            <Button variant="outline" size="sm" onClick={expandAll}>
              Expand All
            </Button>
            <Button variant="outline" size="sm" onClick={collapseAll}>
              Collapse All
            </Button>
            {selectedVariants.size > 0 ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkReject(getSelectedFinishes())}
                  disabled={loading}
                  className="text-red-600 hover:text-red-700"
                >
                  {loading && bulkAction === 'reject' ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <XCircle className="h-4 w-4 mr-2" />
                  )}
                  Reject ({selectedVariants.size})
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleBulkApprove(getSelectedFinishes())}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {loading && bulkAction === 'approve' ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                  )}
                  Approve ({selectedVariants.size})
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                onClick={() => handleBulkApprove(variants.map(v => v.finish))}
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
      <CardContent className="space-y-2">
        {/* Select All row */}
        <div className="flex items-center gap-3 px-4 py-2 bg-muted/50 rounded-lg">
          <Checkbox
            checked={allSelected}
            ref={(el) => {
              if (el) {
                (el as HTMLButtonElement & { indeterminate?: boolean }).indeterminate = someSelected
              }
            }}
            onCheckedChange={handleSelectAll}
            aria-label="Select all variants"
          />
          <span className="text-sm font-medium">Select All</span>
        </div>

        {/* Variant accordions */}
        {variants.map((variant) => {
          const approval = approvalMap.get(variant.finish)
          const isExpanded = expandedVariants.has(variant.option_sku)
          const isSelected = selectedVariants.has(variant.option_sku)
          const currentContent = variantCurrentContent[variant.option_sku] || { title: null, description: null }
          const candidateTitle = generateVariantTitle(baseTitle, variant.finish, platform)
          const candidateDescription = generateVariantDescription(baseDescription, variant.finish)

          return (
            <Collapsible
              key={variant.option_sku}
              open={isExpanded}
              onOpenChange={() => toggleExpanded(variant.option_sku)}
            >
              <div className={`rounded-lg ${getRowStyle(approval)}`}>
                {/* Collapsed header */}
                <div className="flex items-center gap-3 px-4 py-3">
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() => toggleSelection(variant.option_sku)}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={`Select ${variant.finish}`}
                  />
                  <CollapsibleTrigger asChild>
                    <button className="flex-1 flex items-center gap-3 text-left hover:bg-muted/30 rounded px-2 py-1 -ml-2">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                      <div className="flex-1">
                        <div className="font-medium">{variant.finish}</div>
                        <div className="text-xs text-muted-foreground">{variant.option_sku}</div>
                      </div>
                    </button>
                  </CollapsibleTrigger>
                  {getStatusBadge(approval)}
                </div>

                {/* Expanded content */}
                <CollapsibleContent>
                  <div className="px-4 pb-4 pt-2 space-y-4 border-t">
                    {/* Title comparison */}
                    <div>
                      <h4 className="text-sm font-semibold mb-2">Title</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1">Current (Live)</div>
                          <div className="p-3 rounded-lg bg-muted/50 border text-sm min-h-[60px]">
                            {currentContent.title || <span className="text-muted-foreground italic">No current title</span>}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1">Candidate (New)</div>
                          <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-sm min-h-[60px]">
                            {candidateTitle}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Description comparison */}
                    <div>
                      <h4 className="text-sm font-semibold mb-2">Description</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1">Current (Live)</div>
                          <div className="p-3 rounded-lg bg-muted/50 border text-sm min-h-[100px] whitespace-pre-wrap">
                            {currentContent.description || <span className="text-muted-foreground italic">No current description</span>}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1">Candidate (New)</div>
                          <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-sm min-h-[100px] whitespace-pre-wrap">
                            {candidateDescription}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Quick approve/reject for this variant */}
                    <div className="flex justify-end gap-2 pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkReject([variant.finish])}
                        disabled={loading}
                        className="text-red-600 hover:text-red-700"
                      >
                        <X className="h-4 w-4 mr-1" />
                        Reject
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleBulkApprove([variant.finish])}
                        disabled={loading}
                        className="bg-green-600 hover:bg-green-700"
                      >
                        <Check className="h-4 w-4 mr-1" />
                        Approve
                      </Button>
                    </div>
                  </div>
                </CollapsibleContent>
              </div>
            </Collapsible>
          )
        })}
      </CardContent>
    </Card>
  )
}
