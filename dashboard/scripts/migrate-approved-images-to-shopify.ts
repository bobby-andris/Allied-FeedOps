/**
 * Migration script: Upload approved lifestyle images to Shopify CDN.
 *
 * Usage: npx tsx scripts/migrate-approved-images-to-shopify.ts [--dry-run] [--limit N]
 *
 * This script:
 * 1. Finds all approved images without Shopify CDN URLs
 * 2. Uploads each to Shopify via productCreateMedia
 * 3. Updates database with Shopify CDN URLs and metadata
 *
 * Lifecycle:
 * - Supabase Storage (review/approval) → Shopify CDN (production) → Google Sheets
 */

import { createClient } from '@supabase/supabase-js'
import { uploadAndAssociateImage } from '../src/lib/publishing/shopify-images'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async function migrateApprovedImagesToShopify(
  dryRun: boolean = false,
  limit?: number
) {
  console.log(`\n🚀 Starting Shopify CDN migration (dry-run: ${dryRun})\n`)

  // Find approved images without Shopify CDN URLs
  let query = supabase
    .from('generated_images')
    .select('id, master_sku, finish_code, image_url, use_for_master')
    .eq('approval_status', 'approved')
    .is('shopify_cdn_url', null)

  if (limit) {
    query = query.limit(limit)
  }

  const { data: images, error } = await query

  if (error) {
    console.error('❌ Error fetching images:', error)
    process.exit(1)
  }

  if (!images || images.length === 0) {
    console.log('✅ No images to migrate')
    return
  }

  console.log(`📦 Found ${images.length} images to migrate\n`)

  let successCount = 0
  let errorCount = 0

  for (const [index, image] of images.entries()) {
    console.log(`\n[${index + 1}/${images.length}] Processing image ${image.id}`)
    console.log(`  SKU: ${image.master_sku}, Finish: ${image.finish_code || 'Master'}`)

    if (dryRun) {
      console.log('  [DRY RUN] Would upload to Shopify')
      continue
    }

    try {
      // Get Shopify product/variant IDs from variant_index
      const variantQuery = supabase
        .from('variant_index')
        .select('shopify_product_id, shopify_variant_id, finish_code')
        .eq('master_sku', image.master_sku)

      if (image.finish_code && !image.use_for_master) {
        variantQuery.eq('finish_code', image.finish_code)
      }

      const { data: variants, error: variantError } = await variantQuery.limit(1)

      if (variantError || !variants || variants.length === 0) {
        console.error('  ⚠️  No Shopify mapping found, skipping')
        errorCount++
        continue
      }

      const variant = variants[0]

      if (!variant.shopify_product_id) {
        console.error('  ⚠️  No Shopify product ID, skipping')
        errorCount++
        continue
      }

      // Upload to Shopify
      console.log('  📤 Uploading to Shopify...')
      const result = await uploadAndAssociateImage(
        image.image_url,
        variant.shopify_product_id,
        variant.shopify_variant_id || undefined,
        `${image.master_sku} - ${image.finish_code || 'Master'}`
      )

      console.log(`  ✅ Uploaded! Media ID: ${result.mediaId}`)
      console.log(`  🔗 CDN URL: ${result.cdnUrl}`)

      // Update database with Shopify CDN URL
      const { error: updateError } = await supabase
        .from('generated_images')
        .update({
          shopify_media_id: result.mediaId,
          shopify_cdn_url: result.cdnUrl,
          migrated_to_shopify_at: new Date().toISOString(),
        })
        .eq('id', image.id)

      if (updateError) {
        console.error('  ❌ Database update failed:', updateError)
        errorCount++
        continue
      }

      successCount++
    } catch (error) {
      console.error('  ❌ Upload failed:', error)
      errorCount++
    }
  }

  console.log(`\n\n📊 Migration complete:`)
  console.log(`  ✅ Success: ${successCount}`)
  console.log(`  ❌ Errors: ${errorCount}`)
}

// Parse command line args
const args = process.argv.slice(2)
const dryRun = args.includes('--dry-run')
const limitIndex = args.indexOf('--limit')
const limit = limitIndex >= 0 ? parseInt(args[limitIndex + 1]) : undefined

migrateApprovedImagesToShopify(dryRun, limit).catch(console.error)
