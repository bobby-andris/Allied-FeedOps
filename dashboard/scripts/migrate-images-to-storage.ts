import { createClient } from '@supabase/supabase-js'
import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

/**
 * Migrate lifestyle images from local file paths to Supabase Storage
 *
 * This script:
 * 1. Reads generated_images records with file paths
 * 2. Uploads images to Supabase Storage bucket 'lifestyle-images'
 * 3. Updates image_url to use Supabase CDN URL
 *
 * Usage: npx tsx scripts/migrate-images-to-storage.ts
 *
 * Environment variables required:
 * - NEXT_PUBLIC_SUPABASE_URL
 * - NEXT_PUBLIC_SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY for admin access)
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing Supabase credentials')
  console.error('Required: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY)')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

interface ImageRecord {
  id: string
  master_sku: string
  image_url: string | null
  thumbnail_url: string | null
}

async function migrateImages() {
  console.log('🔍 Fetching images from database...\n')

  // Get all images with local file paths
  const { data: images, error } = await supabase
    .from('generated_images')
    .select('id, master_sku, image_url, thumbnail_url')
    .like('image_url', 'dashboard_data/%')
    .order('created_at', { ascending: false })

  if (error) {
    console.error('Error fetching images:', error)
    process.exit(1)
  }

  if (!images || images.length === 0) {
    console.log('✅ No images to migrate (all images already use URLs)')
    return
  }

  console.log(`Found ${images.length} images with local file paths\n`)

  let successCount = 0
  let skipCount = 0
  let errorCount = 0

  for (const image of images as ImageRecord[]) {
    const filePath = image.image_url
    if (!filePath) continue

    // Extract filename from path: dashboard_data/lifestyle-eval-candidate/images/920D-6_var3_20260129_005005.png
    const filename = filePath.split('/').pop()
    if (!filename) {
      console.log(`⚠️  Skipping ${image.id}: Invalid file path`)
      skipCount++
      continue
    }

    // Check if file exists locally
    const localPath = resolve(process.cwd(), '..', filePath)
    if (!existsSync(localPath)) {
      console.log(`⚠️  Skipping ${filename}: File not found at ${localPath}`)
      skipCount++
      continue
    }

    try {
      // Read file
      const fileBuffer = readFileSync(localPath)

      // Upload to Supabase Storage
      const { error: uploadError } = await supabase.storage
        .from('lifestyle-images')
        .upload(filename, fileBuffer, {
          contentType: 'image/png',
          upsert: true, // Overwrite if exists
        })

      if (uploadError) {
        console.error(`❌ Upload failed for ${filename}:`, uploadError.message)
        errorCount++
        continue
      }

      // Get public URL
      const { data: urlData } = supabase.storage
        .from('lifestyle-images')
        .getPublicUrl(filename)

      const publicUrl = urlData.publicUrl

      // Update database
      const { error: updateError } = await supabase
        .from('generated_images')
        .update({ image_url: publicUrl })
        .eq('id', image.id)

      if (updateError) {
        console.error(`❌ Database update failed for ${filename}:`, updateError.message)
        errorCount++
        continue
      }

      console.log(`✅ ${filename} → ${publicUrl}`)
      successCount++
    } catch (err) {
      console.error(`❌ Error processing ${filename}:`, err)
      errorCount++
    }
  }

  console.log(`\n📊 Migration Summary:`)
  console.log(`   ✅ Migrated: ${successCount}`)
  console.log(`   ⚠️  Skipped: ${skipCount}`)
  console.log(`   ❌ Errors: ${errorCount}`)
  console.log(`   📁 Total: ${images.length}`)

  if (skipCount > 0) {
    console.log(`\n💡 Tip: Skipped files weren't found locally. They may be in the archive branch:`)
    console.log(`   git show archive/full-snapshot-2026-02-03:dashboard_data/lifestyle-eval-candidate/images/`)
  }
}

migrateImages()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error('Fatal error:', err)
    process.exit(1)
  })
