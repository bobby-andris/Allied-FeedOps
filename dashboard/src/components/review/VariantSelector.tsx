'use client'

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Check, X, Clock } from "lucide-react"
import { VariantIndex, VariantApproval } from "@/lib/supabase/types"

interface VariantSelectorProps {
  variants: VariantIndex[]
  variantApprovals: VariantApproval[]
  masterApprovalStatus?: string | null
  selectedFinish: string | null // null = "All Variants" (master SKU level)
  onSelect: (finish: string | null) => void
}

export function VariantSelector({
  variants,
  variantApprovals,
  masterApprovalStatus,
  selectedFinish,
  onSelect,
}: VariantSelectorProps) {
  // Get unique finishes from variants
  const finishes = [...new Set(variants.map(v => v.finish).filter(Boolean))] as string[]
  
  // Create a map of finish -> approval status
  const approvalMap = new Map<string, VariantApproval>()
  variantApprovals.forEach(va => {
    approvalMap.set(va.finish, va)
  })

  // Count approved variants
  const approvedCount = variantApprovals.filter(
    va => va.approval_status === 'approved'
  ).length
  
  // Get status indicator for a finish
  const getStatusIndicator = (finish: string) => {
    const approval = approvalMap.get(finish)
    if (!approval) {
      return <Clock className="h-3 w-3 text-muted-foreground" />
    }
    
    switch (approval.approval_status) {
      case 'approved':
        return <Check className="h-3 w-3 text-green-600" />
      case 'rejected':
        return <X className="h-3 w-3 text-red-600" />
      case 'revision':
        return <Clock className="h-3 w-3 text-yellow-600" />
      default:
        return <Clock className="h-3 w-3 text-muted-foreground" />
    }
  }

  // Get status indicator for master SKU (All Variants)
  const getMasterStatusIndicator = () => {
    switch (masterApprovalStatus) {
      case 'approved':
        return <Check className="h-3 w-3 text-green-600" />
      case 'rejected':
        return <X className="h-3 w-3 text-red-600" />
      case 'revision':
        return <Clock className="h-3 w-3 text-yellow-600" />
      default:
        return <Clock className="h-3 w-3 text-muted-foreground" />
    }
  }

  if (finishes.length === 0) {
    return null // Don't show selector if no variants
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">Variant Selection</h3>
        <Badge variant="secondary" className="text-xs">
          {approvedCount}/{finishes.length} variants approved
        </Badge>
      </div>
      
      <Tabs
        value={selectedFinish || 'all'}
        onValueChange={(value) => onSelect(value === 'all' ? null : value)}
        className="w-full"
      >
        <TabsList className="flex flex-wrap h-auto gap-1 p-1 bg-muted/50">
          <TabsTrigger 
            value="all" 
            className="flex items-center gap-1.5 data-[state=active]:bg-background"
          >
            {getMasterStatusIndicator()}
            <span>All Variants</span>
          </TabsTrigger>
          
          {finishes.map((finish) => (
            <TabsTrigger 
              key={finish} 
              value={finish}
              className="flex items-center gap-1.5 data-[state=active]:bg-background"
            >
              {getStatusIndicator(finish)}
              <span className="max-w-[120px] truncate">{finish}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  )
}
