import { createClient } from '@/lib/supabase/client'

/**
 * Upload lifestyle image to Supabase Storage
 *
 * This is a temporary solution for the review/approval workflow.
 * Once images are approved and published to Shopify, update URLs to use Shopify CDN.
 *
 * @param file - Image file or buffer
 * @param filename - Name for the file (e.g., "920D-6_var3_20260129_005005.png")
 * @returns Public URL from Supabase Storage
 */
export async function uploadLifestyleImage(
  file: File | Buffer,
  filename: string
): Promise<string> {
  const supabase = createClient()

  // Upload to Supabase Storage
  const { data, error } = await supabase.storage
    .from('lifestyle-images')
    .upload(filename, file, {
      contentType: 'image/png',
      upsert: true, // Overwrite if exists
    })

  if (error) {
    throw new Error(`Failed to upload image: ${error.message}`)
  }

  // Get public URL
  const { data: urlData } = supabase.storage
    .from('lifestyle-images')
    .getPublicUrl(filename)

  return urlData.publicUrl
}

/**
 * Update image URL to Shopify CDN after publishing
 *
 * Call this after the image has been published to Shopify via productCreateMedia mutation.
 *
 * @param imageId - generated_images.id
 * @param shopifyImageUrl - URL from Shopify CDN (e.g., "https://cdn.shopify.com/...")
 */
export async function migrateToShopifyCdn(
  imageId: string,
  shopifyImageUrl: string
): Promise<void> {
  const supabase = createClient()

  const { error } = await supabase
    .from('generated_images')
    .update({
      image_url: shopifyImageUrl,
      gmc_pushed_at: new Date().toISOString(), // Mark as published
    })
    .eq('id', imageId)

  if (error) {
    throw new Error(`Failed to update image URL: ${error.message}`)
  }
}

/**
 * Delete image from Supabase Storage (cleanup after Shopify migration)
 *
 * @param filename - Filename to delete from storage
 */
export async function deleteFromStorage(filename: string): Promise<void> {
  const supabase = createClient()

  const { error } = await supabase.storage
    .from('lifestyle-images')
    .remove([filename])

  if (error) {
    throw new Error(`Failed to delete image: ${error.message}`)
  }
}
