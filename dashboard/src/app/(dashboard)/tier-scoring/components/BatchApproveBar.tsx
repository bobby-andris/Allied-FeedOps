'use client'

import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'

interface BatchApproveBarProps {
  highConfidenceCount: number
  onBatchApprove: () => void
  loading?: boolean
}

export function BatchApproveBar({
  highConfidenceCount,
  onBatchApprove,
  loading = false,
}: BatchApproveBarProps) {
  if (highConfidenceCount <= 0) return null

  return (
    <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b px-4 py-3 flex items-center justify-between">
      <span className="text-sm font-medium">
        {highConfidenceCount} high-confidence {highConfidenceCount === 1 ? 'recommendation' : 'recommendations'}
      </span>
      <Button
        variant="default"
        size="sm"
        onClick={onBatchApprove}
        disabled={loading}
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Approve All
      </Button>
    </div>
  )
}
