import { createClient } from '@/lib/supabase/server'
import { publishExpandedVariantsToGoogleSheets } from '@/lib/publishing/google-sheets'
import { publishToShopify } from '@/lib/publishing/shopify'
import { expandVariantsForPublish, validateContentForPublishing } from '@/lib/publishing/expand-variants'
import { uploadProductImage } from '@/lib/publishing/shopify-images'
import {
  buildPublishLineageHashes,
  buildBingFinalPayloadSnapshot,
  buildGoogleFinalPayloadSnapshot,
  buildShopifyFinalPayloadSnapshot,
  normalizeSegmentKey,
} from '@/lib/publishing/final-payload'
import type { Platform, PublishEventInsert } from '@/lib/publishing/types'
import { computePlatformReadiness, validateRequestedPlatformsReady } from '@/lib/publishing/platform-readiness'
import { enforcePublishGuard } from '@/lib/auth/publish-guard'
import { NextRequest, NextResponse } from 'next/server'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'

interface SkuPublishRequest {
  master_sku: string
  platforms: Platform[]
  environment: 'staging' | 'production'
}

interface PlatformResult {
  platform: Platform
  success: boolean
  error?: string
  code?: string
  actionable_message?: string
  state?: 'completed' | 'no_change' | 'failed'
  idempotent?: boolean
  details?: Record<string, unknown>
}

function toValidationFailureResult(
  platform: Platform,
  validation: Awaited<ReturnType<typeof validateContentForPublishing>>
): PlatformResult {
  const primaryIssue = validation.issues[0]
  return {
    platform,
    success: false,
    error: validation.errors.join('; '),
    code: primaryIssue?.code ?? `publish_${platform}_validation_failed`,
    state: 'failed',
    actionable_message: primaryIssue?.actionable_message
      ?? `Resolve ${platform} content validation issues before publishing.`,
    details: {
      validation_errors: validation.errors,
      validation_issues: validation.issues,
    },
  }
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
  }
): Promise<boolean> {
  const { data, error } = await supabase
    .from('publish_events')
    .select('published_title, published_description')
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

  return (
    (data.published_title || null) === (args.title || null)
    && (data.published_description || null) === (args.description || null)
  )
}

