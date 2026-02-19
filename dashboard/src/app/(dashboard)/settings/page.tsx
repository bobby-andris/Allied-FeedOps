'use client'

import { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Database, Key, Bell, Shield, RefreshCw, ShoppingCart, BarChart3, TrendingUp } from "lucide-react"
import { ApiStatusCard, type ServiceStatusType } from "@/components/settings/ApiStatusCard"

// Types for health check response
interface ServiceStatus {
  status: ServiceStatusType
  latency?: number
  error?: string
  projectId?: string
  customerId?: string
  spreadsheetId?: string
  spreadsheetTitle?: string
  shopName?: string
  storeUrl?: string
  propertyId?: string
  note?: string
}

interface HealthResponse {
  supabase: ServiceStatus
  googleAds: ServiceStatus
  gmc: ServiceStatus
  shopify: ServiceStatus
  googleAnalytics: ServiceStatus
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchHealth = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    try {
      const response = await fetch('/api/health')
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`)
      }
      const data = await response.json()
      setHealth(data)
    } catch (error) {
      console.error('Failed to fetch health status:', error)
      // Set error state for all services
      setHealth({
        supabase: { status: 'error', error: 'Failed to check status' },
        googleAds: { status: 'error', error: 'Failed to check status' },
        gmc: { status: 'error', error: 'Failed to check status' },
        shopify: { status: 'error', error: 'Failed to check status' },
        googleAnalytics: { status: 'error', error: 'Failed to check status' },
      })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
  }, [fetchHealth])

  const handleRefresh = () => {
    fetchHealth(true)
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Configure dashboard preferences and integrations
          </p>
        </div>
        <Button 
          variant="outline" 
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Checking...' : 'Refresh Status'}
        </Button>
      </div>

      <div className="space-y-6">
        {/* Database Connection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database Connection
            </CardTitle>
            <CardDescription>
              Supabase connection status and configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ApiStatusCard
              name="Supabase"
              status={health?.supabase?.status || 'unknown'}
              details={health?.supabase?.projectId 
                ? `Project: ${health.supabase.projectId}`
                : 'Checking connection...'
              }
              error={health?.supabase?.error}
              latency={health?.supabase?.latency}
              loading={loading}
            />
            <Separator />
            <div className="space-y-2">
              <Label htmlFor="supabase-url">Supabase URL</Label>
              <Input
                id="supabase-url"
                value={process.env.NEXT_PUBLIC_SUPABASE_URL || ''}
                disabled
                placeholder="Configured via NEXT_PUBLIC_SUPABASE_URL"
              />
            </div>
          </CardContent>
        </Card>

        {/* API Keys */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              API Integrations
            </CardTitle>
            <CardDescription>
              External service connections
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ApiStatusCard
              name="Google Merchant Center"
              icon={<ShoppingCart className="h-4 w-4 text-muted-foreground" />}
              status={health?.gmc?.status || 'unknown'}
              details={health?.gmc?.spreadsheetTitle 
                ? `Spreadsheet: ${health.gmc.spreadsheetTitle}`
                : health?.gmc?.status === 'connected' 
                  ? 'Feed sync enabled'
                  : undefined
              }
              error={health?.gmc?.error}
              latency={health?.gmc?.latency}
              loading={loading}
            />
            <Separator />
            <ApiStatusCard
              name="Shopify"
              icon={<ShoppingCart className="h-4 w-4 text-muted-foreground" />}
              status={health?.shopify?.status || 'unknown'}
              details={health?.shopify?.shopName 
                ? `Store: ${health.shopify.shopName}`
                : health?.shopify?.storeUrl
                  ? `Store: ${health.shopify.storeUrl}`
                  : 'GraphQL Admin API'
              }
              error={health?.shopify?.error}
              latency={health?.shopify?.latency}
              loading={loading}
            />
            <Separator />
            <ApiStatusCard
              name="Google Analytics"
              icon={<BarChart3 className="h-4 w-4 text-muted-foreground" />}
              status={health?.googleAnalytics?.status || 'unknown'}
              details={health?.googleAnalytics?.propertyId || 'Allied Brass - GA4 (Old)'}
              error={health?.googleAnalytics?.error}
              loading={loading}
            />
            <Separator />
            <ApiStatusCard
              name="Google Ads"
              icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
              status={health?.googleAds?.status || 'unknown'}
              details={health?.googleAds?.customerId 
                ? `Customer ID: ${health.googleAds.customerId}`
                : undefined
              }
              error={health?.googleAds?.error}
              loading={loading}
            />
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Notifications
            </CardTitle>
            <CardDescription>
              Current notification configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Notifications are configured via the <code className="text-xs bg-muted px-1 py-0.5 rounded">SLACK_WEBHOOK_URL</code> environment variable on Cloud Run.
              When set, the pipeline sends alerts for batch completions, errors, and performance changes.
            </p>
            <Separator />
            <div>
              <p className="font-medium text-sm">Batch completion alerts</p>
              <p className="text-sm text-muted-foreground">Sent when batch jobs complete (success or failure)</p>
            </div>
            <Separator />
            <div>
              <p className="font-medium text-sm">Performance alerts</p>
              <p className="text-sm text-muted-foreground">Sent when significant performance changes are detected post-publish</p>
            </div>
            <Separator />
            <div>
              <p className="font-medium text-sm">Error notifications</p>
              <p className="text-sm text-muted-foreground">Sent for publishing errors and pipeline failures</p>
            </div>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600">
              <Shield className="h-5 w-5" />
              Danger Zone
            </CardTitle>
            <CardDescription>
              Destructive database operations
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Destructive operations (clearing approvals, removing performance data) must be performed
              directly via Supabase. Use the Supabase dashboard or run SQL queries against the
              <code className="text-xs bg-muted px-1 py-0.5 rounded mx-1">sku_approvals</code>,
              <code className="text-xs bg-muted px-1 py-0.5 rounded mx-1">performance_snapshots</code>, and
              <code className="text-xs bg-muted px-1 py-0.5 rounded mx-1">performance_baselines</code> tables.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
