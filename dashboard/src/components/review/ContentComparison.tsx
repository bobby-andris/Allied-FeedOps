'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, X, Copy, CheckCheck } from 'lucide-react'

interface ContentComparisonProps {
  title: string
  baseline: string | null
  candidate: string | null
  approved?: boolean | null
  onApprove?: () => void
  onReject?: () => void
  disabled?: boolean
}

export function ContentComparison({
  title,
  baseline,
  candidate,
  approved,
  onApprove,
  onReject,
  disabled = false,
}: ContentComparisonProps) {
  const [copiedBaseline, setCopiedBaseline] = useState(false)
  const [copiedCandidate, setCopiedCandidate] = useState(false)

  const copyToClipboard = async (text: string | null, side: 'baseline' | 'candidate') => {
    if (!text) return
    await navigator.clipboard.writeText(text)
    if (side === 'baseline') {
      setCopiedBaseline(true)
      setTimeout(() => setCopiedBaseline(false), 2000)
    } else {
      setCopiedCandidate(true)
      setTimeout(() => setCopiedCandidate(false), 2000)
    }
  }

  const getApprovalStatus = () => {
    if (approved === true) return { label: 'Approved', className: 'bg-green-100 text-green-800' }
    if (approved === false) return { label: 'Rejected', className: 'bg-red-100 text-red-800' }
    return { label: 'Pending', className: 'bg-gray-100 text-gray-800' }
  }

  const status = getApprovalStatus()

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            {title}
            <Badge className={status.className}>{status.label}</Badge>
          </CardTitle>
          {!disabled && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className={approved === false ? 'bg-red-50 border-red-200' : 'text-red-600'}
                onClick={onReject}
              >
                <X className="h-4 w-4 mr-1" /> Reject
              </Button>
              <Button
                size="sm"
                className={approved === true ? 'bg-green-600' : 'bg-green-600 hover:bg-green-700'}
                onClick={onApprove}
              >
                <Check className="h-4 w-4 mr-1" /> Approve
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-6">
          {/* Baseline */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">Baseline</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={() => copyToClipboard(baseline, 'baseline')}
              >
                {copiedBaseline ? (
                  <CheckCheck className="h-3 w-3 text-green-600" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 border min-h-[100px] whitespace-pre-wrap text-sm">
              {baseline || <span className="text-muted-foreground italic">No baseline content</span>}
            </div>
            {baseline && (
              <div className="text-xs text-muted-foreground mt-2">
                {baseline.length} characters
              </div>
            )}
          </div>

          {/* Candidate */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">Candidate</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2"
                onClick={() => copyToClipboard(candidate, 'candidate')}
              >
                {copiedCandidate ? (
                  <CheckCheck className="h-3 w-3 text-green-600" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
            <div className={`p-4 rounded-lg border min-h-[100px] whitespace-pre-wrap text-sm ${
              approved === true 
                ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800' 
                : approved === false
                ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
                : 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800'
            }`}>
              {candidate || <span className="text-muted-foreground italic">No candidate content</span>}
            </div>
            {candidate && (
              <div className="text-xs text-muted-foreground mt-2">
                {candidate.length} characters
                {baseline && (
                  <span className={candidate.length > baseline.length ? 'text-green-600' : 'text-yellow-600'}>
                    {' '}({candidate.length > baseline.length ? '+' : ''}{candidate.length - baseline.length})
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
