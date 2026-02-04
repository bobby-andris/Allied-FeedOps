'use client'

import { Progress } from '@/components/ui/progress'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PlatformData {
  total: number
  approved: number
  pending: number
  rejected: number
}

interface PlatformBreakdownProps {
  platforms: {
    google: PlatformData
    bing: PlatformData
    shopify: PlatformData
  }
}

const PLATFORM_ICONS: Record<string, string> = {
  google: 'G',
  bing: 'B',
  shopify: 'S',
}

const PLATFORM_COLORS: Record<string, string> = {
  google: 'bg-blue-500',
  bing: 'bg-teal-500',
  shopify: 'bg-green-500',
}

export function PlatformBreakdown({ platforms }: PlatformBreakdownProps) {
  const renderPlatform = (name: string, data: PlatformData) => {
    const approvedPct = data.total > 0 ? (data.approved / data.total) * 100 : 0

    return (
      <div key={name} className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded text-xs font-bold text-white ${PLATFORM_COLORS[name]}`}
            >
              {PLATFORM_ICONS[name]}
            </div>
            <span className="font-medium capitalize">{name}</span>
          </div>
          <span className="text-muted-foreground">
            {data.approved}/{data.total} approved
          </span>
        </div>
        <Progress value={approvedPct} className="h-2" />
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span className="text-green-600">{data.approved} approved</span>
          <span className="text-yellow-600">{data.pending} pending</span>
          <span className="text-red-600">{data.rejected} rejected</span>
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Platform Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {renderPlatform('google', platforms.google)}
        {renderPlatform('bing', platforms.bing)}
        {renderPlatform('shopify', platforms.shopify)}
      </CardContent>
    </Card>
  )
}
