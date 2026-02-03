import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { ClipboardList, Layers, BarChart3, ArrowRight } from "lucide-react"

// Placeholder stats - will be fetched from Supabase
const stats = {
  pending: 35,
  approved: 5,
  revision: 0,
  rejected: 0,
  totalBatches: 2,
  publishedSkus: 1,
}

export default function DashboardPage() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Feed optimization overview for Allied Brass products
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
            <Badge variant="secondary">{stats.pending}</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending} SKUs</div>
            <p className="text-xs text-muted-foreground">
              Awaiting approval
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
              {stats.approved}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.approved} SKUs</div>
            <p className="text-xs text-muted-foreground">
              Ready for batching
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Batches</CardTitle>
            <Badge variant="outline">{stats.totalBatches}</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalBatches} Batches</div>
            <p className="text-xs text-muted-foreground">
              Total publish batches
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
            <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-100">
              {stats.publishedSkus}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.publishedSkus} SKUs</div>
            <p className="text-xs text-muted-foreground">
              Live in production
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Links */}
      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/review">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5" />
                Review Queue
              </CardTitle>
              <CardDescription>
                Review and approve generated content for SKUs
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center text-sm text-primary">
                Start reviewing <ArrowRight className="ml-2 h-4 w-4" />
              </div>
            </CardContent>
          </Card>
        </Link>
        
        <Link href="/batches">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Batch Management
              </CardTitle>
              <CardDescription>
                Create and manage publish batches
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center text-sm text-primary">
                Manage batches <ArrowRight className="ml-2 h-4 w-4" />
              </div>
            </CardContent>
          </Card>
        </Link>
        
        <Link href="/performance">
          <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Performance
              </CardTitle>
              <CardDescription>
                Track performance metrics post-publish
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center text-sm text-primary">
                View metrics <ArrowRight className="ml-2 h-4 w-4" />
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  )
}
