import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, Check, X, RotateCcw } from "lucide-react"
import Link from "next/link"
import { PlatformBadge } from "@/components/shared/PlatformBadge"
import { QualityScore } from "@/components/shared/QualityScore"

// Placeholder data - will be fetched from Supabase
const skuData = {
  sku: "1051",
  name: "Paper Towel Holders",
  category: "Bath Accessories",
  collection: "Waverly Place",
  score: 85,
  baseline: {
    title: "Waverly Place Collection Wall Mounted Paper Towel Holder",
    description: "Wall mounted paper towel holder from the Waverly Place Collection. Available in multiple finishes.",
  },
  candidate: {
    title: "Wall Mount Paper Towel Holder, Solid Brass, Concealed Hardware - Waverly Place Collection by Allied Brass",
    description: "Elevate your kitchen with this wall-mounted paper towel holder crafted from solid brass that will never corrode, peel, or tarnish. The concealed mounting hardware creates a clean, decorator-friendly appearance while the robust construction ensures years of reliable use.\n\n• Solid brass construction - guaranteed never to corrode, peel, or tarnish\n• Concealed mounting hardware - clean, seamless installation\n• Fits standard paper towel rolls\n• Coordinates with other Waverly Place Collection pieces\n• Backed by Allied Brass lifetime warranty",
  },
  finishes: ["Polished Chrome", "Satin Nickel", "Oil Rubbed Bronze", "Antique Brass"],
  images: [
    { url: "/placeholder-1.jpg", score: 88 },
    { url: "/placeholder-2.jpg", score: 82 },
    { url: "/placeholder-3.jpg", score: 75 },
  ],
}

export default async function SkuReviewPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = await params

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link 
          href="/review" 
          className="flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Review Queue
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              SKU {sku}
              <Badge variant="outline">{skuData.category}</Badge>
            </h1>
            <p className="text-muted-foreground">
              {skuData.name} - {skuData.collection}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <QualityScore score={skuData.score} size="lg" />
            <div className="flex gap-2">
              <Button variant="outline" className="text-red-600 hover:text-red-700">
                <X className="h-4 w-4 mr-2" />
                Reject
              </Button>
              <Button variant="outline" className="text-yellow-600 hover:text-yellow-700">
                <RotateCcw className="h-4 w-4 mr-2" />
                Request Revision
              </Button>
              <Button className="bg-green-600 hover:bg-green-700">
                <Check className="h-4 w-4 mr-2" />
                Approve All
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Platform Tabs */}
      <Tabs defaultValue="google" className="space-y-6">
        <TabsList>
          <TabsTrigger value="google">
            <PlatformBadge platform="google" className="mr-2" />
            Google
          </TabsTrigger>
          <TabsTrigger value="bing">
            <PlatformBadge platform="bing" className="mr-2" />
            Bing
          </TabsTrigger>
          <TabsTrigger value="shopify">
            <PlatformBadge platform="shopify" className="mr-2" />
            Shopify
          </TabsTrigger>
        </TabsList>

        <TabsContent value="google" className="space-y-6">
          {/* Title Comparison */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Title</CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="text-red-600">
                    <X className="h-4 w-4 mr-1" /> Reject
                  </Button>
                  <Button size="sm" className="bg-green-600 hover:bg-green-700">
                    <Check className="h-4 w-4 mr-1" /> Approve
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-2">Baseline</div>
                  <div className="p-4 rounded-lg bg-muted/50 border">
                    {skuData.baseline.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {skuData.baseline.title.length} characters
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-2">Candidate</div>
                  <div className="p-4 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800">
                    {skuData.candidate.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {skuData.candidate.title.length} characters
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Description Comparison */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Description</CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="text-red-600">
                    <X className="h-4 w-4 mr-1" /> Reject
                  </Button>
                  <Button size="sm" className="bg-green-600 hover:bg-green-700">
                    <Check className="h-4 w-4 mr-1" /> Approve
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-2">Baseline</div>
                  <div className="p-4 rounded-lg bg-muted/50 border whitespace-pre-wrap">
                    {skuData.baseline.description}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {skuData.baseline.description.length} characters
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground mb-2">Candidate</div>
                  <div className="p-4 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/20 dark:border-green-800 whitespace-pre-wrap">
                    {skuData.candidate.description}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {skuData.candidate.description.length} characters
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Lifestyle Images */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Lifestyle Images</CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="text-red-600">
                    <X className="h-4 w-4 mr-1" /> Reject
                  </Button>
                  <Button size="sm" className="bg-green-600 hover:bg-green-700">
                    <Check className="h-4 w-4 mr-1" /> Approve
                  </Button>
                </div>
              </div>
              <CardDescription>
                Select the best lifestyle image for this SKU
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                {skuData.images.map((image, index) => (
                  <div 
                    key={index} 
                    className={`relative rounded-lg border-2 p-2 cursor-pointer transition-colors ${
                      index === 0 ? 'border-primary bg-primary/5' : 'border-muted hover:border-primary/50'
                    }`}
                  >
                    <div className="aspect-square bg-muted rounded flex items-center justify-center text-muted-foreground">
                      Image {index + 1}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Variation {index + 1}</span>
                      <QualityScore score={image.score} size="sm" showLabel={false} />
                    </div>
                    {index === 0 && (
                      <Badge className="absolute top-4 right-4 bg-primary">Selected</Badge>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bing">
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Bing content preview coming soon
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shopify">
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Shopify content preview coming soon
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Separator className="my-8" />

      {/* Finish Variants */}
      <Card>
        <CardHeader>
          <CardTitle>Finish Variants</CardTitle>
          <CardDescription>
            Preview how the content will appear for each finish
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {skuData.finishes.map((finish) => (
              <Button key={finish} variant="outline" size="sm">
                {finish}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
