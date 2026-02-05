import { createClient } from '@/lib/supabase/server'
import { publishExpandedVariantsToGoogleSheets } from '@/lib/publishing/google-sheets'
import { publishToShopify } from '@/lib/publishing/shopify'
import { expandVariantsForPublish, validateContentForPublishing } from '@/lib/publishing/expand-variants'
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
  shopify_title?: string
  shopify_description?: string
  shopify_version?: number
  offer_ids: string[]
  shopify_product_id?: string
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
    const body = (await request.json()) as BatchPublishRequest

    // Validate required fields
    const { batch_id, platforms, environment } = body

    if (!batch_id) {
      return NextResponse.json(
        { error: 'batch_id is required' },
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

    // 1. Get all SKUs in the batch
    const { data: assignments, error: assignmentError } = await supabase
      .from('batch_sku_assignments')
      .select('master_sku')
      .eq('batch_id', batch_id)

    if (assignmentError) {
      return NextResponse.json(
        { error: `Failed to fetch batch assignments: ${assignmentError.message}` },
        { status: 500 }
      )
    }

    if (!assignments || assignments.length === 0) {
      return NextResponse.json(
        { error: `No SKUs found in batch ${batch_id}` },
        { status: 404 }
      )
    }

    const skuList = assignments.map((a) => a.master_sku)

    // Update batch status to 'executing'
    await supabase
      .from('publish_batches')
      .update({ status: 'executing', updated_at: new Date().toISOString() })
      .eq('batch_id', batch_id)

    // 2. Get APPROVED content for each SKU (not candidate_content)
    const { data: contentData, error: contentError } = await supabase
      .from('generated_content')
      .select('master_sku, platform, content_type, approved_content, approved_version')
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
      for (const row of contentData as { master_sku: string; platform: string; content_type: string; approved_content: string | null; approved_version: number | null }[]) {
        const content = skuContentMap.get(row.master_sku)
        if (!content) continue

        if (row.content_type === 'title') {
          if (row.platform === 'google') {
            content.google_title = row.approved_content || undefined
            content.google_version = row.approved_version || undefined
          } else if (row.platform === 'shopify') {
            content.shopify_title = row.approved_content || undefined
            content.shopify_version = row.approved_version || undefined
          }
        } else if (row.content_type === 'description') {
          if (row.platform === 'google') {
            content.google_description = row.approved_content || undefined
          } else if (row.platform === 'shopify') {
            content.shopify_description = row.approved_content || undefined
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
    let successCount = 0
    let failedCount = 0

    for (const sku of skuList) {
      const content = skuContentMap.get(sku)
      if (!content) continue

      // Publish to Google
      if (platforms.includes('google')) {
        const title = content.google_title
        const description = content.google_description

        // Check approval status first
        if (content.approval_status !== 'approved') {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: `SKU not approved (status: ${content.approval_status || 'not found'})`,
          }
          results.push(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            batch_id,
          })
        } else if (!title || !description) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: 'Missing approved title or description for Google',
          }
          results.push(result)
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
          })
        } else if (content.offer_ids.length === 0) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'google',
            error: 'No GMC offer IDs found',
          }
          results.push(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'google',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'No GMC offer IDs found',
            batch_id,
          })
        } else {
          try {
            // Expand templates for each variant (replaces {FINISH_NAME} with actual finish)
            const expandedVariants = await expandVariantsForPublish({
              master_sku: sku,
              platform: 'google',
              approved_title: title,
              approved_description: description,
            })

            // Publish expanded variants - each with unique title/description
            const googleResult = await publishExpandedVariantsToGoogleSheets(
              expandedVariants.map((v) => ({
                gmc_offer_id: v.gmc_offer_id,
                title: v.title,
                description: v.description,
              })),
              environment
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
            results.push(result)

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
              published_title: title,
              published_description: description,
              variant_count: expandedVariants.length,
              content_version: content.google_version,
            })
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            const result: PublishResult = {
              success: false,
              master_sku: sku,
              platform: 'google',
              error: errorMsg,
            }
            results.push(result)
            failedCount++

            await logPublishEvent(supabase, {
              master_sku: sku,
              platform: 'google',
              environment,
              action: 'publish',
              status: 'failed',
              error_message: errorMsg,
              batch_id,
            })
          }
        }
      }

      // Publish to Shopify
      if (platforms.includes('shopify')) {
        const title = content.shopify_title || content.google_title
        const description = content.shopify_description || content.google_description

        // Check approval status first
        if (content.approval_status !== 'approved') {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: `SKU not approved (status: ${content.approval_status || 'not found'})`,
          }
          results.push(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: `SKU not approved (status: ${content.approval_status || 'not found'})`,
            batch_id,
          })
        } else if (!title || !description) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: 'Missing approved title or description for Shopify',
          }
          results.push(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'Missing approved title or description',
            batch_id,
          })
        } else if (!content.shopify_product_id) {
          const result: PublishResult = {
            success: false,
            master_sku: sku,
            platform: 'shopify',
            error: 'No Shopify product ID found',
          }
          results.push(result)
          failedCount++

          await logPublishEvent(supabase, {
            master_sku: sku,
            platform: 'shopify',
            environment,
            action: 'publish',
            status: 'failed',
            error_message: 'No Shopify product ID found',
            batch_id,
          })
        } else {
          try {
            const shopifyResult = await publishToShopify(
              content.shopify_product_id,
              title,
              description,
              environment
            )

            const result: PublishResult = {
              success: shopifyResult.success,
              master_sku: sku,
              platform: 'shopify',
              error: shopifyResult.success ? undefined : shopifyResult.errors.join('; '),
              details: {
                shopify_product_id: content.shopify_product_id,
              },
            }
            results.push(result)

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
              published_title: title,
              published_description: description,
              content_version: content.shopify_version,
            })
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            const result: PublishResult = {
              success: false,
              master_sku: sku,
              platform: 'shopify',
              error: errorMsg,
            }
            results.push(result)
            failedCount++

            await logPublishEvent(supabase, {
              master_sku: sku,
              platform: 'shopify',
              environment,
              action: 'publish',
              status: 'failed',
              error_message: errorMsg,
              batch_id,
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
        }
        results.push(result)
        failedCount++

        await logPublishEvent(supabase, {
          master_sku: sku,
          platform: 'bing',
          environment,
          action: 'publish',
          status: 'failed',
          error_message: 'Bing publishing not yet implemented',
          batch_id,
        })
      }
    }

    // 6. Update batch status based on results
    const allFailed = successCount === 0 && failedCount > 0
    const allSucceeded = failedCount === 0 && successCount > 0
    const batchStatus = allFailed ? 'failed' : allSucceeded ? 'completed' : 'partial'

    await supabase
      .from('publish_batches')
      .update({
        status: batchStatus,
        executed_at: new Date().toISOString(),
        success_count: successCount,
        failed_count: failedCount,
        updated_at: new Date().toISOString(),
      })
      .eq('batch_id', batch_id)

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
