'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { CompetitorListing } from '@/lib/supabase/types'

interface ComparisonViewProps {
  ourContent: {
    sku?: string
    title: string | null
    description: string | null
  }
  competitor: CompetitorListing
}

export function ComparisonView({ ourContent, competitor }: ComparisonViewProps) {
  const ourTitleLen = ourContent.title?.length || 0
  const compTitleLen = competitor.title.length
  const titleDiff = ourTitleLen - compTitleLen

  const ourDescLen = ourContent.description?.length || 0
  const compDescLen = competitor.description?.length || 0
  const descDiff = ourDescLen - compDescLen

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Allied Brass */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Badge className="bg-blue-100 text-blue-800">Allied Brass</Badge>
            {ourContent.sku && (
              <span className="text-xs text-muted-foreground font-normal">
                {ourContent.sku}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Title
            </div>
            <p className="text-sm font-medium">
              {ourContent.title || (
                <span className="text-muted-foreground italic">No title</span>
              )}
            </p>
            <div className="text-xs text-muted-foreground mt-1">
              {ourTitleLen} chars
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Description
            </div>
            <p className="text-xs line-clamp-4">
              {ourContent.description?.slice(0, 300) || (
                <span className="text-muted-foreground italic">No description</span>
              )}
              {ourContent.description && ourContent.description.length > 300 && '...'}
            </p>
            <div className="text-xs text-muted-foreground mt-1">
              {ourDescLen} chars
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Competitor */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Badge variant="outline">{competitor.source}</Badge>
            {competitor.position && (
              <span className="text-xs text-muted-foreground font-normal">
                #{competitor.position}
              </span>
            )}
            {competitor.domain && (
              <span className="text-xs text-muted-foreground font-normal">
                {competitor.domain}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Title
            </div>
            <p className="text-sm font-medium">{competitor.title}</p>
            <div className="text-xs text-muted-foreground mt-1">
              {compTitleLen} chars
              {titleDiff !== 0 && (
                <span className={titleDiff > 0 ? 'text-green-600' : 'text-yellow-600'}>
                  {' '}
                  (ours {titleDiff > 0 ? '+' : ''}
                  {titleDiff})
                </span>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">
              Description
            </div>
            <p className="text-xs line-clamp-4">
              {competitor.description?.slice(0, 300) || (
                <span className="text-muted-foreground italic">No description</span>
              )}
              {competitor.description && competitor.description.length > 300 && '...'}
            </p>
            <div className="text-xs text-muted-foreground mt-1">
              {compDescLen} chars
              {descDiff !== 0 && (
                <span className={descDiff > 0 ? 'text-green-600' : 'text-yellow-600'}>
                  {' '}
                  (ours {descDiff > 0 ? '+' : ''}
                  {descDiff})
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
