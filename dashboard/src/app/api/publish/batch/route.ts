import { createClient } from '@/lib/supabase/server'
import { publishExpandedVariantsToGoogleSheets } from '@/lib/publishing/google-sheets'
import { publishToShopify } from '@/lib/publishing/shopify'
import { expandVariantsForPublish, validateContentForPublishing } from '@/lib/publishing/expand-variants'
import { uploadProductImage } from '@/lib/publishing/shopify-images'
import { captureBaseline } from '@/lib/baseline-capture'
import {
  buildPublishLineageHashes,
  buildGoogleFinalPayloadSnapshot,
  buildShopifyFinalPayloadSnapshot,
  normalizeSegmentKey,
} from '@/lib/publishing/final-payload'
import { enforcePublishGuard } from '@/lib/auth/publish-guard'
import type {
  BatchPublishRequest,
  BatchPublishResult,
  PublishResult,
  Platform,
  PublishEventInsert,
  VariantIndexRow,
} from '@/lib/publishing/types'
import { NextRequest, NextResponse } from 'next/server'

interface SkuContent {
  master_sku: string
  approval_status?: string
  google_title?: string
  google_description?: string
  google_version?: number
  google_prompt_hash?: string
  shopify_title?: string
  shopify_description?: string
  shopify_version?: number
  shopify_prompt_hash?: string
  offer_ids: string[]
  shopify_product_id?: string
}

type BatchAssignmentStatus = 'pending' | 'success' | 'partial' | 'failed'

interface AssignmentOutcome {
  totalAttempts: number
  failedAttempts: number
  errors: string[]
}

function normalizeBatchStatus(status: string | null | undefined): 'draft' | 'pending' | 'executing' | 'published' | 'partial' | 'failed' {
  if (status === 'ready') return 'pending'
  if (status === 'completed') return 'published'
  if (status === 'pending' || status === 'executing' || status === 'published' || status === 'partial' || status === 'failed') {
    return status
  }
  return 'draft'
}

function publishErrorResponse(
  status: number,
  payload: {
    error: string
    code: string
    step: string
    actionable_message: string
  }
) {
  return NextResponse.json(payload, { status })
}

async function isIdempotentNoop(
  supabase: Awaited<ReturnType<typeof createClient>>,
  args: {
    master_sku: string
    platform: Platform
    environment: 'staging' | 'production'
    title: string | null
    description: string | null
    contentVersion?: number
  }
): Promise<boolean> {
  const { data, error } = await supabase
    .from('publish_events')
    .select('content_version, published_title, published_description')
    .eq('master_sku', args.master_sku)
    .eq('platform', args.platform)
    .eq('environment', args.environment)
    .eq('action', 'publish')
    .eq('status', 'success')
    .order('published_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (error || !data) {
    return false
  }

  if (args.contentVersion !== undefined && args.contentVersion !== null && data.content_version === args.contentVersion) {
    return true
  }

  return (
    (data.published_title || null) === (args.title || null)
    && (data.published_description || null) === (args.description || null)
  )
}

function extractResultReason(result: PublishResult): string | null {
  if (result.error && result.error.trim()) {
    return result.error.trim()
  }

  if (result.details && typeof result.details === 'object') {
    const actionable = (result.details as Record<string, unknown>).actionable_message
    if (typeof actionable === 'string' && actionable.trim()) {
      return actionable.trim()
    }
  }

  return null
}

function resolveAssignmentStatus(outcome: AssignmentOutcome | undefined): BatchAssignmentStatus {
  if (!outcome || outcome.totalAttempts === 0) {
    return 'pending'
  }
  if (outcome.failedAttempts === 0) {
    return 'success'
  }
  if (outcome.failedAttempts === outcome.totalAttempts) {
    return 'failed'
  }
  return 'partial'
}

function extractSegmentLabel(row: Record<string, unknown>): string | null {
  const direct = typeof row.custom_label_0 === 'string' ? row.custom_label_0 : null
  if (direct && direct.trim()) return direct.trim()
  if (row.custom_labels && typeof row.custom_labels === 'object') {
    const labels = row.custom_labels as Record<string, unknown>
    const nested = typeof labels.custom_label_0 === 'string'
      ? labels.custom_label_0
      : (typeof labels.customLabel0 === 'string' ? labels.customLabel0 : null)
    if (nested && nested.trim()) return nested.trim()
  }
  return null
}

