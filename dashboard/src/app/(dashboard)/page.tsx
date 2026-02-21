'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ApprovalChart } from '@/components/dashboard/ApprovalChart'
import { PlatformBreakdown } from '@/components/dashboard/PlatformBreakdown'
import { QualityDistribution } from '@/components/dashboard/QualityDistribution'
import { RecentActivity } from '@/components/dashboard/RecentActivity'
import { CoverageFunnel } from '@/components/dashboard/CoverageFunnel'
import {
  ArrowRight,
  Package,
  CheckCircle,
  Clock,
  XCircle,
  TrendingUp,
  ClipboardList,
  Layers,
  BarChart3,
  Sparkles,
} from 'lucide-react'
import Link from 'next/link'

interface Stats {
  overview: {
    totalSkus: number
    pendingReview: number
    approved: number
    rejected: number
    published: number
  }
  byPlatform: {
    google: { total: number; approved: number; pending: number; rejected: number }
    bing: { total: number; approved: number; pending: number; rejected: number }
    shopify: { total: number; approved: number; pending: number; rejected: number }
  }
  qualityScores: {
    average: number
    distribution: Array<{ range: string; count: number }>
  }
  recentActivity: Array<{
    type: string
    sku: string
    platform?: string
    status?: string
    timestamp: string
    user?: string
  }>
  trends: {
    approvalsThisWeek: number
    approvalsLastWeek: number
    publishesThisMonth: number
  }
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch('/api/stats')
        if (!res.ok) throw new Error('Failed to fetch stats')
        const data = await res.json()
        setStats(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }
    fetchStats()
  }, [])

  if (loading) {
    return <DashboardSkeleton />
  }

  if (error || !stats) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">Error loading dashboard: {error}</p>
          <Button variant="outline" className="mt-2" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </div>
      </div>
    )
  }

  const { overview, byPlatform, qualityScores, recentActivity, trends } = stats

  return (
    <div className="space-y-6 p-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            FeedOps content optimization overview
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/review">Review Queue</Link>
          </Button>
          <Button asChild>
            <Link href="/generate">
              <Sparkles className="h-4 w-4 mr-2" />
              Generate Content
            </Link>
          </Button>
        </div>
      </div>

      {/* SKU Coverage Funnel — pipeline health at a glance */}
      <CoverageFunnel />

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard
          title="Total SKUs"
          value={overview.totalSkus}
          icon={<Package className="h-4 w-4" />}
        />
        <StatCard
          title="Pending Review"
          value={overview.pendingReview}
          icon={<Clock className="h-4 w-4" />}
          variant="warning"
        />
        <StatCard
          title="Approved"
          value={overview.approved}
          icon={<CheckCircle className="h-4 w-4" />}
          variant="success"
        />
        <StatCard
          title="Rejected"
          value={overview.rejected}
          icon={<XCircle className="h-4 w-4" />}
          variant="danger"
        />
        <StatCard
          title="Published"
          value={overview.published}
          icon={<TrendingUp className="h-4 w-4" />}
          variant="info"
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Approval Progress</CardTitle>
            <CardDescription>Overall content approval status</CardDescription>
          </CardHeader>
          <CardContent>
            <ApprovalChart
              data={{
                approved: overview.approved,
                pending: overview.pendingReview,
                rejected: overview.rejected,
              }}
            />
          </CardContent>
        </Card>

        <PlatformBreakdown platforms={byPlatform} />

        <Card>
          <CardHeader>
            <CardTitle>Quality Distribution</CardTitle>
            <CardDescription>
              {qualityScores.distribution.reduce((sum, d) => sum + d.count, 0) > 0
                ? `Average score: ${qualityScores.average}`
                : 'No scores yet'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <QualityDistribution data={qualityScores.distribution} />
          </CardContent>
        </Card>
      </div>

      {/* Activity & Insights Row */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <RecentActivity activities={recentActivity} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Insights</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {overview.pendingReview > 0 && (
              <InsightCard
                type="action"
                message={`${overview.pendingReview} SKUs ready for review`}
                href="/review"
                label="Review Now"
              />
            )}
            {trends.approvalsThisWeek > trends.approvalsLastWeek && (
              <InsightCard
                type="success"
                message={`Approvals up ${trends.approvalsThisWeek - trends.approvalsLastWeek} from last week`}
              />
            )}
            {overview.published > 0 && (
              <InsightCard
                type="info"
                message={`${overview.published} SKU(s) published - monitor performance`}
                href="/performance"
                label="View Performance"
              />
            )}
            {overview.totalSkus === 0 && (
              <InsightCard
                type="action"
                message="No SKUs yet - start by generating content"
                href="/generate"
                label="Generate Content"
              />
            )}
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

function StatCard({
  title,
  value,
  icon,
  variant = 'default',
}: {
  title: string
  value: number
  icon: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}) {
  const colors = {
    default: 'text-foreground',
    success: 'text-green-600',
    warning: 'text-yellow-600',
    danger: 'text-red-600',
    info: 'text-blue-600',
  }

  const bgColors = {
    default: '',
    success: 'bg-green-100',
    warning: 'bg-yellow-100',
    danger: 'bg-red-100',
    info: 'bg-blue-100',
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className={`text-2xl font-bold ${colors[variant]}`}>{value}</p>
          </div>
          <Badge variant="secondary" className={bgColors[variant]}>
            <span className={colors[variant]}>{icon}</span>
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}

function InsightCard({
  type,
  message,
  href,
  label,
}: {
  type: 'action' | 'success' | 'info' | 'warning'
  message: string
  href?: string
  label?: string
}) {
  const colors = {
    action: 'border-blue-200 bg-blue-50',
    success: 'border-green-200 bg-green-50',
    info: 'border-gray-200 bg-gray-50',
    warning: 'border-yellow-200 bg-yellow-50',
  }

  return (
    <div className={`p-3 rounded-lg border ${colors[type]}`}>
      <p className="text-sm">{message}</p>
      {href && label && (
        <Button asChild variant="link" className="p-0 h-auto mt-1">
          <Link href={href}>
            {label} <ArrowRight className="h-3 w-3 ml-1" />
          </Link>
        </Button>
      )}
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6 p-8">
      <div className="flex justify-between items-center">
        <div>
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-5 w-64 mt-2" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-40" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-72" />
        ))}
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {[...Array(2)].map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    </div>
  )
}
