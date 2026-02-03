import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Search, Filter } from "lucide-react"

// Placeholder data - will be fetched from Supabase
const skuList = [
  { sku: "1051", name: "Paper Towel Holders", category: "Bath Accessories", status: "approved", score: 85 },
  { sku: "1052", name: "Towel Bars", category: "Bath Accessories", status: "pending", score: 78 },
  { sku: "1053", name: "Grab Bars", category: "Safety", status: "pending", score: 82 },
  { sku: "1054", name: "Soap Dishes", category: "Bath Accessories", status: "revision", score: 65 },
  { sku: "1055", name: "Mirrors", category: "Bath Accessories", status: "pending", score: 88 },
]

export default function ReviewPage() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Review Queue</h1>
        <p className="text-muted-foreground">
          Review and approve generated content for product SKUs
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search SKUs..." className="pl-9" />
        </div>
        
        <Select defaultValue="all">
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="revision">Needs Revision</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
        
        <Select defaultValue="all">
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="bath">Bath Accessories</SelectItem>
            <SelectItem value="safety">Safety</SelectItem>
            <SelectItem value="kitchen">Kitchen</SelectItem>
          </SelectContent>
        </Select>
        
        <Button variant="outline" size="icon">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {/* Status Tabs */}
      <Tabs defaultValue="pending" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pending">
            Pending <Badge variant="secondary" className="ml-2">35</Badge>
          </TabsTrigger>
          <TabsTrigger value="approved">
            Approved <Badge variant="secondary" className="ml-2">5</Badge>
          </TabsTrigger>
          <TabsTrigger value="revision">
            Revision <Badge variant="secondary" className="ml-2">0</Badge>
          </TabsTrigger>
          <TabsTrigger value="all">All</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="space-y-4">
          {skuList.filter(s => s.status === 'pending').map((sku) => (
            <Card key={sku.sku} className="hover:bg-muted/50 transition-colors">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      SKU {sku.sku}
                      <Badge variant="outline">{sku.category}</Badge>
                    </CardTitle>
                    <CardDescription>{sku.name}</CardDescription>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">Quality Score</div>
                      <div className="text-2xl font-bold text-green-600">{sku.score}</div>
                    </div>
                    <Button>Review</Button>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="approved" className="space-y-4">
          {skuList.filter(s => s.status === 'approved').map((sku) => (
            <Card key={sku.sku}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      SKU {sku.sku}
                      <Badge className="bg-green-100 text-green-800">Approved</Badge>
                    </CardTitle>
                    <CardDescription>{sku.name}</CardDescription>
                  </div>
                  <Button variant="outline">View Details</Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="revision" className="space-y-4">
          {skuList.filter(s => s.status === 'revision').map((sku) => (
            <Card key={sku.sku}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      SKU {sku.sku}
                      <Badge className="bg-yellow-100 text-yellow-800">Revision</Badge>
                    </CardTitle>
                    <CardDescription>{sku.name}</CardDescription>
                  </div>
                  <Button>Review</Button>
                </div>
              </CardHeader>
            </Card>
          ))}
          {skuList.filter(s => s.status === 'revision').length === 0 && (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No SKUs need revision
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="all" className="space-y-4">
          {skuList.map((sku) => (
            <Card key={sku.sku}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      SKU {sku.sku}
                      <Badge variant={sku.status === 'approved' ? 'default' : 'secondary'}>
                        {sku.status}
                      </Badge>
                    </CardTitle>
                    <CardDescription>{sku.name}</CardDescription>
                  </div>
                  <Button variant={sku.status === 'approved' ? 'outline' : 'default'}>
                    {sku.status === 'approved' ? 'View' : 'Review'}
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  )
}