async function buildSegmentKeyMap(
  supabase: Awaited<ReturnType<typeof createClient>>,
  skuList: string[],
): Promise<Map<string, string | null>> {
  const segmentMap = new Map<string, string | null>()
  for (const sku of skuList) {
    segmentMap.set(sku, null)
  }

  try {
    const { data, error } = await supabase
      .from('variant_index')
      .select('master_sku, custom_label_0, custom_labels')
      .in('master_sku', skuList)

    if (error || !data) return segmentMap

    for (const row of data as Record<string, unknown>[]) {
      const sku = typeof row.master_sku === 'string' ? row.master_sku : null
      if (!sku || segmentMap.get(sku)) continue
      const label = extractSegmentLabel(row)
      const key = normalizeSegmentKey(label)
      if (key) {
        segmentMap.set(sku, key)
      }
    }
  } catch {
    // Ignore lineage enrichment failures to keep publish path non-blocking.
  }

  return segmentMap
}

function extractValidationFailureDetails(
  validation: Awaited<ReturnType<typeof validateContentForPublishing>>,
  fallbackCode: string,
  fallbackAction: string
): { code: string; actionable_message: string; validation_errors: string[]; validation_issues: unknown[] } {
  const primaryIssue = validation.issues[0]
  return {
    code: primaryIssue?.code ?? fallbackCode,
    actionable_message: primaryIssue?.actionable_message ?? fallbackAction,
    validation_errors: validation.errors,
    validation_issues: validation.issues,
  }
}

async function updateAssignmentStatus(
  supabase: Awaited<ReturnType<typeof createClient>>,
  args: {
    batchId: string
    sku: string
    status: BatchAssignmentStatus
    errorMessage: string | null
  }
): Promise<void> {
  const { error } = await supabase
    .from('batch_sku_assignments')
    .update({
      status: args.status,
      error_message: args.errorMessage,
    })
    .eq('batch_id', args.batchId)
    .eq('master_sku', args.sku)

  if (error) {
    throw new Error(`Failed to update assignment ${args.sku}: ${error.message}`)
  }
}

/**
 * POST /api/publish/batch
 *
 * Orchestrate publishing a batch of SKUs across multiple platforms.
 *
 * Request body:
 * {
 *   batch_id: string,                              // Required: Batch identifier
 *   platforms: ['google', 'shopify'],              // Required: Platforms to publish to
 *   environment: 'staging' | 'production',         // Required
 * }
 *
 * Workflow:
 * 1. Get all SKUs in batch from batch_sku_assignments
 * 2. Get content for each SKU from generated_content
 * 3. Get offer IDs and shopify_product_id from variant_index
 * 4. Call platform-specific publish functions
 * 5. Log results to publish_events
 * 6. Update batch status
 * 7. Return detailed results per SKU
 */
