'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Ga4AttributionTrendPoint } from '@/lib/ga4/forensics'

interface AttributionTrendChartProps {
  points: Ga4AttributionTrendPoint[]
}

export function AttributionTrendChart({ points }: AttributionTrendChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Attribution Quality Trend</CardTitle>
      </CardHeader>
      <CardContent>
        {points.length === 0 ? (
          <p className="text-sm text-muted-foreground">No trend data available for this window.</p>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="reportDate" tick={{ fontSize: 12 }} minTickGap={18} />
                <YAxis tickFormatter={(value) => `${Math.round(value * 100)}%`} domain={[0, 1]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="qualityScore"
                  stroke="#0f766e"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="unassignedRevenueShare"
                  stroke="#b91c1c"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="notSetCampaignRevenueShare"
                  stroke="#d97706"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
