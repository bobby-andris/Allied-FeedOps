import { createClient } from '@/lib/supabase/server'
import { publishToShopify } from '@/lib/publishing/shopify'
import type { ShopifyPublishRequest, PublishEventInsert } from '@/lib/publishing/types'
import { NextRequest, NextResponse } from 'next/server'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'

/**
 * POST /api/publish/shopify
 *
 * Publish optimized content to Shopify via GraphQL Admin API.
 *
 * Request body:
 * {
 *   master_sku: string,           // Required: SKU identifier
 *   shopify_product_id: string,   // Required: Shopify product ID (numeric or GID format)
 *   title: string,                // Required: Optimized title
 *   description: string,          // Required: Optimized description (HTML supported)
 *   environment: 'staging' | 'production',  // Required
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as ShopifyPublishRequest

    // Validate required fields
    let { master_sku } = body
    const { shopify_product_id, title, description, environment } = body

    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
        { status: 400 }
      )
    }

    if (!shopify_product_id) {
      return NextResponse.json(
        { error: 'shopify_product_id is required' },
        { status: 400 }
      )
    }

    if (!title) {
      return NextResponse.json({ error: 'title is required' }, { status: 400 })
    }

    if (!description) {
      return NextResponse.json(
        { error: 'description is required' },
        { status: 400 }
      )
    }

    if (!environment || !['staging', 'production'].includes(environment)) {
      return NextResponse.json(
        { error: "environment must be 'staging' or 'production'" },
        { status: 400 }
      )
    }

    const supabase = await createClient()
    const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)
    master_sku = canonicalMasterSku

    // Publish to Shopify
    const result = await publishToShopify(
      shopify_product_id,
      title,
      description,
      environment
    )

    // Log publish event to Supabase
    const publishEvent: PublishEventInsert = {
      master_sku,
      platform: 'shopify',
      environment,
      action: 'publish',
      status: result.success ? 'success' : 'failed',
      error_message: result.success ? undefined : result.errors.join('; '),
    }

    const { error: logError } = await supabase
      .from('publish_events')
      .insert(publishEvent)

    if (logError) {
      console.error('Failed to log publish event:', logError)
      // Don't fail the request if logging fails
    }

    if (!result.success) {
      return NextResponse.json(
        {
          success: false,
          master_sku,
          platform: 'shopify',
          environment,
          errors: result.errors,
        },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      master_sku,
      platform: 'shopify',
      environment,
      details: {
        shopify_product_id,
        tracking_tag: result.tracking_tag,
        product: result.product,
      },
    })
  } catch (error) {
    console.error('Shopify publish error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
