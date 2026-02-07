-- Add Shopify CDN fields to generated_images table
-- This migration enables lifecycle: Supabase Storage (review) → Shopify CDN (production) → Google Sheets

ALTER TABLE generated_images
ADD COLUMN IF NOT EXISTS shopify_media_id TEXT,
ADD COLUMN IF NOT EXISTS shopify_cdn_url TEXT,
ADD COLUMN IF NOT EXISTS migrated_to_shopify_at TIMESTAMP WITH TIME ZONE;

-- Create index for efficient querying of approved images with Shopify CDN URLs
CREATE INDEX IF NOT EXISTS idx_generated_images_shopify_cdn
ON generated_images(approval_status, shopify_cdn_url)
WHERE approval_status = 'approved';

-- Add comments for documentation
COMMENT ON COLUMN generated_images.shopify_media_id IS 'Shopify Media GID (e.g., gid://shopify/MediaImage/123)';
COMMENT ON COLUMN generated_images.shopify_cdn_url IS 'Production Shopify CDN URL - only populated after migration';
COMMENT ON COLUMN generated_images.migrated_to_shopify_at IS 'Timestamp when image was uploaded to Shopify';
