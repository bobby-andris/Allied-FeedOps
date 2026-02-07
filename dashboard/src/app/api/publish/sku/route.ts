import { createClient } from '@/lib/supabase/server'
import { publishExpandedVariantsToGoogleSheets } from '@/lib/publishing/google-sheets'
import { publishToShopify } from '@/lib/publishing/shopify'
import { expandVariantsForPublish, validateContentForPublishing } from '@/lib/publishing/expand-variants'
import type { Platform, PublishEventInsert } from '@/lib/publishing/types'
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
  details?: Record<string, unknown>
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
    const body = (await request.json()) as SkuPublishRequest

    // Validate required fields
    const { master_sku, platforms, environment } = body

    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    if (!platforms || !Array.isArray(platforms) || platforms.length === 0) {
      return NextResponse.json(
        { error: 'platforms array is required and must not be empty' },
        { status: 400 }
      )
    }

    const validPlatforms: Platform[] = ['google', 'shopify', 'bing']
    for (const platform of platforms) {
      if (!validPlatforms.includes(platform)) {
        return NextResponse.json(
          { error: `Invalid platform: ${platform}. Must be one of: ${validPlatforms.join(', ')}` },
          { status: 400 }
        )
      }
    }

    if (!environment || !['staging', 'production'].includes(environment)) {
      return NextResponse.json(
        { error: "environment must be 'staging' or 'production'" },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // 1. Validate SKU is approved
    const { data: approval, error: approvalError } = await supabase
      .from('sku_approvals')
      .select('approval_status')
      .eq('master_sku', master_sku)
      .single()

    if (approvalError && approvalError.code !== 'PGRST116') {
      return NextResponse.json(
        { error: `Failed to check approval status: ${approvalError.message}` },
        { status: 500 }
      )
    }

    if (!approval || approval.approval_status !== 'approved') {
      return NextResponse.json(
        { error: `SKU ${master_sku} is not approved (status: ${approval?.approval_status || 'not found'})` },
        { status: 400 }
      )
    }

    // 2. Get variant data for this SKU
    const { data: variants, error: variantError } = await supabase
      .from('variant_index')
      .select('gmc_offer_id, shopify_product_id')
      .eq('master_sku', master_sku)

    if (variantError) {
      return NextResponse.json(
        { error: `Failed to fetch variants: ${variantError.message}` },
        { status: 500 }
      )
    }

    const offerIds = variants?.map((v) => v.gmc_offer_id).filter(Boolean) || []
    const shopifyProductId = variants?.find((v) => v.shopify_product_id)?.shopify_product_id

    // 3. Publish to each platform
    const results: PlatformResult[] = []

    // Publish to Google
    if (platforms.includes('google')) {
      const validation = await validateContentForPublishing(master_sku, 'google')

      if (!validation.isValid) {
        results.push({
          platform: 'google',
          success: false,
          error: validation.errors.join('; '),
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'google',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: validation.errors.join('; '),
        })
      } else if (offerIds.length === 0) {
        results.push({
          platform: 'google',
          success: false,
          error: 'No GMC offer IDs found for this SKU',
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'google',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No GMC offer IDs found',
        })
      } else {
        try {
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
          })
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error)
          results.push({
            platform: 'google',
            success: false,
            error: errorMsg,
          })

          await logPublishEvent(supabase, {
            master_sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: errorMsg,
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
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'shopify',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No approved content found',
        })
      } else if (!shopifyProductId) {
        results.push({
          platform: 'shopify',
          success: false,
          error: 'No Shopify product ID found for this SKU',
        })

        await logPublishEvent(supabase, {
          master_sku,
          platform: 'shopify',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'No Shopify product ID found',
        })
      } else {
        try {
          // Shopify uses the master template without finish expansion
          // Strip {FINISH_NAME} placeholder if present since Shopify is product-level
          const shopifyTitle = validation.title!.replace(/\s*\{FINISH_NAME\}\s*/g, ' ').trim()
          const shopifyDescription = validation.description!.replace(/\s*\{FINISH_NAME\}\s*/g, ' ').replace(/\s*\{FINISH_SENTENCE\}\s*/g, ' ').trim()

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
          })
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error)
          results.push({
            platform: 'shopify',
            success: false,
            error: errorMsg,
          })

          await logPublishEvent(supabase, {
            master_sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: errorMsg,
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
      })

      await logPublishEvent(supabase, {
        master_sku,
        platform: 'bing',
        environment,
        action: 'publish',
        status: 'failed',
        error_message: 'Bing publishing not yet implemented',
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
      },
    })
  } catch (error) {
    console.error('SKU publish error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return NextResponse.json({ error: message }, { status: 500 })
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
