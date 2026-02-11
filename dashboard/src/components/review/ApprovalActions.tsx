'use client'

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Check, X, RotateCcw, Loader2 } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import type { Platform } from '@/lib/publishing/types'
import { getPlatformApprovalActionText } from './approval-copy'

interface ApprovalActionsProps {
  sku: string
  // New explicit mode
  platform?: Platform
  scope?: 'platform' | 'variant'
  // Backward-compatible props
  finish?: string | null
  type?: 'title' | 'description' | 'image' | 'all'
  currentApproval?: boolean | null
  size?: 'sm' | 'default'
}

export function ApprovalActions({
  sku,
  platform,
  scope,
  finish,
  type = 'title',
  size = 'default',
}: ApprovalActionsProps) {
  const [loading, setLoading] = useState<'approve' | 'reject' | 'revision' | null>(null)
  const router = useRouter()
  const isPlatformScope = scope === 'platform' && Boolean(platform)

  const handleApproval = async (action: 'approve' | 'reject' | 'revision') => {
    setLoading(action)
    try {
      const body: Record<string, unknown> = { master_sku: sku }

      if (isPlatformScope && platform) {
        body.platform = platform
        body.title_approved = action === 'approve'
        body.description_approved = action === 'approve'
      } else {
        // Add finish for variant-level approvals
        if (finish) {
          body.finish = finish
        }

        if (type === 'all') {
          body.title_approved = action === 'approve'
          body.description_approved = action === 'approve'
          body.image_approved = action === 'approve'
        } else {
          body[`${type}_approved`] = action === 'approve' ? true : action === 'reject' ? false : null
        }
      }

      const apiUrl = finish ? '/api/variants/approvals' : '/api/approvals'

      const response = await fetch(apiUrl, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        throw new Error('Failed to update approval')
      }

      if (isPlatformScope && platform) {
        if (action === 'approve') {
          const platformLabel = platform.charAt(0).toUpperCase() + platform.slice(1)
          toast.success(`${platformLabel} content approved for publishing`)
        }
      } else {
        const finishLabel = finish ? ` (${finish})` : ''
        toast.success(
          action === 'approve'
            ? `${type === 'all' ? 'All content' : type.charAt(0).toUpperCase() + type.slice(1)} approved${finishLabel}`
            : action === 'reject'
              ? `${type === 'all' ? 'All content' : type.charAt(0).toUpperCase() + type.slice(1)} rejected${finishLabel}`
              : `Revision requested${finishLabel}`,
        )
      }

      router.refresh()
    } catch (error) {
      console.error('Approval error:', error)
      toast.error('Failed to update approval status')
    } finally {
      setLoading(null)
    }
  }

  if (isPlatformScope && platform) {
    return (
      <div className="flex items-center gap-2">
        <Button
          size={size}
          className="bg-green-600 hover:bg-green-700"
          onClick={() => handleApproval('approve')}
          disabled={loading !== null}
        >
          {loading === 'approve' ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Check className="h-4 w-4 mr-2" />
          )}
          {getPlatformApprovalActionText(platform)}
        </Button>
      </div>
    )
  }

  if (type === 'all') {
    return (
      <div className="flex gap-2">
        <Button
          variant="outline"
          size={size}
          className="text-red-600 hover:text-red-700"
          onClick={() => handleApproval('reject')}
          disabled={loading !== null}
        >
          {loading === 'reject' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <X className="h-4 w-4 mr-2" />}
          Reject
        </Button>
        <Button
          variant="outline"
          size={size}
          className="text-yellow-600 hover:text-yellow-700"
          onClick={() => handleApproval('revision')}
          disabled={loading !== null}
        >
          {loading === 'revision' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RotateCcw className="h-4 w-4 mr-2" />}
          Request Revision
        </Button>
        <Button
          size={size}
          className="bg-green-600 hover:bg-green-700"
          onClick={() => handleApproval('approve')}
          disabled={loading !== null}
        >
          {loading === 'approve' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
          Approve All
        </Button>
      </div>
    )
  }

  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        size={size}
        className="text-red-600 hover:text-red-700 hover:bg-red-50"
        onClick={() => handleApproval('reject')}
        disabled={loading !== null}
      >
        {loading === 'reject' ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <X className="h-4 w-4 mr-1" />}
        Reject
      </Button>
      <Button
        size={size}
        className="bg-green-600 hover:bg-green-700"
        onClick={() => handleApproval('approve')}
        disabled={loading !== null}
      >
        {loading === 'approve' ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Check className="h-4 w-4 mr-1" />}
        Approve
      </Button>
    </div>
  )
}
