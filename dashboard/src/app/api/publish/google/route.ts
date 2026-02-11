import { createClient } from '@/lib/supabase/server'
import { publishToGoogleSheets } from '@/lib/publishing/google-sheets'
import type { PublishRequest, PublishEventInsert } from '@/lib/publishing/types'
import { NextRequest, NextResponse } from 'next/server'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'

interface GooglePublishRequest extends PublishRequest {
  // Optional: override offer IDs (if not provided, fetched from variant_index)
  offer_ids?: string[]
}

/**
 * POST /api/publish/google
 *
 * Publish optimized content to Google Merchant Center via Google Sheets supplemental feed.
 *
 * Request body:
 * {
 *   master_sku: string,       // Required: SKU identifier
 *   title: string,            // Required: Optimized title
 *   description: string,      // Required: Optimized description
 *   image_url?: string,       // Optional: Lifestyle image URL
 *   environment: 'staging' | 'production',  // Required
 *   offer_ids?: string[]      // Optional: Override offer IDs (fetched from variant_index if not provided)
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as GooglePublishRequest

    // Validate required fields
    let { master_sku } = body
    const { title, description, environment, image_url, offer_ids } = body

    if (!master_sku) {
      return NextResponse.json(
        { error: 'master_sku is required' },
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
    let resolvedOfferIds = offer_ids || []

    // If no offer IDs provided, fetch from variant_index
    if (resolvedOfferIds.length === 0) {
      const { data: variants, error: variantError } = await supabase
        .from('variant_index')
        .select('gmc_offer_id')
        .eq('master_sku', master_sku)

      if (variantError) {
        console.error('Error fetching variants:', variantError)
        return NextResponse.json(
          { error: `Failed to fetch variants: ${variantError.message}` },
          { status: 500 }
        )
      }

      if (!variants || variants.length === 0) {
        return NextResponse.json(
          { error: `No variants found for SKU ${master_sku} in variant_index` },
          { status: 404 }
        )
      }

      resolvedOfferIds = variants
        .map((v) => v.gmc_offer_id)
        .filter((id): id is string => !!id)
    }

    if (resolvedOfferIds.length === 0) {
      return NextResponse.json(
        { error: `No GMC offer IDs found for SKU ${master_sku}` },
        { status: 404 }
      )
    }

    // Publish to Google Sheets
    const result = await publishToGoogleSheets(
      resolvedOfferIds,
      title,
      description,
      environment,
      image_url
    )

    // Log publish event to Supabase
    const publishEvent: PublishEventInsert = {
      master_sku,
      platform: 'google',
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
          platform: 'google',
          environment,
          errors: result.errors,
        },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      master_sku,
      platform: 'google',
      environment,
      details: {
        updated_count: result.updated_count,
        appended_count: result.appended_count,
        total_variants: result.total_variants,
        offer_ids: resolvedOfferIds,
      },
    })
  } catch (error) {
    console.error('Google publish error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
