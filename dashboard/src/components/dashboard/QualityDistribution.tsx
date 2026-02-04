'use client'

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface QualityDistributionProps {
  data: Array<{ range: string; count: number }>
}

// Colors from high to low quality
const COLORS = ['#22c55e', '#84cc16', '#facc15', '#f97316', '#ef4444']

export function QualityDistribution({ data }: QualityDistributionProps) {
  const hasData = data.some((d) => d.count > 0)

  if (!hasData) {
    return (
      <div className="flex items-center justify-center h-[200px] text-muted-foreground">
        No quality scores yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <XAxis
          dataKey="range"
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
        <Tooltip
          formatter={(value) => [`${value} SKUs`, 'Count']}
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
