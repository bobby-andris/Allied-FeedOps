'use client'

import { AlertTriangle, Database, Gauge, Link2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface AttributionHealthCardsProps {
  qualityScore: number
  unassignedRevenueShare: number
  notSetCampaignRevenueShare: number
  landingInvalidRevenueShare: number
  reconciliationRatio: number | null
  riskLevel: 'low' | 'medium' | 'high'
}

function riskVariant(riskLevel: 'low' | 'medium' | 'high') {
  if (riskLevel === 'high') return 'destructive' as const
  if (riskLevel === 'medium') return 'outline' as const
  return 'secondary' as const
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

export function AttributionHealthCards(props: AttributionHealthCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Gauge className="h-4 w-4" />
            Attribution Quality
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-2xl font-bold">{formatPercent(props.qualityScore)}</p>
          <Badge variant={riskVariant(props.riskLevel)}>{props.riskLevel.toUpperCase()} risk</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4" />
            Unassigned Revenue Share
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">{formatPercent(props.unassignedRevenueShare)}</p>
          <p className="text-xs text-muted-foreground">Threshold: 25% (critical)</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Database className="h-4 w-4" />
            Campaign/Landing Integrity
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-sm font-semibold">
            (not set) campaign: {formatPercent(props.notSetCampaignRevenueShare)}
          </p>
          <p className="text-sm font-semibold">
            blank/(not set) landing: {formatPercent(props.landingInvalidRevenueShare)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Link2 className="h-4 w-4" />
            GA4 ↔ Shopify Ratio
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {typeof props.reconciliationRatio === 'number'
              ? props.reconciliationRatio.toFixed(3)
              : 'N/A'}
          </p>
          <p className="text-xs text-muted-foreground">Healthy band: 0.80 to 1.20</p>
        </CardContent>
      </Card>
    </div>
  )
}