function isApprovedFlag(value: unknown): boolean {
  return value === true || value === 1 || value === '1'
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

async function resolveSegmentKeyForSku(
  supabase: Awaited<ReturnType<typeof createClient>>,
  masterSku: string,
): Promise<string | null> {
  try {
    const { data, error } = await supabase
      .from('variant_index')
      .select('custom_label_0, custom_labels')
      .eq('master_sku', masterSku)
      .limit(50)

    if (error || !data || data.length === 0) {
      return null
    }

    for (const row of data as Record<string, unknown>[]) {
      const label = extractSegmentLabel(row)
      const segmentKey = normalizeSegmentKey(label)
      if (segmentKey) return segmentKey
    }
    return null
  } catch {
    return null
  }
}

async function getPlatformReadiness(
  supabase: Awaited<ReturnType<typeof createClient>>,
  masterSku: string,
) {
  const [contentResult, variantResult, variantApprovalResult, variantImageResult, productImageResult] = await Promise.all([
    supabase
      .from('generated_content')
      .select('platform, content_type, approved_content')
      .eq('master_sku', masterSku)
      .in('platform', ['google', 'bing', 'shopify'])
      .in('content_type', ['title', 'description']),
    supabase
      .from('variant_index')
      .select('finish')
      .eq('master_sku', masterSku),
    supabase
      .from('variant_approvals')
      .select('finish, title_approved, description_approved, approval_status')
      .eq('master_sku', masterSku),
    supabase
      .from('variant_lifestyle_images')
      .select('finish')
      .eq('master_sku', masterSku)
      .eq('approval_status', 'approved')
      .eq('user_selected', true),
    supabase
      .from('product_lifestyle_images')
      .select('id')
      .eq('master_sku', masterSku)
      .eq('approval_status', 'approved')
      .eq('user_selected', true)
      .limit(1)
      .maybeSingle(),
  ])

  if (contentResult.error) {
    throw new Error(`readiness_content_lookup_failed: ${contentResult.error.message}`)
  }
  if (variantResult.error) {
    throw new Error(`readiness_variant_lookup_failed: ${variantResult.error.message}`)
  }
  if (variantApprovalResult.error) {
    throw new Error(`readiness_variant_approval_lookup_failed: ${variantApprovalResult.error.message}`)
  }
  if (variantImageResult.error) {
    throw new Error(`readiness_variant_image_lookup_failed: ${variantImageResult.error.message}`)
  }
  if (productImageResult.error) {
    throw new Error(`readiness_product_image_lookup_failed: ${productImageResult.error.message}`)
  }

  const contentFlags: Record<Platform, { titleApproved: boolean; descriptionApproved: boolean }> = {
    google: { titleApproved: false, descriptionApproved: false },
    bing: { titleApproved: false, descriptionApproved: false },
    shopify: { titleApproved: false, descriptionApproved: false },
  }

  for (const row of contentResult.data || []) {
    if (!row.approved_content || row.approved_content.trim().length === 0) continue
    if (row.content_type === 'title') {
      contentFlags[row.platform as Platform].titleApproved = true
    } else if (row.content_type === 'description') {
      contentFlags[row.platform as Platform].descriptionApproved = true
    }
  }

  const requiredFinishes = new Set(
    (variantResult.data || [])
      .map((row) => row.finish)
      .filter((finish): finish is string => Boolean(finish))
  )

  const approvedVariantFinishes = new Set(
    (variantApprovalResult.data || [])
      .filter((row) =>
        row.finish
        && row.approval_status === 'approved'
        && isApprovedFlag(row.title_approved)
        && isApprovedFlag(row.description_approved)
      )
      .map((row) => row.finish as string)
  )

  const variantImageFinishes = new Set(
    (variantImageResult.data || [])
      .map((row) => row.finish)
      .filter((finish): finish is string => Boolean(finish))
  )

  const variantApprovalsReady = requiredFinishes.size > 0
    && approvedVariantFinishes.size >= requiredFinishes.size
  const variantImagesReady = requiredFinishes.size > 0
    && variantImageFinishes.size >= requiredFinishes.size
  const shopifyMasterImageReady = Boolean(productImageResult.data?.id)

  return computePlatformReadiness({
    content: contentFlags,
    variantApprovalsReady,
    variantImagesReady,
    shopifyMasterImageReady,
  })
}

/**
 * POST /api/publish/sku
 *
 * Publish approved content for a single SKU to selected platforms.
 *
 * Request body:
 * {
 *   master_sku: string,                             // Required: SKU identifier
 *   platforms: ['google', 'shopify'],               // Required: Platforms to publish to
 *   environment: 'staging' | 'production',          // Required
 * }
 *
 * Workflow:
 * 1. Compute deterministic per-platform readiness from stored state
 * 2. Validate requested platform subset is ready
 * 3. Fetch approved_content from generated_content
 * 4. Get variant data from variant_index
 * 5. Call platform-specific publish functions
 * 6. Log results to publish_events
 * 7. Return detailed results
 */
export async function POST(request: NextRequest) {
  try {
    const guard = enforcePublishGuard(request)
    if (!guard.allowed) {
      return guard.response!
    }

    const body = (await request.json()) as SkuPublishRequest

    // Validate required fields
    let { master_sku } = body
    const { platforms, environment } = body

    if (!master_sku) {
      return publishErrorResponse(400, {
        error: 'master_sku is required',
        code: 'publish_missing_master_sku',
        step: 'request_validation',
        actionable_message: 'Provide master_sku in the request body and retry.',
      })
    }

    if (!platforms || !Array.isArray(platforms) || platforms.length === 0) {
      return publishErrorResponse(400, {
        error: 'platforms array is required and must not be empty',
        code: 'publish_missing_platforms',
        step: 'request_validation',
        actionable_message: 'Select at least one platform to publish.',
      })
    }

    const validPlatforms: Platform[] = ['google', 'shopify', 'bing']
    for (const platform of platforms) {
      if (!validPlatforms.includes(platform)) {
        return publishErrorResponse(400, {
          error: `Invalid platform: ${platform}. Must be one of: ${validPlatforms.join(', ')}`,
          code: 'publish_invalid_platform',
          step: 'request_validation',
          actionable_message: `Use one of: ${validPlatforms.join(', ')}.`,
        })
      }
    }

    if (!environment || !['staging', 'production'].includes(environment)) {
      return publishErrorResponse(400, {
        error: "environment must be 'staging' or 'production'",
        code: 'publish_invalid_environment',
        step: 'request_validation',
        actionable_message: "Set environment to either 'staging' or 'production'.",
      })
    }

    const supabase = await createClient()
    const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)
    master_sku = canonicalMasterSku
    const segmentKey = await resolveSegmentKeyForSku(supabase, master_sku)

    const readiness = await getPlatformReadiness(supabase, master_sku)
    const readinessValidation = validateRequestedPlatformsReady(platforms, readiness)
    if (!readinessValidation.ok) {
      return NextResponse.json(
        {
          error: 'One or more requested platforms are not ready for publishing.',
          code: 'publish_platform_not_ready',
          step: 'platform_readiness',
          actionable_message: 'Resolve the readiness blockers for requested platforms, then retry publish.',
          readiness_errors: readinessValidation.errors,
        },
        { status: 409 },
      )
    }

    // 2. Get variant data for this SKU
    const { data: variants, error: variantError } = await supabase
      .from('variant_index')
      .select('gmc_offer_id, shopify_product_id')
      .eq('master_sku', master_sku)

    if (variantError) {
      return publishErrorResponse(500, {
        error: `Failed to fetch variants: ${variantError.message}`,
        code: 'publish_variant_lookup_failed',
        step: 'variant_lookup',
        actionable_message: 'Retry publish. If this persists, check variant_index table health.',
      })
    }

    const offerIds = variants?.map((v) => v.gmc_offer_id).filter(Boolean) || []
    const shopifyProductId = variants?.find((v) => v.shopify_product_id)?.shopify_product_id

    // 3. Migrate approved images to Shopify CDN (if not already migrated)
    // Non-blocking - log errors but continue with publish
    try {
      await migrateImagesForPublish(supabase, master_sku)
    } catch (error) {
      console.error('Image CDN migration failed (non-blocking):', error)
    }

    // 4. Publish to each platform
    const results: PlatformResult[] = []

    // Publish to Google
    if (platforms.includes('google')) {
      const validation = await validateContentForPublishing(master_sku, 'google', {
        requireGlobalSkuApproval: false,
      })

      if (!validation.isValid) {
        const failedResult = toValidationFailureResult('google', validation)
        results.push(failedResult)

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'google',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: validation.errors.join('; '),
          published_by: guard.actorId || undefined,
        })
      } else if (offerIds.length === 0) {
        results.push({
          platform: 'google',
          success: false,
          error: 'No GMC offer IDs found for this SKU',
          code: 'publish_missing_offer_ids',
          state: 'failed',
          actionable_message: 'Sync variant index mappings so this SKU has GMC offer IDs.',
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'google',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No GMC offer IDs found',
          published_by: guard.actorId || undefined,
        })
      } else {
        try {
          const googleNoop = await isIdempotentNoop(supabase, {
            master_sku,
            platform: 'google',
            environment,
            title: validation.title,
            description: validation.description,
          })

          if (googleNoop) {
            results.push({
              platform: 'google',
              success: true,
              state: 'no_change',
              idempotent: true,
              details: { reason: 'Already published this content snapshot.' },
            })
          } else {
          // Expand templates for each variant
          const expandedVariants = await expandVariantsForPublish({
            master_sku,
            platform: 'google',
            approved_title: validation.title!,
            approved_description: validation.description!,
          })

          // Publish expanded variants
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

          results.push({
            platform: 'google',
            success: googleResult.success,
            error: googleResult.success ? undefined : googleResult.errors.join('; '),
            details: {
              updated_count: googleResult.updated_count,
              appended_count: googleResult.appended_count,
              variant_count: expandedVariants.length,
              offer_ids: offerIds,
            },
          })

          await logPublishEvent(supabase, {
            master_sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: googleResult.success ? 'success' : 'failed',
            error_message: googleResult.success ? undefined : googleResult.errors.join('; '),
            published_title: validation.title ?? undefined,
            published_description: validation.description ?? undefined,
            variant_count: expandedVariants.length,
            final_payload_snapshot: googleSnapshot,
            ...buildPublishLineageHashes({
              finalPayloadSnapshot: googleSnapshot,
              promptHash: validation.prompt_hash,
              evidenceInput: {
                master_sku,
                platform: 'google',
                title: validation.title ?? null,
                description: validation.description ?? null,
                offer_ids: offerIds,
                variant_count: expandedVariants.length,
              },
              segmentKey,
            }),
            published_by: guard.actorId || undefined,
          })
          }
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error)
          results.push({
            platform: 'google',
            success: false,
            error: errorMsg,
            code: 'publish_google_failed',
            state: 'failed',
            actionable_message: 'Inspect Google Sheets integration logs and retry publish.',
          })

          await logPublishEvent(supabase, {
            master_sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: errorMsg,
            published_by: guard.actorId || undefined,
          })
        }
      }
    }

    // Publish to Shopify
    if (platforms.includes('shopify')) {
      // Strict fail-closed validation: Shopify publish requires Shopify-compliant content.
      const validation = await validateContentForPublishing(master_sku, 'shopify', {
        requireGlobalSkuApproval: false,
      })

      if (!validation.isValid) {
        const failedResult = toValidationFailureResult('shopify', validation)
        results.push(failedResult)

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'shopify',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: validation.errors.join('; '),
          published_by: guard.actorId || undefined,
        })
      } else if (!shopifyProductId) {
        results.push({
          platform: 'shopify',
          success: false,
          error: 'No Shopify product ID found for this SKU',
          code: 'publish_missing_shopify_product_id',
          state: 'failed',
          actionable_message: 'Sync variant_index so this SKU is linked to a Shopify product ID.',
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'shopify',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No Shopify product ID found',
          published_by: guard.actorId || undefined,
        })
      } else {
        try {
          // Shopify uses the master template without finish expansion
          // Strip {FINISH_NAME} placeholder if present since Shopify is product-level
          const shopifyTitle = validation.title!.replace(/\s*\{FINISH_NAME\}\s*/g, ' ').trim()
          const shopifyDescription = validation.description!.replace(/\s*\{FINISH_NAME\}\s*/g, ' ').replace(/\s*\{FINISH_SENTENCE\}\s*/g, ' ').trim()

          const shopifyNoop = await isIdempotentNoop(supabase, {
            master_sku,
            platform: 'shopify',
            environment,
            title: shopifyTitle,
            description: shopifyDescription,
          })

          if (shopifyNoop) {
            results.push({
              platform: 'shopify',
              success: true,
              state: 'no_change',
              idempotent: true,
              details: { reason: 'Already published this content snapshot.' },
            })
          } else {
            const shopifyResult = await publishToShopify(
              shopifyProductId,
              shopifyTitle,
              shopifyDescription,
              environment
            )
            const shopifySnapshot = buildShopifyFinalPayloadSnapshot({
              shopify_product_id: shopifyProductId,
              title: shopifyTitle,
              description: shopifyDescription,
            })

            results.push({
              platform: 'shopify',
              success: shopifyResult.success,
              error: shopifyResult.success ? undefined : shopifyResult.errors.join('; '),
              details: {
                shopify_product_id: shopifyProductId,
              },
            })

            await logPublishEvent(supabase, {
              master_sku,
              platform: 'shopify',
              environment,
              action: 'publish',
              status: shopifyResult.success ? 'success' : 'failed',
              error_message: shopifyResult.success ? undefined : shopifyResult.errors.join('; '),
              published_title: shopifyTitle ?? undefined,
              published_description: shopifyDescription ?? undefined,
              final_payload_snapshot: shopifySnapshot,
              ...buildPublishLineageHashes({
                finalPayloadSnapshot: shopifySnapshot,
                promptHash: validation.prompt_hash,
                evidenceInput: {
                  master_sku,
                  platform: 'shopify',
                  title: shopifyTitle,
                  description: shopifyDescription,
                  shopify_product_id: shopifyProductId,
                },
                segmentKey,
              }),
              published_by: guard.actorId || undefined,
            })
          }
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error)
          results.push({
            platform: 'shopify',
            success: false,
            error: errorMsg,
            code: 'publish_shopify_failed',
            state: 'failed',
            actionable_message: 'Inspect Shopify publish logs and retry publish.',
          })

          await logPublishEvent(supabase, {
            master_sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: errorMsg,
            published_by: guard.actorId || undefined,
          })
        }
      }
    }

    // Publish to Bing (readiness + content validated, non-destructive publish acknowledgement)
    if (platforms.includes('bing')) {
      const validation = await validateContentForPublishing(master_sku, 'bing', {
        requireGlobalSkuApproval: false,
      })

      if (!validation.isValid) {
        const failedResult = toValidationFailureResult('bing', validation)
        results.push(failedResult)

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'bing',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: validation.errors.join('; '),
          published_by: guard.actorId || undefined,
        })
      } else if (offerIds.length === 0) {
        results.push({
          platform: 'bing',
          success: false,
          error: 'No variant offer IDs found for this SKU',
          code: 'publish_missing_offer_ids',
          state: 'failed',
          actionable_message: 'Sync variant index mappings so this SKU has variant offer IDs.',
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'bing',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No variant offer IDs found',
          published_by: guard.actorId || undefined,
        })
      } else {
        const bingNoop = await isIdempotentNoop(supabase, {
          master_sku,
          platform: 'bing',
          environment,
          title: validation.title,
          description: validation.description,
        })
        const bingSnapshot = buildBingFinalPayloadSnapshot({
          offer_ids: offerIds,
          title: validation.title ?? '',
          description: validation.description ?? '',
          publish_mode: 'readiness_recorded',
        })

        results.push({
          platform: 'bing',
          success: true,
          state: bingNoop ? 'no_change' : 'completed',
          idempotent: bingNoop,
          details: {
            note: bingNoop
              ? 'Bing content snapshot already published.'
              : 'Bing content readiness validated and publish recorded.',
            offer_ids: offerIds,
          },
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'bing',
          environment,
          action: 'publish',
          status: 'success',
          published_title: validation.title ?? undefined,
          published_description: validation.description ?? undefined,
          final_payload_snapshot: bingSnapshot,
          ...buildPublishLineageHashes({
            finalPayloadSnapshot: bingSnapshot,
            promptHash: validation.prompt_hash,
            evidenceInput: {
              master_sku,
              platform: 'bing',
              title: validation.title ?? null,
              description: validation.description ?? null,
              offer_ids: offerIds,
              publish_mode: 'readiness_recorded',
            },
            segmentKey,
          }),
          published_by: guard.actorId || undefined,
        })
      }
    }

    // Calculate overall success
    const successCount = results.filter((r) => r.success).length
    const failedCount = results.filter((r) => !r.success).length
    const overallSuccess = failedCount === 0

    // FEED-03: Capture search query snapshot after successful publish for term delta analysis.
    // Fire-and-forget — don't block the publish response on snapshot capture.
    if (successCount > 0) {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_APP_URL
          || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000')
        fetch(`${baseUrl}/api/monitoring/snapshot-capture?master_sku=${encodeURIComponent(master_sku)}`, {
          method: 'POST',
        }).catch(err => console.error('[FEED-03] Snapshot capture failed (non-blocking):', err.message))
      } catch (err) {
        console.error('[FEED-03] Snapshot capture trigger failed (non-blocking):', err)
      }
    }

    return NextResponse.json({
      success: overallSuccess,
      master_sku,
      environment,
      results,
      summary: {
        total: results.length,
        successful: successCount,
        failed: failedCount,
        no_change: results.filter((r) => r.state === 'no_change').length,
      },
    })
  } catch (error) {
    console.error('SKU publish error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return publishErrorResponse(500, {
      error: message,
      code: 'publish_unhandled_exception',
      step: 'route_exception',
      actionable_message: 'Retry publish once. If it persists, inspect API logs for the failing SKU.',
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
