'use client'

import { useState, useMemo } from 'react'
import { ChevronDown, TrendingUp, TrendingDown, Activity, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import {
  formatNumber,
  formatCurrency,
  formatPercentage,
  formatMetricChange,
  getStatusLabel,
  getStatusColor,
  getStatusGlow,
  getCategoryAvgCTR,
  calculatePerformanceStatus,
} from '@/lib/performance-utils'
import { cn } from '@/lib/utils'

interface PerformanceBaseline {
  master_sku: string
  platform: string
  avg_impressions: number | null
  avg_clicks: number | null
  avg_ctr: number | null
  avg_conversions: number | null
  avg_cvr: number | null
  avg_conversion_value: number | null
  baseline_start_date: string
  baseline_end_date: string
  created_at: string
}

interface PerformanceSnapshot {
  id: string
  master_sku: string
  platform: string
  snapshot_date: string
  impressions: number | null
  clicks: number | null
  ctr: number | null
  conversions: number | null
  cvr: number | null
  conversion_value: number | null
  days_since_publish: number | null
  fetched_at: string
}

interface CurrentMetrics {
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  conversion_value: number
}

interface PerformanceCardProps {
  sku: string
  platform?: 'google' | 'bing' | 'shopify'
  baselines: PerformanceBaseline[]
  snapshots: PerformanceSnapshot[]
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function PerformanceCard({ sku, platform = 'google', baselines, snapshots }: PerformanceCardProps) {
  const [isOpen, setIsOpen] = useState(false)

  // Filter and aggregate data for the selected platform
  const { baseline, current, status } = useMemo(() => {
    // Get baseline for this platform (latest)
    const platformBaseline = baselines
      .filter(b => b.platform === platform)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] || null

    // Get snapshots for this platform (last 30 days)
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    const platformSnapshots = snapshots.filter(
      s => s.platform === platform && new Date(s.snapshot_date) >= thirtyDaysAgo
    )

    // Aggregate snapshots into current metrics
    let currentMetrics: CurrentMetrics | null = null
    if (platformSnapshots.length > 0) {
      const totalImpressions = platformSnapshots.reduce((sum, s) => sum + (s.impressions || 0), 0)
      const totalClicks = platformSnapshots.reduce((sum, s) => sum + (s.clicks || 0), 0)
      const totalConversions = platformSnapshots.reduce((sum, s) => sum + (s.conversions || 0), 0)
      const totalConversionValue = platformSnapshots.reduce((sum, s) => sum + (s.conversion_value || 0), 0)
      const avgCTR = totalImpressions > 0 ? totalClicks / totalImpressions : 0

      currentMetrics = {
        impressions: totalImpressions,
        clicks: totalClicks,
        ctr: avgCTR,
        conversions: totalConversions,
        conversion_value: totalConversionValue,
      }
    }

    // Calculate status
    const categoryAvgCTR = getCategoryAvgCTR('Bathroom Accessories')
    const performanceStatus = calculatePerformanceStatus(
      currentMetrics?.ctr,
      platformBaseline?.avg_ctr ?? undefined,
      categoryAvgCTR
    )

    return {
      baseline: platformBaseline,
      current: currentMetrics,
      status: performanceStatus,
    }
  }, [baselines, snapshots, platform])

  // If no current data but baseline exists, show baseline
  if (!current && baseline) {
    return (
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/5 to-transparent pointer-events-none" />
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-serif flex items-center gap-2">
              <Activity className="h-5 w-5" />
              BASELINE (30d)
            </CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Pre-Publish
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-muted-foreground text-xs">Impressions</div>
                <div className="font-semibold">{formatNumber(baseline.avg_impressions || 0)}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs">Clicks</div>
                <div className="font-semibold">{formatNumber(baseline.avg_clicks || 0)}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs">CTR</div>
                <div className="font-semibold">{formatPercentage(baseline.avg_ctr || 0)}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs">Conversions</div>
                <div className="font-semibold">{formatNumber(baseline.avg_conversions || 0)}</div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground border-t pt-2">
              Current baseline metrics. Post-publish tracking will begin after content is published.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // No data state (neither current nor baseline)
  if (!current) {
    return (
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/5 to-transparent pointer-events-none" />
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-serif flex items-center gap-2">
              <Activity className="h-5 w-5" />
              PERFORMANCE (30d)
            </CardTitle>
            <div className="flex items-center gap-2">
              <div
                data-testid="status-indicator"
                className={cn(
                  "w-2 h-2 rounded-full",
                  getStatusColor('no-data')
                )}
              />
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                {getStatusLabel('no-data')}
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              No data yet. Performance tracking begins after first publish.
            </p>
            <p className="text-xs text-muted-foreground">
              Check back 30 days after publishing to see metrics.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const categoryAvgCTR = getCategoryAvgCTR('Bathroom Accessories')
  const ctrVsCategory = current.ctr ? ((current.ctr - categoryAvgCTR) / categoryAvgCTR) * 100 : 0

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="relative overflow-hidden">
        {/* Scan-line overlay effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/5 to-transparent pointer-events-none" />

        <CardHeader className="pb-3">
          <CollapsibleTrigger asChild>
            <button
              className="w-full text-left hover:opacity-80 transition-opacity group"
              aria-expanded={isOpen}
            >
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-serif flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  PERFORMANCE (30d)
                </CardTitle>
                <div className="flex items-center gap-3">
                  {/* Status indicator with glow */}
                  <div className="flex items-center gap-2">
                    <div
                      data-testid="status-indicator"
                      className={cn(
                        "w-2 h-2 rounded-full transition-all duration-300",
                        getStatusColor(status),
                        getStatusGlow(status)
                      )}
                    />
                    <span className="text-xs text-muted-foreground uppercase tracking-wide font-mono">
                      {getStatusLabel(status)}
                    </span>
                  </div>
                  {/* Chevron */}
                  <ChevronDown
                    data-testid="chevron-icon"
                    className={cn(
                      "h-4 w-4 transition-transform duration-300",
                      isOpen && "rotate-180"
                    )}
                  />
                </div>
              </div>
            </button>
          </CollapsibleTrigger>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Collapsed state: Key metrics row */}
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-1.5">
              <span className="font-mono">{formatNumber(current.impressions)}</span>
              <span className="text-muted-foreground">impressions</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono font-semibold">{formatPercentage(current.ctr)}</span>
              <span className="text-muted-foreground">CTR</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono">{formatCurrency(current.conversion_value)}</span>
              <span className="text-muted-foreground">revenue</span>
            </div>
          </div>

          {/* CTR vs category indicator */}
          {current.ctr > 0 && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {ctrVsCategory >= 0 ? (
                <TrendingUp className="h-3 w-3 text-green-500" />
              ) : (
                <TrendingDown className="h-3 w-3 text-red-500" />
              )}
              <span>
                {ctrVsCategory >= 0 ? '+' : ''}
                {ctrVsCategory.toFixed(1)}% vs category avg
              </span>
            </div>
          )}

          {/* Expanded state: Comparison table or no-baseline message */}
          <CollapsibleContent>
            <div className="pt-4 border-t space-y-4">
              {baseline ? (
                <>
                  {/* Comparison table */}
                  <div className="space-y-2">
                    {/* Table header */}
                    <div className="grid grid-cols-[2fr,1fr,1fr,1fr] gap-4 text-xs uppercase tracking-wide text-muted-foreground font-mono pb-2">
                      <div></div>
                      <div>Current</div>
                      <div>Baseline</div>
                      <div>Change</div>
                    </div>

                    {/* Metrics rows */}
                    {[
                      {
                        label: 'Impressions',
                        current: current.impressions,
                        baseline: baseline.avg_impressions,
                        format: formatNumber,
                      },
                      {
                        label: 'Clicks',
                        current: current.clicks,
                        baseline: baseline.avg_clicks,
                        format: formatNumber,
                      },
                      {
                        label: 'CTR',
                        current: current.ctr,
                        baseline: baseline.avg_ctr,
                        format: formatPercentage,
                      },
                      {
                        label: 'Conversions',
                        current: current.conversions,
                        baseline: baseline.avg_conversions,
                        format: formatNumber,
                      },
                      {
                        label: 'Revenue',
                        current: current.conversion_value,
                        baseline: baseline.avg_conversion_value,
                        format: formatCurrency,
                      },
                    ].map((metric, index) => {
                      const change = formatMetricChange(metric.current, metric.baseline)
                      const isPositive = metric.current > (metric.baseline || 0)

                      return (
                        <div
                          key={metric.label}
                          className={cn(
                            "grid grid-cols-[2fr,1fr,1fr,1fr] gap-4 py-2 px-3 rounded bg-muted/30",
                            "animate-in fade-in slide-in-from-bottom-2 duration-300"
                          )}
                          style={{ animationDelay: `${index * 50}ms` }}
                        >
                          <div className="text-sm font-medium">{metric.label}</div>
                          <div className="text-sm font-mono">{metric.format(metric.current)}</div>
                          <div className="text-sm font-mono text-muted-foreground">
                            {metric.format(metric.baseline)}
                          </div>
                          <div className={cn(
                            "text-sm font-mono flex items-center gap-1",
                            change !== '—' && (isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400')
                          )}>
                            {change}
                            {change !== '—' && (
                              isPositive ?
                                <TrendingUp className="h-3 w-3" /> :
                                <TrendingDown className="h-3 w-3" />
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {/* Warning if CTR below category average */}
                  {status === 'warning' || status === 'critical' ? (
                    <div className={cn(
                      "p-3 rounded-lg border flex items-start gap-2",
                      status === 'critical'
                        ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
                        : "bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800"
                    )}>
                      <AlertTriangle className={cn(
                        "h-4 w-4 mt-0.5 shrink-0",
                        status === 'critical' ? "text-red-600" : "text-yellow-600"
                      )} />
                      <div className="space-y-1">
                        <p className={cn(
                          "text-sm font-medium",
                          status === 'critical'
                            ? "text-red-800 dark:text-red-200"
                            : "text-yellow-800 dark:text-yellow-200"
                        )}>
                          CTR {formatPercentage(current.ctr)} is {status === 'critical' ? 'significantly ' : ''}below category average ({formatPercentage(categoryAvgCTR)})
                        </p>
                        <p className={cn(
                          "text-xs",
                          status === 'critical'
                            ? "text-red-700 dark:text-red-300"
                            : "text-yellow-700 dark:text-yellow-300"
                        )}>
                          Recommend: Improve title keyword match and product relevance
                        </p>
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                /* No baseline message */
                <div className="p-4 rounded-lg bg-muted/50 text-center">
                  <p className="text-sm text-muted-foreground">
                    Baseline will be captured when content is published.
                  </p>
                </div>
              )}
            </div>
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  )
}