export async function POST(request: NextRequest) {
  try {
    const guard = enforcePublishGuard(request)
    if (!guard.allowed) {
      return guard.response!
    }

    const body = (await request.json()) as BatchPublishRequest

    // Validate required fields
    const { batch_id, platforms, environment } = body

    if (!batch_id) {
      return publishErrorResponse(400, {
        error: 'batch_id is required',
        code: 'batch_publish_missing_batch_id',
        step: 'request_validation',
        actionable_message: 'Provide batch_id in the request body and retry.',
      })
    }

    if (!platforms || !Array.isArray(platforms) || platforms.length === 0) {
      return publishErrorResponse(400, {
        error: 'platforms array is required and must not be empty',
        code: 'batch_publish_missing_platforms',
        step: 'request_validation',
        actionable_message: 'Select at least one platform to publish.',
      })
    }

    const validPlatforms: Platform[] = ['google', 'shopify', 'bing']
    for (const platform of platforms) {
      if (!validPlatforms.includes(platform)) {
        return publishErrorResponse(400, {
          error: `Invalid platform: ${platform}. Must be one of: ${validPlatforms.join(', ')}`,
          code: 'batch_publish_invalid_platform',
          step: 'request_validation',
          actionable_message: `Use one of: ${validPlatforms.join(', ')}.`,
        })
      }
    }

    if (!environment || !['staging', 'production'].includes(environment)) {
      return publishErrorResponse(400, {
        error: "environment must be 'staging' or 'production'",
        code: 'batch_publish_invalid_environment',
        step: 'request_validation',
        actionable_message: "Set environment to either 'staging' or 'production'.",
      })
    }

    const supabase = await createClient()

    const { data: batchRecord, error: batchLookupError } = await supabase
      .from('publish_batches')
      .select('batch_id, status')
      .eq('batch_id', batch_id)
      .maybeSingle()

    if (batchLookupError) {
      return publishErrorResponse(500, {
        error: `Failed to load batch ${batch_id}: ${batchLookupError.message}`,
        code: 'batch_publish_lookup_failed',
        step: 'batch_lookup',
        actionable_message: 'Retry publish. If this persists, inspect publish_batches table access.',
      })
    }

    if (!batchRecord) {
      return publishErrorResponse(404, {
        error: `Batch ${batch_id} was not found`,
        code: 'batch_publish_not_found',
        step: 'batch_lookup',
        actionable_message: 'Create the batch first, then retry publish.',
      })
    }

    const batchStatus = normalizeBatchStatus(batchRecord.status)
    if (batchStatus === 'executing') {
      return publishErrorResponse(409, {
        error: `Batch ${batch_id} is already executing`,
        code: 'batch_publish_already_executing',
        step: 'batch_state_check',
        actionable_message: 'Wait for the active execution to finish before retrying.',
      })
    }

    // 1. Get all SKUs in the batch
    const { data: assignments, error: assignmentError } = await supabase
      .from('batch_sku_assignments')
      .select('master_sku')
      .eq('batch_id', batch_id)

    if (assignmentError) {
      return publishErrorResponse(500, {
        error: `Failed to fetch batch assignments: ${assignmentError.message}`,
        code: 'batch_publish_assignment_lookup_failed',
        step: 'batch_assignment_lookup',
        actionable_message: 'Retry publish. If this persists, inspect batch_sku_assignments access.',
      })
    }

    if (!assignments || assignments.length === 0) {
      return publishErrorResponse(404, {
        error: `No SKUs found in batch ${batch_id}`,
        code: 'batch_publish_empty_batch',
        step: 'batch_assignment_lookup',
        actionable_message: 'Add SKUs to the batch before publishing.',
      })
    }

    const skuList = assignments.map((a) => a.master_sku)

    // Update batch status to 'executing'
    await supabase
      .from('publish_batches')
      .update({ status: 'executing' })
      .eq('batch_id', batch_id)

    // Reset assignment rows for this execution so retries are deterministic.
    const { error: resetAssignmentsError } = await supabase
      .from('batch_sku_assignments')
      .update({
        status: 'pending',
        error_message: null,
      })
      .eq('batch_id', batch_id)

    if (resetAssignmentsError) {
      return publishErrorResponse(500, {
        error: `Failed to reset batch assignment status rows: ${resetAssignmentsError.message}`,
        code: 'batch_publish_assignment_reset_failed',
        step: 'batch_assignment_reset',
        actionable_message: 'Retry publish. If this persists, inspect batch_sku_assignments write access.',
      })
    }

    // 2. Get APPROVED content for each SKU (not candidate_content)
    const { data: contentData, error: contentError } = await supabase
      .from('generated_content')
      .select('master_sku, platform, content_type, approved_content, approved_version, generation_prompt_hash')
      .in('master_sku', skuList)

    if (contentError) {
      console.error('Error fetching generated content:', contentError)
    }

    // 2b. Get approval status for each SKU
    const { data: approvalData, error: approvalError } = await supabase
      .from('sku_approvals')
      .select('master_sku, approval_status')
      .in('master_sku', skuList)

    if (approvalError) {
      console.error('Error fetching approvals:', approvalError)
    }

    const approvalMap = new Map<string, string>()
    approvalData?.forEach((a) => {
      approvalMap.set(a.master_sku, a.approval_status)
    })

    // 3. Get variant index data (offer IDs and Shopify product IDs)
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('gmc_offer_id, master_sku, shopify_product_id')
      .in('master_sku', skuList)

    if (variantError) {
      console.error('Error fetching variant index:', variantError)
    }

    // Build content map for each SKU
    const skuContentMap = new Map<string, SkuContent>()

    // Initialize with SKUs and approval status
    for (const sku of skuList) {
      skuContentMap.set(sku, {
        master_sku: sku,
        approval_status: approvalMap.get(sku),
        offer_ids: [],
      })
    }

    // Add APPROVED content data (not candidate_content!)
    if (contentData) {
      for (const row of contentData as {
        master_sku: string
        platform: string
        content_type: string
        approved_content: string | null
        approved_version: number | null
        generation_prompt_hash: string | null
      }[]) {
        const content = skuContentMap.get(row.master_sku)
        if (!content) continue

        if (row.content_type === 'title') {
          if (row.platform === 'google') {
            content.google_title = row.approved_content || undefined
            content.google_version = row.approved_version || undefined
            content.google_prompt_hash = row.generation_prompt_hash || undefined
          } else if (row.platform === 'shopify') {
            content.shopify_title = row.approved_content || undefined
            content.shopify_version = row.approved_version || undefined
            content.shopify_prompt_hash = row.generation_prompt_hash || undefined
          }
        } else if (row.content_type === 'description') {
          if (row.platform === 'google') {
            content.google_description = row.approved_content || undefined
            content.google_prompt_hash = row.generation_prompt_hash || content.google_prompt_hash
          } else if (row.platform === 'shopify') {
            content.shopify_description = row.approved_content || undefined
            content.shopify_prompt_hash = row.generation_prompt_hash || content.shopify_prompt_hash
          }
        }
      }
    }

    // Add variant data
    if (variantData) {
      for (const variant of variantData as VariantIndexRow[]) {
        const content = skuContentMap.get(variant.master_sku)
        if (!content) continue

        if (variant.gmc_offer_id) {
          content.offer_ids.push(variant.gmc_offer_id)
        }
        // Use the first Shopify product ID found
        if (variant.shopify_product_id && !content.shopify_product_id) {
          content.shopify_product_id = variant.shopify_product_id
        }
      }
    }

    // 4. Execute publishing for each platform and SKU
    const results: PublishResult[] = []
    const assignmentOutcomes = new Map<string, AssignmentOutcome>()
    const segmentKeyMap = await buildSegmentKeyMap(supabase, skuList)
    let successCount = 0
    let failedCount = 0

    const recordResult = (result: PublishResult): void => {
      results.push(result)
      const current = assignmentOutcomes.get(result.master_sku) || {
        totalAttempts: 0,
        failedAttempts: 0,
        errors: [],
      }
      current.totalAttempts += 1
      if (!result.success) {
        current.failedAttempts += 1
        const reason = extractResultReason(result)
        if (reason) {
          current.errors.push(reason)
        }
      }
      assignmentOutcomes.set(result.master_sku, current)
    }

    for (const sku of skuList) {
      const content = skuContentMap.get(sku)
      if (!content) continue

      // Publish to Google
      if (platforms.includes('google')) {
        const validation = await validateContentForPublishing(sku, 'google')

        // Check approval status first
        if (content.approval_status !== 'approved') {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            details: {
              code: 'batch_publish_requires_approved_sku',
              actionable_message: 'Approve this SKU in Review before publishing.',
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else if (!validation.isValid) {
          const details = extractValidationFailureDetails(
            validation,
            'batch_publish_google_validation_failed',
            'Resolve Google content parity/policy issues before publishing this SKU.'
          )
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: validation.errors.join('; '),
            details: {
              ...details,
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: validation.errors.join('; '),
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else if (!validation.title || !validation.description) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: 'Missing approved title or description for Google',
            details: {
              code: 'batch_publish_missing_approved_content_google',
              actionable_message: 'Approve Google title/description content before publishing.',
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          // Log failed event
          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'Missing approved title or description',
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else if (content.offer_ids.length === 0) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: 'No GMC offer IDs found',
            details: {
              code: 'batch_publish_missing_offer_ids',
              actionable_message: 'Sync variant mappings so this SKU has GMC offer IDs.',
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'No GMC offer IDs found',
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else {
          try {
            const googleNoop = await isIdempotentNoop(supabase, {
              master_sku: sku,
              platform: 'google',
              environment,
              title: validation.title,
              description: validation.description,
              contentVersion: content.google_version,
            })

            if (googleNoop) {
              const noopResult: PublishResult = {
                success: true,
                master_sku: sku,
                platform: 'google',
                details: {
                  state: 'no_change',
                  idempotent: true,
                  reason: 'Already published this content snapshot.',
                },
              }
              recordResult(noopResult)
              successCount++
            } else {
              // Capture 30-day performance baseline BEFORE publishing (allows measuring lift)
              try {
                await captureBaseline(supabase, sku, 'google')
                console.log(`Captured baseline for ${sku} before Google publish`)
              } catch (baselineError) {
                // Non-fatal: Log warning but continue with publish
                console.warn(`Failed to capture baseline for ${sku}:`, baselineError)
              }

              // Migrate approved images to Shopify CDN (if not already migrated)
              // Non-blocking - log errors but continue with publish
              try {
                await migrateImagesForPublish(supabase, sku)
              } catch (error) {
                console.error('Image CDN migration failed (non-blocking):', error)
              }

              // Expand templates for each variant (replaces {FINISH_NAME} with actual finish)
              const expandedVariants = await expandVariantsForPublish({
                master_sku: sku,
                platform: 'google',
                approved_title: validation.title,
                approved_description: validation.description,
              })

              // Publish expanded variants - each with unique title/description
              const googleResult = await publishExpandedVariantsToGoogleSheets(
                expandedVariants.map((v) => ({
                  gmc_offer_id: v.gmc_offer_id,
                  master_sku: v.master_sku,
                  finish_code: v.finish_code,
                  title: v.title,
                  description: v.description,
                  image_url: v.image_url,
                })),
                environment
              )
              const googleSnapshot = buildGoogleFinalPayloadSnapshot(
                expandedVariants.map((v) => ({
                  gmc_offer_id: v.gmc_offer_id,
                  finish: v.finish,
                  finish_code: v.finish_code,
                  title: v.title,
                  description: v.description,
                  image_url: v.image_url,
                }))
              )

              const result: PublishResult = {
                success: googleResult.success,
                master_sku: sku,
                platform: 'google',
                error: googleResult.success ? undefined : googleResult.errors.join('; '),
                details: {
                  updated_count: googleResult.updated_count,
                  appended_count: googleResult.appended_count,
                  offer_ids: content.offer_ids,
                  variant_count: expandedVariants.length,
                },
              }
              recordResult(result)

              if (googleResult.success) {
                successCount++
              } else {
                failedCount++
              }

              await logPublishEvent(supabase, {
                master_sku: sku,
                platform: 'google',
                environment,
                action: 'publish',
                status: googleResult.success ? 'success' : 'failed',
                error_message: googleResult.success ? undefined : googleResult.errors.join('; '),
                batch_id,
                // Include content snapshot for rollback capability
                published_title: validation.title,
                published_description: validation.description,
                variant_count: expandedVariants.length,
                content_version: content.google_version,
                final_payload_snapshot: googleSnapshot,
                ...buildPublishLineageHashes({
                  finalPayloadSnapshot: googleSnapshot,
                  promptHash: content.google_prompt_hash,
                  evidenceInput: {
                    master_sku: sku,
                    platform: 'google',
                    title: validation.title,
                    description: validation.description,
                    offer_ids: content.offer_ids,
                    variant_count: expandedVariants.length,
                  },
                  segmentKey: segmentKeyMap.get(sku) || null,
                }),
                published_by: guard.actorId || undefined,
              })
            }
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            const result: PublishResult = {
              success: false,
              master_sku: sku,
              platform: 'google',
              error: errorMsg,
              details: {
                code: 'batch_publish_google_failed',
                actionable_message: 'Inspect Google Sheets publish logs and retry this SKU.',
                state: 'failed',
              },
            }
            recordResult(result)
            failedCount++

            await logPublishEvent(supabase, {
              master_sku: sku,
              platform: 'google',
              environment,
              action: 'publish',
              status: 'failed',
              error_message: errorMsg,
              batch_id,
              published_by: guard.actorId || undefined,
            })
          }
        }
      }

      // Publish to Shopify
      if (platforms.includes('shopify')) {
        const validation = await validateContentForPublishing(sku, 'shopify')

        // Check approval status first
        if (content.approval_status !== 'approved') {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            details: {
              code: 'batch_publish_requires_approved_sku',
              actionable_message: 'Approve this SKU in Review before publishing.',
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else if (!validation.isValid) {
          const details = extractValidationFailureDetails(
            validation,
            'batch_publish_shopify_validation_failed',
            'Resolve Shopify content policy issues before publishing this SKU.'
          )
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: validation.errors.join('; '),
            details: {
              ...details,
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: validation.errors.join('; '),
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else if (!content.shopify_product_id) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: 'No Shopify product ID found',
            details: {
              code: 'batch_publish_missing_shopify_product_id',
              actionable_message: 'Sync variant_index so this SKU is linked to a Shopify product ID.',
              state: 'failed',
            },
          }
          recordResult(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'No Shopify product ID found',
            batch_id,
            published_by: guard.actorId || undefined,
          })
        } else {
          if (!validation.title || !validation.description) {
            const result: PublishResult = {
              success: false,
              master_sku: sku,
              platform: 'shopify',
              error: 'Missing approved title or description for Shopify',
              details: {
                code: 'batch_publish_missing_approved_content_shopify',
                actionable_message: 'Approve Shopify title/description content before publishing.',
                state: 'failed',
              },
            }
            recordResult(result)
            failedCount++

            await logPublishEvent(supabase, {
              master_sku: sku,
              platform: 'shopify',
              environment,
              action: 'publish',
              status: 'failed',
              error_message: 'Missing approved title or description',
              batch_id,
              published_by: guard.actorId || undefined,
            })
            continue
          }
          try {
            const shopifyNoop = await isIdempotentNoop(supabase, {
              master_sku: sku,
              platform: 'shopify',
              environment,
              title: validation.title,
              description: validation.description,
              contentVersion: content.shopify_version || content.google_version,
            })

            if (shopifyNoop) {
              const noopResult: PublishResult = {
                success: true,
                master_sku: sku,
                platform: 'shopify',
                details: {
                  state: 'no_change',
                  idempotent: true,
                  reason: 'Already published this content snapshot.',
                },
              }
              recordResult(noopResult)
              successCount++
            } else {
              const shopifyResult = await publishToShopify(
                content.shopify_product_id,
                validation.title,
                validation.description,
                environment
              )
              const shopifySnapshot = buildShopifyFinalPayloadSnapshot({
                shopify_product_id: content.shopify_product_id,
                title: validation.title,
                description: validation.description,
              })

              const result: PublishResult = {
                success: shopifyResult.success,
                master_sku: sku,
                platform: 'shopify',
                error: shopifyResult.success ? undefined : shopifyResult.errors.join('; '),
                details: {
                  shopify_product_id: content.shopify_product_id,
                },
              }
              recordResult(result)

              if (shopifyResult.success) {
                successCount++
              } else {
                failedCount++
              }

              await logPublishEvent(supabase, {
                master_sku: sku,
                platform: 'shopify',
                environment,
                action: 'publish',
                status: shopifyResult.success ? 'success' : 'failed',
                error_message: shopifyResult.success ? undefined : shopifyResult.errors.join('; '),
                batch_id,
                // Include content snapshot for rollback capability
                published_title: validation.title,
                published_description: validation.description,
                content_version: content.shopify_version || content.google_version,
                final_payload_snapshot: shopifySnapshot,
                ...buildPublishLineageHashes({
                  finalPayloadSnapshot: shopifySnapshot,
                  promptHash: content.shopify_prompt_hash,
                  evidenceInput: {
                    master_sku: sku,
                    platform: 'shopify',
                    title: validation.title,
                    description: validation.description,
                    shopify_product_id: content.shopify_product_id,
                  },
                  segmentKey: segmentKeyMap.get(sku) || null,
                }),
                published_by: guard.actorId || undefined,
              })
            }
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            const result: PublishResult = {
              success: false,
              master_sku: sku,
              platform: 'shopify',
              error: errorMsg,
              details: {
                code: 'batch_publish_shopify_failed',
                actionable_message: 'Inspect Shopify publish logs and retry this SKU.',
                state: 'failed',
              },
            }
            recordResult(result)
            failedCount++

            await logPublishEvent(supabase, {
              master_sku: sku,
              platform: 'shopify',
              environment,
              action: 'publish',
              status: 'failed',
              error_message: errorMsg,
              batch_id,
              published_by: guard.actorId || undefined,
            })
          }
        }
      }

      // Bing publishing deferred - would need XML feed generation
      if (platforms.includes('bing')) {
        const result: PublishResult = {
          success: false,
          master_sku: sku,
          platform: 'bing',
          error: 'Bing publishing not yet implemented in dashboard',
          details: {
            code: 'batch_publish_bing_not_implemented',
            actionable_message: 'Use Google/Shopify publish for now. Bing support is not implemented yet.',
            state: 'failed',
          },
        }
        recordResult(result)
        failedCount++

        await logPublishEvent(supabase, {
          master_sku: sku,
          platform: 'bing',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'Bing publishing not yet implemented',
          batch_id,
          published_by: guard.actorId || undefined,
        })
      }
    }

    // 5.5 Persist per-SKU assignment status for operator visibility and retry safety.
    for (const sku of skuList) {
      const outcome = assignmentOutcomes.get(sku)
      const assignmentStatus = resolveAssignmentStatus(outcome)
      const uniqueErrors = outcome ? [...new Set(outcome.errors)] : []
      const errorMessage = uniqueErrors.length > 0 ? uniqueErrors.slice(0, 3).join(' | ') : null

      await updateAssignmentStatus(supabase, {
        batchId: batch_id,
        sku,
        status: assignmentStatus,
        errorMessage,
      })
    }

    // 6. Update batch status based on results
    const allFailed = successCount === 0 && failedCount > 0
    const allSucceeded = failedCount === 0 && successCount > 0
    const finalBatchStatus = allFailed ? 'failed' : allSucceeded ? 'published' : 'partial'

    console.log(`[publishBatch] Updating batch status: ${finalBatchStatus}, success=${successCount}, failed=${failedCount}`)

    const { error: updateError } = await supabase
      .from('publish_batches')
      .update({
        status: finalBatchStatus,
        executed_at: new Date().toISOString(),
        success_count: successCount,
        failed_count: failedCount,
      })
      .eq('batch_id', batch_id)

    if (updateError) {
      console.error(`[publishBatch] Failed to update batch status:`, updateError)
      throw new Error(`Failed to update batch status: ${updateError.message}`)
    }

    console.log(`[publishBatch] Batch status updated successfully to ${finalBatchStatus}`)

    // 7. Return detailed results
    const batchResult: BatchPublishResult = {
      success: failedCount === 0,
      batch_id,
      environment,
      total_skus: skuList.length,
      successful_skus: successCount,
      failed_skus: failedCount,
      results,
    }

    return NextResponse.json(batchResult)
  } catch (error) {
    console.error('Batch publish error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return publishErrorResponse(500, {
      error: message,
      code: 'batch_publish_unhandled_exception',
      step: 'route_exception',
      actionable_message: 'Retry batch publish once. If it persists, inspect API logs for failing SKUs.',
    })
  }
}

/**
 * Helper function to log publish events to Supabase.
 */
async function logPublishEvent(
  supabase: Awaited<ReturnType<typeof createClient>>,
  event: PublishEventInsert
): Promise<void> {
  // FEED-04: Enforce prompt_hash for new successful publish events (forward-only).
  // Content versioning linkage requires prompt_hash to connect publish -> generated_content -> prompt version.
  // Legacy events with NULL prompt_hash are unaffected. Failed events don't require prompt_hash.
  if (event.status === 'success' && (!event.prompt_hash || !event.prompt_hash.trim())) {
    throw new Error(
      `[FEED-04] Cannot publish without prompt_hash for ${event.master_sku}/${event.platform}. ` +
      `Content versioning linkage required. Ensure generated_content.generation_prompt_hash is populated.`
    )
  }

  try {
    const payload = {
      ...event,
      published_at: new Date().toISOString(),
    }
    const { error } = await supabase.from('publish_events').insert(payload)
    if (
      error
      && (
        event.final_payload_snapshot
        || event.final_payload_hash
        || event.prompt_hash
        || event.evidence_hash
        || event.segment_key
      )
      && /final_payload_snapshot|final_payload_hash|prompt_hash|evidence_hash|segment_key/i.test(error.message)
    ) {
      // Legacy fallback: strip new columns but PRESERVE prompt_hash if available
      const legacyPayload: Record<string, unknown> = { ...payload }
      delete legacyPayload.final_payload_snapshot
      delete legacyPayload.final_payload_hash
      delete legacyPayload.evidence_hash
      delete legacyPayload.segment_key
      // Keep prompt_hash in the retry — only strip if it was part of the error
      if (/prompt_hash/i.test(error.message)) {
        delete legacyPayload.prompt_hash
      }
      await supabase.from('publish_events').insert(legacyPayload)
    }
  } catch (error) {
    console.error('Failed to log publish event:', error)
    // Re-throw FEED-04 errors so publish is properly rejected
    if (error instanceof Error && error.message.includes('[FEED-04]')) {
      throw error
    }
  }
}

/**
 * Migrate approved images to Shopify CDN before publishing.
 * Only migrates images that are approved but not yet on CDN.
 *
 * Lifecycle: Supabase Storage → Shopify CDN → Google Sheets
 */
async function migrateImagesForPublish(
  supabase: Awaited<ReturnType<typeof createClient>>,
  masterSku: string
): Promise<void> {
  console.log(`[CDN Migration] Starting for ${masterSku}`)

  // Get product-level images needing migration
  const { data: productImages } = await supabase
    .from('product_lifestyle_images')
    .select('id, image_url, shopify_product_id, master_sku')
    .eq('master_sku', masterSku)
    .eq('approval_status', 'approved')
    .is('shopify_cdn_url', null)

  // Get variant-level images needing migration
  const { data: variantImages } = await supabase
    .from('variant_lifestyle_images')
    .select('id, image_url, gmc_offer_id, master_sku, finish')
    .eq('master_sku', masterSku)
    .eq('approval_status', 'approved')
    .is('shopify_cdn_url', null)

  let migratedCount = 0
  let errorCount = 0

  // Migrate product images
  for (const img of productImages || []) {
    try {
      console.log(`[CDN Migration] Uploading product image ${img.id}`)
      const result = await uploadProductImage(
        img.image_url,
        img.shopify_product_id,
        `${img.master_sku} product image`
      )

      await supabase
        .from('product_lifestyle_images')
        .update({
          shopify_media_id: result.mediaId,
          shopify_cdn_url: result.cdnUrl,
          migrated_to_shopify_at: new Date().toISOString(),
        })
        .eq('id', img.id)

      migratedCount++
      console.log(`[CDN Migration] ✓ Product image ${img.id} migrated`)
    } catch (error) {
      console.error(`[CDN Migration] ✗ Failed to migrate product image ${img.id}:`, error)
      errorCount++
    }
  }

  // Migrate variant images
  for (const img of variantImages || []) {
    try {
      // Lookup Shopify IDs from variant_index
      const { data: variant } = await supabase
        .from('variant_index')
        .select('shopify_product_id, shopify_variant_id')
        .eq('gmc_offer_id', img.gmc_offer_id)
        .single()

      if (!variant?.shopify_product_id) {
        console.warn(`[CDN Migration] No Shopify mapping for ${img.gmc_offer_id}`)
        errorCount++
        continue
      }

      console.log(`[CDN Migration] Uploading variant image ${img.id} for ${img.gmc_offer_id}`)
      // Use uploadProductImage instead of uploadVariantImage to avoid "variant already has media" error
      // Lifestyle images don't need variant-specific association - they're just for GMC feed CDN hosting
      const result = await uploadProductImage(
        img.image_url,
        variant.shopify_product_id,
        `${img.master_sku} - ${img.finish}`
      )

      await supabase
        .from('variant_lifestyle_images')
        .update({
          shopify_media_id: result.mediaId,
          shopify_cdn_url: result.cdnUrl,
          migrated_to_shopify_at: new Date().toISOString(),
        })
        .eq('id', img.id)

      migratedCount++
      console.log(`[CDN Migration] ✓ Variant image ${img.id} migrated`)
    } catch (error) {
      console.error(`[CDN Migration] ✗ Failed to migrate variant image ${img.id}:`, error)
      errorCount++
    }
  }

  console.log(`[CDN Migration] Complete: ${migratedCount} migrated, ${errorCount} errors`)
}
