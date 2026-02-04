'use client'

import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Star, ExternalLink } from 'lucide-react'
import type { CompetitorListing } from '@/lib/supabase/types'

interface CompetitorCardProps {
  listing: CompetitorListing
  onSelect?: () => void
  selected?: boolean
}

const SOURCE_COLORS: Record<string, string> = {
  google: 'bg-blue-100 text-blue-800',
  amazon: 'bg-orange-100 text-orange-800',
  wayfair: 'bg-purple-100 text-purple-800',
  homedepot: 'bg-orange-100 text-orange-700',
}

export function CompetitorCard({ listing, onSelect, selected }: CompetitorCardProps) {
  return (
    <Card
      className={`transition-all hover:shadow-md ${
        onSelect ? 'cursor-pointer' : ''
      } ${selected ? 'ring-2 ring-primary' : ''}`}
      onClick={onSelect}
    >
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start gap-2">
          <div className="flex items-center gap-2">
            <Badge className={SOURCE_COLORS[listing.source] || 'bg-gray-100'}>
              {listing.source}
            </Badge>
            {listing.source_type === 'serp' && listing.domain && (
              <span className="text-xs text-muted-foreground">
                {listing.domain}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {listing.position && (
              <span className="text-xs text-muted-foreground">
                #{listing.position}
              </span>
            )}
            {listing.source_url && (
              <a
                href={listing.source_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <h4 className="text-sm font-medium line-clamp-2">{listing.title}</h4>
        {listing.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {listing.description}
          </p>
        )}
        <div className="flex justify-between items-center text-xs">
          <span className="font-medium">
            {listing.price ? `$${listing.price.toFixed(2)}` : '—'}
          </span>
          {listing.rating && (
            <span className="flex items-center gap-1">
              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
              {listing.rating.toFixed(1)}
              {listing.review_count && (
                <span className="text-muted-foreground">
                  ({listing.review_count.toLocaleString()})
                </span>
              )}
            </span>
          )}
        </div>
        {listing.brand && (
          <p className="text-xs text-muted-foreground">{listing.brand}</p>
        )}
      </CardContent>
    </Card>
  )
}
