import { createClient } from '@/lib/supabase/server'
import { publishExpandedVariantsToGoogleSheets } from '@/lib/publishing/google-sheets'
import { publishToShopify } from '@/lib/publishing/shopify'
import { expandVariantsForPublish, validateContentForPublishing } from '@/lib/publishing/expand-variants'
import { uploadProductImage } from '@/lib/publishing/shopify-images'
import type { Platform, PublishEventInsert } from '@/lib/publishing/types'
import { enforcePublishGuard } from '@/lib/auth/publish-guard'
import { NextRequest, NextResponse } from 'next/server'

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
 * 1. Validate SKU is approved in sku_approvals
 * 2. Fetch approved_content from generated_content
 * 3. Get variant data from variant_index
 * 4. Call platform-specific publish functions
 * 5. Log results to publish_events
 * 6. Return detailed results
 */
export async function POST(request: NextRequest) {
  try {
    const guard = enforcePublishGuard(request)
    if (!guard.allowed) {
      return guard.response!
    }

    const body = (await request.json()) as SkuPublishRequest

    // Validate required fields
    const { master_sku, platforms, environment } = body

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

    // 1. Validate SKU is approved
    const { data: approval, error: approvalError } = await supabase
      .from('sku_approvals')
      .select('approval_status')
      .eq('master_sku', master_sku)
      .single()

    if (approvalError && approvalError.code !== 'PGRST116') {
      return publishErrorResponse(500, {
        error: `Failed to check approval status: ${approvalError.message}`,
        code: 'publish_approval_lookup_failed',
        step: 'approval_check',
        actionable_message: 'Retry publish. If this persists, check sku_approvals table access.',
      })
    }

    if (!approval || approval.approval_status !== 'approved') {
      return publishErrorResponse(400, {
        error: `SKU ${master_sku} is not approved (status: ${approval?.approval_status || 'not found'})`,
        code: 'publish_requires_approved_sku',
        step: 'approval_check',
        actionable_message: 'Approve this SKU in Review before publishing.',
      })
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
      const validation = await validateContentForPublishing(master_sku, 'google')

      if (!validation.isValid) {
        results.push({
          platform: 'google',
          success: false,
          error: validation.errors.join('; '),
          code: 'publish_missing_approved_content_google',
          state: 'failed',
          actionable_message: 'Approve Google title and description content before publishing.',
          details: { validation_errors: validation.errors },
        })

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
      // Prefer Shopify-specific content, fall back to Google content
      let validation = await validateContentForPublishing(master_sku, 'shopify')
      if (!validation.isValid) {
        // Try Google content as fallback
        validation = await validateContentForPublishing(master_sku, 'google')
      }

      if (!validation.isValid) {
        results.push({
          platform: 'shopify',
          success: false,
          error: 'No approved content found for Shopify or Google',
          code: 'publish_missing_approved_content_shopify',
          state: 'failed',
          actionable_message: 'Approve Shopify or Google title/description content before publishing.',
          details: { validation_errors: validation.errors },
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'shopify',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No approved content found',
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

    // Bing publishing deferred
    if (platforms.includes('bing')) {
      results.push({
        platform: 'bing',
        success: false,
        error: 'Bing publishing not yet implemented',
        code: 'publish_bing_not_implemented',
        state: 'failed',
        actionable_message: 'Use Google/Shopify publish for now. Bing support is not implemented yet.',
      })

      await logPublishEvent(supabase, {
        master_sku,
        platform: 'bing',
        environment,
        action: 'publish',
        status: 'failed',
        error_message: 'Bing publishing not yet implemented',
        published_by: guard.actorId || undefined,
      })
    }

    // Calculate overall success
    const successCount = results.filter((r) => r.success).length
    const failedCount = results.filter((r) => !r.success).length
    const overallSuccess = failedCount === 0

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
  try {
    await supabase.from('publish_events').insert({
      ...event,
      published_at: new Date().toISOString(),
    })
  } catch (error) {
    console.error('Failed to log publish event:', error)
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
