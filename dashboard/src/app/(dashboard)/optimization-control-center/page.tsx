import { Card, CardContent } from '@/components/ui/card'
import { Construction } from 'lucide-react'

export default function OptimizationControlCenterPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Optimization Control Center</h1>
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <Construction className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">Coming in v1.3c</h2>
          <p className="text-muted-foreground mt-2 max-w-md">
            Distribution-based scoring, revenue leakage analysis, and profitability-aware optimization.
            Requires margin data integration (Shopify COGS) planned for v1.3c.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
