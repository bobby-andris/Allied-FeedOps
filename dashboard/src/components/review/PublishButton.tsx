'use client'

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Loader2, Rocket, CheckCircle2, XCircle } from "lucide-react"
import { toast } from 'sonner'

interface PublishButtonProps {
  sku: string
  approvalStatus: string | null
  hasGoogleContent?: boolean
  hasShopifyContent?: boolean
}

type Environment = 'production' | 'staging'
type Platform = 'google' | 'shopify'

interface PublishResult {
  platform: Platform
  success: boolean
  error?: string
  details?: Record<string, unknown>
}

export function PublishButton({
  sku,
  approvalStatus,
  hasGoogleContent = true,
  hasShopifyContent = true,
}: PublishButtonProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [environment, setEnvironment] = useState<Environment>('production')
  const [platforms, setPlatforms] = useState<Platform[]>(['google', 'shopify'])
  const [results, setResults] = useState<PublishResult[] | null>(null)

  // Only show if SKU is approved
  if (approvalStatus !== 'approved') {
    return null
  }

  const togglePlatform = (platform: Platform) => {
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    )
  }

  const handlePublish = async () => {
    if (platforms.length === 0) {
      toast.error('Please select at least one platform')
      return
    }

    setLoading(true)
    setResults(null)

    try {
      const response = await fetch('/api/publish/sku', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_sku: sku,
          platforms,
          environment,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Publish failed')
      }

      setResults(data.results)

      // Show toast with summary
      const successful = data.summary?.successful || 0
      const failed = data.summary?.failed || 0

      if (failed === 0) {
        toast.success(
          `Published to ${successful} platform${successful > 1 ? 's' : ''} successfully`,
          {
            description: platforms.join(', '),
          }
        )
      } else if (successful === 0) {
        toast.error('Publishing failed', {
          description: data.results?.map((r: PublishResult) => r.error).filter(Boolean).join('; '),
        })
      } else {
        toast.warning(`Published to ${successful}/${successful + failed} platforms`, {
          description: `${failed} failed`,
        })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Publishing failed'
      toast.error(message)
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Rocket className="h-4 w-4" />
          Publish
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">Publish to Production</h4>
            <p className="text-sm text-muted-foreground">
              Push approved content to selected platforms
            </p>
          </div>

          {/* Environment selector */}
          <div className="space-y-2">
            <Label>Environment</Label>
            <Select
              value={environment}
              onValueChange={(v) => setEnvironment(v as Environment)}
              disabled={loading}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="production">Production</SelectItem>
                <SelectItem value="staging">Staging</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Platform checkboxes */}
          <div className="space-y-3">
            <Label>Platforms</Label>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="google"
                  checked={platforms.includes('google')}
                  onCheckedChange={() => togglePlatform('google')}
                  disabled={loading || !hasGoogleContent}
                />
                <label
                  htmlFor="google"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Google Shopping (GMC Sheets)
                </label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="shopify"
                  checked={platforms.includes('shopify')}
                  onCheckedChange={() => togglePlatform('shopify')}
                  disabled={loading || !hasShopifyContent}
                />
                <label
                  htmlFor="shopify"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Shopify
                </label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="bing"
                  checked={false}
                  disabled={true}
                />
                <label
                  htmlFor="bing"
                  className="text-sm font-medium leading-none opacity-50"
                >
                  Bing (coming soon)
                </label>
              </div>
            </div>
          </div>

          {/* Results */}
          {results && (
            <div className="space-y-2 pt-2 border-t">
              <Label>Results</Label>
              <div className="space-y-1">
                {results.map((result) => (
                  <div
                    key={result.platform}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="capitalize">{result.platform}</span>
                    {result.success ? (
                      <span className="flex items-center gap-1 text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                        Success
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-600">
                        <XCircle className="h-4 w-4" />
                        Failed
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {results.some((r) => r.details?.variant_count) && (
                <p className="text-xs text-muted-foreground">
                  {results.find((r) => r.details?.variant_count)?.details?.variant_count} variants updated
                </p>
              )}
            </div>
          )}

          {/* Publish button */}
          <Button
            onClick={handlePublish}
            disabled={loading || platforms.length === 0}
            className="w-full"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Publishing...
              </>
            ) : (
              <>
                <Rocket className="h-4 w-4 mr-2" />
                Publish to {environment}
              </>
            )}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
