'use client'

import Link from 'next/link'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { QualityScore } from '@/components/shared/QualityScore'
import { Check, X, RotateCcw } from 'lucide-react'

interface SkuCardProps {
  sku: string
  name?: string
  category?: string
  status: 'pending' | 'approved' | 'revision' | 'rejected'
  score?: number | null
  titleApproved?: boolean | null
  descriptionApproved?: boolean | null
  imageApproved?: boolean | null
  onApprove?: () => void
  onReject?: () => void
}

const statusColors: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  approved: 'bg-green-100 text-green-800',
  revision: 'bg-yellow-100 text-yellow-800',
  rejected: 'bg-red-100 text-red-800',
}

export function SkuCard({
  sku,
  name,
  category,
  status,
  score,
  titleApproved,
  descriptionApproved,
  imageApproved,
}: SkuCardProps) {
  const getApprovalIndicator = (approved: boolean | null | undefined) => {
    if (approved === true) return <Check className="h-3 w-3 text-green-600" />
    if (approved === false) return <X className="h-3 w-3 text-red-600" />
    return <span className="h-3 w-3 rounded-full bg-gray-200" />
  }

  return (
    <Card className="hover:bg-muted/50 transition-colors">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              SKU {sku}
              <Badge className={statusColors[status]}>{status}</Badge>
              {category && <Badge variant="outline">{category}</Badge>}
            </CardTitle>
            {name && <CardDescription>{name}</CardDescription>}
            
            {/* Element approval indicators */}
            <div className="flex items-center gap-4 pt-2">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                {getApprovalIndicator(titleApproved)}
                <span>Title</span>
              </div>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                {getApprovalIndicator(descriptionApproved)}
                <span>Description</span>
              </div>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                {getApprovalIndicator(imageApproved)}
                <span>Image</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {score !== undefined && score !== null && (
              <QualityScore score={score} />
            )}
            <Link href={`/review/${sku}`}>
              <Button variant={status === 'approved' ? 'outline' : 'default'}>
                {status === 'approved' ? 'View' : 'Review'}
              </Button>
            </Link>
          </div>
        </div>
      </CardHeader>
    </Card>
  )
}
