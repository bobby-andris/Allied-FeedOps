'use client'

import { useMemo, useState } from 'react'
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Loader2, Rocket, CheckCircle2, XCircle } from "lucide-react"
import { toast } from 'sonner'
import type { Platform } from '@/lib/publishing/types'
import type { PlatformReadinessByPlatform } from '@/lib/publishing/platform-readiness'

interface PublishButtonProps {
  sku: string
  // New readiness-aware mode
  platformReadiness?: PlatformReadinessByPlatform
  // Backward-compatible props
  approvalStatus?: string | null
  hasGoogleContent?: boolean
  hasBingContent?: boolean
  hasShopifyContent?: boolean
}

type Environment = 'production' | 'staging'

interface PublishResult {
  platform: Platform
  success: boolean
  error?: string
  code?: string
  actionable_message?: string
  details?: Record<string, unknown>
}

function fallbackReadinessFromLegacyProps({
  approvalStatus,
  hasGoogleContent = true,
  hasBingContent = false,
  hasShopifyContent = true,
}: Pick<PublishButtonProps, 'approvalStatus' | 'hasGoogleContent' | 'hasBingContent' | 'hasShopifyContent'>): PlatformReadinessByPlatform {
  const globallyApproved = approvalStatus === 'approved'
  return {
    google: {
      ready: globallyApproved && hasGoogleContent,
      blockers: globallyApproved && hasGoogleContent
        ? []
        : [{ code: 'legacy_not_ready', reason: 'Google is not approved yet', actionableMessage: 'Approve Google content before publishing.' }],
    },
    bing: {
      ready: globallyApproved && hasBingContent,
      blockers: globallyApproved && hasBingContent
        ? []
        : [{ code: 'legacy_not_ready', reason: 'Bing is not approved yet', actionableMessage: 'Approve Bing content before publishing.' }],
    },
    shopify: {
      ready: globallyApproved && hasShopifyContent,
      blockers: globallyApproved && hasShopifyContent
        ? []
        : [{ code: 'legacy_not_ready', reason: 'Shopify is not approved yet', actionableMessage: 'Approve Shopify content before publishing.' }],
    },
  }
}

export function PublishButton(props: PublishButtonProps) {
  const {
    sku,
    platformReadiness,
    approvalStatus,
    hasGoogleContent,
    hasBingContent,
    hasShopifyContent,
  } = props

  const readiness = useMemo(
    () => platformReadiness ?? fallbackReadinessFromLegacyProps({
      approvalStatus,
      hasGoogleContent,
      hasBingContent,
      hasShopifyContent,
    }),
    [platformReadiness, approvalStatus, hasGoogleContent, hasBingContent, hasShopifyContent],
  )

  const initialPlatforms = useMemo<Platform[]>(
    () => (['google', 'bing', 'shopify'] as Platform[]).filter((platform) => readiness[platform].ready),
    [readiness],
  )

  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [environment, setEnvironment] = useState<Environment>('production')
  const [platforms, setPlatforms] = useState<Platform[]>(initialPlatforms)
  const [results, setResults] = useState<PublishResult[] | null>(null)

  const togglePlatform = (platform: Platform) => {
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    )
  }

  const handlePublish = async () => {
    if (platforms.length === 0) {
      toast.error('Select at least one platform to publish')
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
        if (Array.isArray(data.readiness_errors) && data.readiness_errors.length > 0) {
          const readinessResults: PublishResult[] = data.readiness_errors.map((error: {
            platform: Platform
            reason: string
            code: string
            actionableMessage: string
          }) => ({
            platform: error.platform,
            success: false,
            error: error.reason,
            code: error.code,
            actionable_message: error.actionableMessage,
          }))
          setResults(readinessResults)
        }
        throw new Error(data.error || 'Publish failed')
      }

      setResults(data.results)

      const successful = data.summary?.successful || 0
      const failed = data.summary?.failed || 0

      if (failed === 0) {
        toast.success(
          `Published to ${successful} platform${successful > 1 ? 's' : ''} successfully`,
          { description: platforms.join(', ') },
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
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Rocket className="h-4 w-4" />
          Publish
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Publish Platform Subset</DialogTitle>
          <DialogDescription>
            Publish SKU {sku} to ready platforms only. Unready selections will fail with exact blockers.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
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

          <div className="space-y-3">
            <Label>Platforms</Label>
            <div className="space-y-2">
              {(['google', 'bing', 'shopify'] as Platform[]).map((platform) => {
                const ready = readiness[platform].ready
                const blockers = readiness[platform].blockers

                return (
                  <div key={platform} className="rounded-md border p-2">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={platform}
                        checked={platforms.includes(platform)}
                        onCheckedChange={() => togglePlatform(platform)}
                        disabled={loading}
                      />
                      <label
                        htmlFor={platform}
                        className="text-sm font-medium capitalize leading-none"
                      >
                        {platform}
                      </label>
                      <Badge variant={ready ? 'default' : 'secondary'}>
                        {ready ? 'Ready' : 'Not Ready'}
                      </Badge>
                    </div>
                    {!ready && blockers.length > 0 && (
                      <div className="mt-2 text-xs text-muted-foreground space-y-1">
                        {blockers.slice(0, 2).map((blocker) => (
                          <div key={`${platform}-${blocker.code}`}>• {blocker.reason}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {results && (
            <div className="space-y-2 pt-2 border-t">
              <Label>Results</Label>
              <div className="space-y-2">
                {results.map((result, index) => (
                  <div
                    key={`${result.platform}-${result.code ?? result.error ?? 'result'}-${index}`}
                    className="rounded-md border p-2 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="capitalize font-medium">{result.platform}</span>
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
                    {!result.success && result.error && (
                      <div className="mt-1 text-xs text-muted-foreground">{result.error}</div>
                    )}
                    {!result.success && result.actionable_message && (
                      <div className="mt-1 text-xs text-red-700">{result.actionable_message}</div>
                    )}
                  </div>
                ))}
              </div>
              {results.some((r) => r.details?.variant_count) && (
                <p className="text-xs text-muted-foreground">
                  {String(results.find((r) => r.details?.variant_count)?.details?.variant_count)} variants updated
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handlePublish} disabled={loading || platforms.length === 0}>
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
