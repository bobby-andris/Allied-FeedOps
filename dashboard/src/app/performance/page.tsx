import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { TrendingUp, TrendingDown, RefreshCw, Download } from "lucide-react"
import { PlatformBadge } from "@/components/shared/PlatformBadge"

// Placeholder data
const performanceData = {
  summary: {
    totalPublished: 1,
    avgCtrChange: 15.2,
    avgCvrChange: 8.5,
    totalImpressions: 12500,
    totalClicks: 450,
  },
  skus: [
    {
      sku: "1051",
      name: "Paper Towel Holders",
      platform: "google",
      publishedAt: "2026-02-03",
      baseline: { ctr: 2.1, cvr: 1.8, impressions: 5000, clicks: 105 },
      current: { ctr: 2.42, cvr: 1.95, impressions: 7500, clicks: 182 },
    },
  ],
}

function MetricChange({ baseline, current, format = 'percent' }: { 
  baseline: number; 
  current: number; 
  format?: 'percent' | 'number' 
}) {
  const change = ((current - baseline) / baseline) * 100
  const isPositive = change > 0
  
  return (
    <div className="flex items-center gap-1">
      <span className={isPositive ? 'text-green-600' : 'text-red-600'}>
        {format === 'percent' ? `${current.toFixed(2)}%` : current.toLocaleString()}
      </span>
      <span className={`text-xs flex items-center ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
        {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
        {Math.abs(change).toFixed(1)}%
      </span>
    </div>
  )
}

export default function PerformancePage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Performance</h1>
          <p className="text-muted-foreground">
            Track performance metrics for published SKUs
          </p>
        </div>
        <div className="flex gap-2">
          <Select defaultValue="7d">
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Time range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-5 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Published SKUs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{performanceData.summary.totalPublished}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg CTR Change</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 flex items-center gap-1">
              <TrendingUp className="h-5 w-5" />
              +{performanceData.summary.avgCtrChange}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg CVR Change</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 flex items-center gap-1">
              <TrendingUp className="h-5 w-5" />
              +{performanceData.summary.avgCvrChange}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Impressions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceData.summary.totalImpressions.toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Clicks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceData.summary.totalClicks.toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Platform Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Platforms</TabsTrigger>
          <TabsTrigger value="google">Google</TabsTrigger>
          <TabsTrigger value="bing">Bing</TabsTrigger>
          <TabsTrigger value="shopify">Shopify</TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <Card>
            <CardHeader>
              <CardTitle>SKU Performance</CardTitle>
              <CardDescription>
                Compare baseline vs current performance for all published SKUs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU</TableHead>
                    <TableHead>Product</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Published</TableHead>
                    <TableHead>CTR</TableHead>
                    <TableHead>CVR</TableHead>
                    <TableHead>Impressions</TableHead>
                    <TableHead>Clicks</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {performanceData.skus.map((sku) => (
                    <TableRow key={`${sku.sku}-${sku.platform}`}>
                      <TableCell className="font-medium">{sku.sku}</TableCell>
                      <TableCell>{sku.name}</TableCell>
                      <TableCell>
                        <PlatformBadge platform={sku.platform as 'google' | 'bing' | 'shopify'} />
                      </TableCell>
                      <TableCell>{sku.publishedAt}</TableCell>
                      <TableCell>
                        <MetricChange 
                          baseline={sku.baseline.ctr} 
                          current={sku.current.ctr} 
                        />
                      </TableCell>
                      <TableCell>
                        <MetricChange 
                          baseline={sku.baseline.cvr} 
                          current={sku.current.cvr} 
                        />
                      </TableCell>
                      <TableCell>
                        <MetricChange 
                          baseline={sku.baseline.impressions} 
                          current={sku.current.impressions}
                          format="number"
                        />
                      </TableCell>
                      <TableCell>
                        <MetricChange 
                          baseline={sku.baseline.clicks} 
                          current={sku.current.clicks}
                          format="number"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              
              {performanceData.skus.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  No published SKUs yet. Approve and publish content to see performance data.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="google">
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Google-specific performance charts coming soon
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bing">
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Bing-specific performance charts coming soon
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shopify">
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Shopify-specific performance charts coming soon
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
