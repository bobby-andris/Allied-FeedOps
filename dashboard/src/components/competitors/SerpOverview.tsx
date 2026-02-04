'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { TrendingUp, ExternalLink } from 'lucide-react'

interface DomainStats {
  domain: string
  count: number
  avgPosition: number
}

interface SerpOverviewProps {
  domainStats: DomainStats[]
  totalListings: number
}

// Known domains to highlight
const KNOWN_DOMAINS: Record<string, { label: string; color: string }> = {
  'amazon.com': { label: 'Amazon', color: 'bg-orange-100 text-orange-800' },
  'wayfair.com': { label: 'Wayfair', color: 'bg-purple-100 text-purple-800' },
  'homedepot.com': { label: 'Home Depot', color: 'bg-orange-100 text-orange-700' },
  'lowes.com': { label: "Lowe's", color: 'bg-blue-100 text-blue-800' },
  'signaturehardware.com': { label: 'Signature Hardware', color: 'bg-green-100 text-green-800' },
  'kingstonbrass.com': { label: 'Kingston Brass', color: 'bg-yellow-100 text-yellow-800' },
  'alliedbrass.com': { label: 'Allied Brass', color: 'bg-blue-100 text-blue-700' },
  'houzz.com': { label: 'Houzz', color: 'bg-teal-100 text-teal-800' },
  'build.com': { label: 'Build.com', color: 'bg-gray-100 text-gray-800' },
  'overstock.com': { label: 'Overstock', color: 'bg-red-100 text-red-800' },
}

export function SerpOverview({ domainStats, totalListings }: SerpOverviewProps) {
  if (!domainStats.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            SERP Domain Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No SERP data available. Run a Google SERP scrape to see who ranks for your keywords.
          </p>
        </CardContent>
      </Card>
    )
  }

  const maxCount = Math.max(...domainStats.map(d => d.count), 1)

  // Find Allied Brass position
  const alliedBrassStats = domainStats.find(d =>
    d.domain.includes('alliedbrass') || d.domain.includes('allied-brass')
  )

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <TrendingUp className="h-4 w-4" />
          SERP Domain Analysis
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {totalListings} search results across {domainStats.length} domains
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {domainStats.slice(0, 12).map((stat, i) => {
          const known = KNOWN_DOMAINS[stat.domain]
          const isAlliedBrass = stat.domain.includes('alliedbrass') || stat.domain.includes('allied-brass')

          return (
            <div
              key={stat.domain}
              className={`flex items-center gap-3 ${isAlliedBrass ? 'bg-blue-50 -mx-2 px-2 py-1 rounded' : ''}`}
            >
              <span className="text-xs text-muted-foreground w-4">
                {i + 1}.
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  {known ? (
                    <Badge className={known.color}>{known.label}</Badge>
                  ) : (
                    <span className="text-sm font-medium truncate">
                      {stat.domain}
                    </span>
                  )}
                  <a
                    href={`https://${stat.domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <Progress
                  value={(stat.count / maxCount) * 100}
                  className="h-1.5 mt-1"
                />
              </div>
              <div className="text-right text-xs">
                <div className="font-medium">{stat.count} results</div>
                <div className="text-muted-foreground">
                  avg #{stat.avgPosition}
                </div>
              </div>
            </div>
          )
        })}

        {/* Allied Brass insight */}
        {alliedBrassStats ? (
          <div className="pt-3 border-t mt-4">
            <p className="text-xs text-muted-foreground">
              Allied Brass appears in <strong>{alliedBrassStats.count}</strong> results
              with an average position of <strong>#{alliedBrassStats.avgPosition}</strong>
            </p>
          </div>
        ) : (
          <div className="pt-3 border-t mt-4">
            <p className="text-xs text-yellow-700 bg-yellow-50 p-2 rounded">
              Allied Brass not found in current SERP results. Consider SEO optimization.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
