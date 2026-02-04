import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const supabase = await createClient()

    // Fetch all data in parallel
    const [
      approvalsResult,
      batchesResult,
      publishEventsResult,
      generatedContentResult,
      variantApprovalsResult,
    ] = await Promise.all([
      supabase.from('sku_approvals').select('approval_status, approved_at'),
      supabase.from('publish_batches').select('status'),
      supabase
        .from('publish_events')
        .select('master_sku, platform, action, status, created_at, published_by')
        .order('created_at', { ascending: false })
        .limit(20),
      supabase.from('generated_content').select('platform, quality_score'),
      supabase.from('variant_approvals').select('platform, approval_status'),
    ])

    const approvals = approvalsResult.data || []
    const batches = batchesResult.data || []
    const publishEvents = publishEventsResult.data || []
    const generatedContent = generatedContentResult.data || []
    const variantApprovals = variantApprovalsResult.data || []

    // Overview stats
    const overview = {
      totalSkus: approvals.length,
      pendingReview: approvals.filter((s) => s.approval_status === 'pending').length,
      approved: approvals.filter((s) => s.approval_status === 'approved').length,
      rejected: approvals.filter((s) => s.approval_status === 'rejected').length,
      published: new Set(
        publishEvents
          .filter((e) => e.status === 'success' && e.action === 'publish')
          .map((e) => e.master_sku)
      ).size,
    }

    // Platform breakdown from variant_approvals
    const platforms = ['google', 'bing', 'shopify'] as const
    const byPlatform: Record<string, { total: number; approved: number; pending: number; rejected: number }> = {}

    for (const platform of platforms) {
      const platformApprovals = variantApprovals.filter((v) => v.platform === platform)
      byPlatform[platform] = {
        total: platformApprovals.length || overview.totalSkus,
        approved: platformApprovals.filter((v) => v.approval_status === 'approved').length,
        pending: platformApprovals.filter((v) => v.approval_status === 'pending').length,
        rejected: platformApprovals.filter((v) => v.approval_status === 'rejected').length,
      }
      // If no variant_approvals, fall back to sku_approvals counts
      if (platformApprovals.length === 0) {
        byPlatform[platform] = {
          total: overview.totalSkus,
          approved: overview.approved,
          pending: overview.pendingReview,
          rejected: overview.rejected,
        }
      }
    }

    // Quality scores distribution
    const scores = generatedContent
      .map((c) => c.quality_score)
      .filter((s): s is number => s != null)

    const qualityDistribution = [
      { range: '90-100', count: scores.filter((s) => s >= 90).length },
      { range: '80-89', count: scores.filter((s) => s >= 80 && s < 90).length },
      { range: '70-79', count: scores.filter((s) => s >= 70 && s < 80).length },
      { range: '60-69', count: scores.filter((s) => s >= 60 && s < 70).length },
      { range: '<60', count: scores.filter((s) => s < 60).length },
    ]

    const averageScore = scores.length > 0
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : 0

    const qualityScores = {
      average: averageScore,
      distribution: qualityDistribution,
    }

    // Recent activity
    const recentActivity = publishEvents.map((event) => ({
      type: event.action,
      sku: event.master_sku,
      platform: event.platform,
      status: event.status,
      timestamp: event.created_at,
      user: event.published_by,
    }))

    // Trends - approvals this week vs last week
    const now = new Date()
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    const twoWeeksAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000)

    const approvalsThisWeek = approvals.filter(
      (s) => s.approved_at && new Date(s.approved_at) > weekAgo
    ).length

    const approvalsLastWeek = approvals.filter(
      (s) =>
        s.approved_at &&
        new Date(s.approved_at) > twoWeeksAgo &&
        new Date(s.approved_at) <= weekAgo
    ).length

    const publishesThisMonth = publishEvents.filter(
      (e) =>
        e.status === 'success' &&
        new Date(e.created_at).getMonth() === now.getMonth() &&
        new Date(e.created_at).getFullYear() === now.getFullYear()
    ).length

    const trends = {
      approvalsThisWeek,
      approvalsLastWeek,
      publishesThisMonth,
    }

    // Legacy format (for backwards compatibility)
    const approvalStats = {
      pending: overview.pendingReview,
      approved: overview.approved,
      revision: approvals.filter((s) => s.approval_status === 'revision').length,
      rejected: overview.rejected,
      total: overview.totalSkus,
    }

    const batchStats = {
      draft: batches.filter((b) => b.status === 'draft').length,
      ready: batches.filter((b) => b.status === 'ready').length,
      executing: batches.filter((b) => b.status === 'executing').length,
      completed: batches.filter((b) => b.status === 'completed').length,
      failed: batches.filter((b) => b.status === 'failed').length,
      total: batches.length,
    }

    return NextResponse.json({
      // New enhanced format
      overview,
      byPlatform,
      qualityScores,
      recentActivity,
      trends,
      // Legacy format
      approvals: approvalStats,
      batches: batchStats,
      publishedSkus: overview.published,
    })
  } catch (error) {
    console.error('Stats API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
