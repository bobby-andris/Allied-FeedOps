'use client'

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Check, X, RotateCcw, Loader2 } from "lucide-react"
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

interface ApprovalActionsProps {
  sku: string
  type: 'title' | 'description' | 'image' | 'all'
  currentApproval?: boolean | null
  size?: 'sm' | 'default'
}

export function ApprovalActions({ sku, type, currentApproval, size = 'default' }: ApprovalActionsProps) {
  const [loading, setLoading] = useState<'approve' | 'reject' | 'revision' | null>(null)
  const router = useRouter()

  const handleApproval = async (action: 'approve' | 'reject' | 'revision') => {
    setLoading(action)
    try {
      const body: Record<string, unknown> = { master_sku: sku }
      
      if (type === 'all') {
        // Approve/reject all elements
        body.title_approved = action === 'approve'
        body.description_approved = action === 'approve'
        body.image_approved = action === 'approve'
      } else {
        // Update specific element
        body[`${type}_approved`] = action === 'approve' ? true : action === 'reject' ? false : null
      }

      const response = await fetch('/api/approvals', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        throw new Error('Failed to update approval')
      }

      toast.success(
        action === 'approve' 
          ? `${type === 'all' ? 'All content' : type.charAt(0).toUpperCase() + type.slice(1)} approved` 
          : action === 'reject'
          ? `${type === 'all' ? 'All content' : type.charAt(0).toUpperCase() + type.slice(1)} rejected`
          : 'Revision requested'
      )
      
      router.refresh()
    } catch (error) {
      console.error('Approval error:', error)
      toast.error('Failed to update approval status')
    } finally {
      setLoading(null)
    }
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
