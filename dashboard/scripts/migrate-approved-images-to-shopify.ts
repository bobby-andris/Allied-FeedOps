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
import { uploadProductImage, uploadVariantImage } from '../src/lib/publishing/shopify-images'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async function migrateApprovedImagesToShopify(
  dryRun: boolean = false,
  limit?: number
) {
  console.log(`\n🚀 Starting Shopify CDN migration (dry-run: ${dryRun})\n`)

  // Migrate product-level images
  console.log('📦 Migrating product-level images...\n')
  let productQuery = supabase
    .from('product_lifestyle_images')
    .select('id, master_sku, shopify_product_id, image_url')
    .eq('approval_status', 'approved')
    .is('shopify_cdn_url', null)

  if (limit) {
    productQuery = productQuery.limit(limit)
  }

  const { data: productImages, error: productError } = await productQuery

  if (productError) {
    console.error('❌ Error fetching product images:', productError)
  }

  let productSuccessCount = 0
  let productErrorCount = 0

  for (const [index, img] of (productImages || []).entries()) {
    console.log(`\n[Product ${index + 1}/${productImages?.length || 0}] Processing ${img.id}`)
    console.log(`  SKU: ${img.master_sku}`)

    if (dryRun) {
      console.log('  [DRY RUN] Would upload to Shopify')
      continue
    }

    try {
      console.log('  📤 Uploading to Shopify...')
      const result = await uploadProductImage(
        img.image_url,
        img.shopify_product_id,
        `${img.master_sku} product image`
      )

      console.log(`  ✅ Uploaded! Media ID: ${result.mediaId}`)
      console.log(`  🔗 CDN URL: ${result.cdnUrl}`)

      const { error: updateError } = await supabase
        .from('product_lifestyle_images')
        .update({
          shopify_media_id: result.mediaId,
          shopify_cdn_url: result.cdnUrl,
          migrated_to_shopify_at: new Date().toISOString(),
        })
        .eq('id', img.id)

      if (updateError) {
        console.error('  ❌ Database update failed:', updateError)
        productErrorCount++
        continue
      }

      productSuccessCount++
    } catch (error) {
      console.error('  ❌ Upload failed:', error)
      productErrorCount++
    }
  }

  // Migrate variant-level images
  console.log('\n\n📦 Migrating variant-level images...\n')
  let variantQuery = supabase
    .from('variant_lifestyle_images')
    .select('id, master_sku, gmc_offer_id, finish, image_url')
    .eq('approval_status', 'approved')
    .is('shopify_cdn_url', null)

  if (limit) {
    variantQuery = variantQuery.limit(limit)
  }

  const { data: variantImages, error: variantError } = await variantQuery

  if (variantError) {
    console.error('❌ Error fetching variant images:', variantError)
  }

  let variantSuccessCount = 0
  let variantErrorCount = 0

  for (const [index, img] of (variantImages || []).entries()) {
    console.log(`\n[Variant ${index + 1}/${variantImages?.length || 0}] Processing ${img.id}`)
    console.log(`  SKU: ${img.master_sku}, Finish: ${img.finish}`)

    if (dryRun) {
      console.log('  [DRY RUN] Would upload to Shopify')
      continue
    }

    try {
      // Lookup Shopify IDs from variant_index
      const { data: variant, error: lookupError } = await supabase
        .from('variant_index')
        .select('shopify_product_id, shopify_variant_id')
        .eq('gmc_offer_id', img.gmc_offer_id)
        .single()

      if (lookupError || !variant?.shopify_product_id) {
        console.error(`  ⚠️  No Shopify mapping for ${img.gmc_offer_id}, skipping`)
        variantErrorCount++
        continue
      }

      console.log('  📤 Uploading to Shopify...')
      const result = await uploadVariantImage(
        img.image_url,
        variant.shopify_product_id,
        variant.shopify_variant_id || '',
        `${img.master_sku} - ${img.finish}`
      )

      console.log(`  ✅ Uploaded! Media ID: ${result.mediaId}`)
      console.log(`  🔗 CDN URL: ${result.cdnUrl}`)

      const { error: updateError } = await supabase
        .from('variant_lifestyle_images')
        .update({
          shopify_media_id: result.mediaId,
          shopify_cdn_url: result.cdnUrl,
          migrated_to_shopify_at: new Date().toISOString(),
        })
        .eq('id', img.id)

      if (updateError) {
        console.error('  ❌ Database update failed:', updateError)
        variantErrorCount++
        continue
      }

      variantSuccessCount++
    } catch (error) {
      console.error('  ❌ Upload failed:', error)
      variantErrorCount++
    }
  }

  const successCount = productSuccessCount + variantSuccessCount
  const errorCount = productErrorCount + variantErrorCount

  console.log(`\n\n📊 Migration complete:`)
  console.log(`  ✅ Product images: ${productSuccessCount} success, ${productErrorCount} errors`)
  console.log(`  ✅ Variant images: ${variantSuccessCount} success, ${variantErrorCount} errors`)
  console.log(`  📈 Total: ${successCount} success, ${errorCount} errors`)
}

// Parse command line args
const args = process.argv.slice(2)
const dryRun = args.includes('--dry-run')
const limitIndex = args.indexOf('--limit')
const limit = limitIndex >= 0 ? parseInt(args[limitIndex + 1]) : undefined

migrateApprovedImagesToShopify(dryRun, limit).catch(console.error)
