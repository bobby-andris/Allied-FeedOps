import { PublishBatch } from '@/lib/supabase/types'

export type BatchStatus = PublishBatch['status']
export type AssignmentStatus = 'pending' | 'success' | 'partial' | 'failed' | null

export interface BatchAssignmentLike {
  master_sku: string
  status: AssignmentStatus
  error_message: string | null
}

export interface PublishEventLike {
  master_sku: string
  status: 'success' | 'failed'
  error_message: string | null
  published_at: string | null
}

export interface BatchSummary {
  status: BatchStatus
  skuCount: number
  successCount: number
  failedCount: number
  pendingCount: number
}

export function normalizeBatchStatus(status: string | null | undefined): BatchStatus {
  if (!status) return 'draft'
  if (status === 'ready') return 'pending'
  if (status === 'completed') return 'published'
  if (status === 'pending' || status === 'executing' || status === 'published' || status === 'partial' || status === 'failed') {
    return status
  }
  return 'draft'
}

function toTimestamp(value: string | null | undefined): number {
  if (!value) return 0
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function latestEventsBySku(events: PublishEventLike[]): Map<string, PublishEventLike> {
  return events.reduce((acc, event) => {
    const existing = acc.get(event.master_sku)
    if (!existing || toTimestamp(event.published_at) > toTimestamp(existing.published_at)) {
      acc.set(event.master_sku, event)
    }
    return acc
  }, new Map<string, PublishEventLike>())
}

export function hydrateAssignmentsWithEventFailures<T extends BatchAssignmentLike>(
  assignments: T[],
  events: PublishEventLike[]
): T[] {
  const latestEventMap = latestEventsBySku(events)

  return assignments.map((assignment) => {
    const latestEvent = latestEventMap.get(assignment.master_sku)
    const resolvedStatus: AssignmentStatus = assignment.status
      ?? (latestEvent ? (latestEvent.status === 'success' ? 'success' : 'failed') : null)

    const resolvedErrorMessage = assignment.error_message
      ?? (
        latestEvent?.status === 'failed'
          ? latestEvent.error_message
          : null
      )

    return {
      ...assignment,
      status: resolvedStatus,
      error_message: resolvedErrorMessage,
    }
  })
}

export function deriveBatchSummary(
  batchStatus: string | null | undefined,
  assignments: BatchAssignmentLike[]
): BatchSummary {
  const normalizedBatchStatus = normalizeBatchStatus(batchStatus)
  const skuCount = assignments.length

  if (skuCount === 0) {
    return {
      status: normalizedBatchStatus,
      skuCount: 0,
      successCount: 0,
      failedCount: 0,
      pendingCount: 0,
    }
  }

  const successCount = assignments.filter((assignment) => assignment.status === 'success').length
  const hardFailedCount = assignments.filter((assignment) => assignment.status === 'failed').length
  const partialCount = assignments.filter((assignment) => assignment.status === 'partial').length
  const failedCount = hardFailedCount + partialCount
  const pendingCount = skuCount - successCount - failedCount

  if (pendingCount === 0) {
    if (failedCount === 0) {
      return {
        status: 'published',
        skuCount,
        successCount,
        failedCount,
        pendingCount,
      }
    }
    if (successCount === 0 && partialCount === 0) {
      return {
        status: 'failed',
        skuCount,
        successCount,
        failedCount,
        pendingCount,
      }
    }
    return {
      status: 'partial',
      skuCount,
      successCount,
      failedCount,
      pendingCount,
    }
  }

  const inProgressStatus = normalizedBatchStatus === 'draft'
    ? 'draft'
    : normalizedBatchStatus === 'executing'
      ? 'executing'
      : 'pending'

  return {
    status: inProgressStatus,
    skuCount,
    successCount,
    failedCount,
    pendingCount,
  }
}
