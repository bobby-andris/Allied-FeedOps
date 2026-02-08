-- 023_split_lifestyle_images.sql
-- Split generated_images into product_lifestyle_images and variant_lifestyle_images
--
-- Context: The unified generated_images table conflated product-level images (for Shopify)
-- and variant-level images (for GMC feed). This migration separates them with proper
-- foreign keys to variant_index for data integrity.
--
-- References:
-- - Plan: /Users/bobby/.claude/plans/lucky-churning-pretzel.md
-- - Discussion: Prompt 23 verification uncovered architectural issues

-- ============================================================================
-- Product-level Lifestyle Images
-- ============================================================================
-- Images displayed on Shopify product pages (applies to all variants).
-- NOT published to GMC feed lifestyle_image_link column.

CREATE TABLE IF NOT EXISTS product_lifestyle_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    shopify_product_id TEXT NOT NULL,  -- FK to variant_index.shopify_product_id

    -- Image storage (lifecycle: Supabase Storage → Shopify CDN)
    image_url TEXT NOT NULL,  -- Supabase Storage URL (review/approval stage)
    thumbnail_url TEXT,

    -- Shopify CDN (production stage - migrated during publish)
    shopify_media_id TEXT,  -- Shopify Media GID (e.g., gid://shopify/MediaImage/123)
    shopify_cdn_url TEXT,   -- Production CDN URL
    migrated_to_shopify_at TIMESTAMPTZ,

    -- Generation metadata
    prompt TEXT,
    generation_model TEXT,  -- e.g., 'gemini-3-pro-image-preview'
    generation_timestamp TIMESTAMPTZ,
    score NUMERIC(5,2),  -- Image quality score (0-100)
    score_breakdown JSONB,  -- {composition, relevance, quality, brand_fit}

    -- Approval workflow
    approval_status TEXT NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Selection (if multiple image variations generated)
    ai_selected BOOLEAN DEFAULT FALSE,
    user_selected BOOLEAN DEFAULT FALSE,
    variation_index INTEGER NOT NULL,  -- 0, 1, 2 for multiple variations

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraints
    UNIQUE(master_sku, variation_index),
    FOREIGN KEY (shopify_product_id) REFERENCES variant_index(shopify_product_id)
);

-- ============================================================================
-- Variant-level Lifestyle Images
-- ============================================================================
-- Images published to GMC feed (Google Sheets lifestyle_image_link column).
-- Each variant (gmc_offer_id) can have its own unique lifestyle image.
-- Still hosted on Shopify CDN but NOT displayed on Shopify product pages.

CREATE TABLE IF NOT EXISTS variant_lifestyle_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    gmc_offer_id TEXT NOT NULL,  -- FK to variant_index.gmc_offer_id (unique per variant)
    finish TEXT NOT NULL,
    finish_code TEXT NOT NULL,

    -- Image storage (lifecycle: Supabase Storage → Shopify CDN → GMC feed)
    image_url TEXT NOT NULL,  -- Supabase Storage URL (review/approval stage)
    thumbnail_url TEXT,

    -- Shopify CDN (production hosting for GMC feed)
    shopify_media_id TEXT,
    shopify_cdn_url TEXT,
    migrated_to_shopify_at TIMESTAMPTZ,

    -- Generation metadata
    prompt TEXT,
    generation_model TEXT,
    generation_timestamp TIMESTAMPTZ,
    score NUMERIC(5,2),
    score_breakdown JSONB,

    -- Approval workflow
    approval_status TEXT NOT NULL DEFAULT 'pending',
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Selection (if multiple variations per variant)
    ai_selected BOOLEAN DEFAULT FALSE,
    user_selected BOOLEAN DEFAULT FALSE,
    variation_index INTEGER NOT NULL,  -- Multiple variations per gmc_offer_id

    -- GMC publishing tracking
    gmc_pushed_at TIMESTAMPTZ,  -- When published to Google Sheets

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraints
    -- Note: One image per gmc_offer_id + variation_index
    UNIQUE(gmc_offer_id, variation_index),
    FOREIGN KEY (gmc_offer_id) REFERENCES variant_index(gmc_offer_id)
);

-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================

-- Product images indexes
CREATE INDEX IF NOT EXISTS idx_product_images_sku
    ON product_lifestyle_images(master_sku);

CREATE INDEX IF NOT EXISTS idx_product_images_shopify
    ON product_lifestyle_images(shopify_product_id);

CREATE INDEX IF NOT EXISTS idx_product_images_approval
    ON product_lifestyle_images(approval_status)
    WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_product_images_needs_migration
    ON product_lifestyle_images(approval_status, shopify_cdn_url)
    WHERE approval_status = 'approved' AND shopify_cdn_url IS NULL;

-- Variant images indexes
CREATE INDEX IF NOT EXISTS idx_variant_images_sku
    ON variant_lifestyle_images(master_sku);

CREATE INDEX IF NOT EXISTS idx_variant_images_offer
    ON variant_lifestyle_images(gmc_offer_id);

CREATE INDEX IF NOT EXISTS idx_variant_images_finish
    ON variant_lifestyle_images(master_sku, finish_code);

CREATE INDEX IF NOT EXISTS idx_variant_images_approval
    ON variant_lifestyle_images(approval_status)
    WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_variant_images_needs_migration
    ON variant_lifestyle_images(approval_status, shopify_cdn_url)
    WHERE approval_status = 'approved' AND shopify_cdn_url IS NULL;

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE product_lifestyle_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE variant_lifestyle_images ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Allow all access" ON product_lifestyle_images;
DROP POLICY IF EXISTS "Allow all access" ON variant_lifestyle_images;

-- Create policies (allow all for now, auth handled at app level)
CREATE POLICY "Allow all access" ON product_lifestyle_images FOR ALL USING (true);
CREATE POLICY "Allow all access" ON variant_lifestyle_images FOR ALL USING (true);

-- ============================================================================
-- Table and Column Comments (Documentation)
-- ============================================================================

COMMENT ON TABLE product_lifestyle_images IS
'Product-level lifestyle images for Shopify product pages only. Not published to GMC feed. One set of images applies to all variants of a master SKU.';

COMMENT ON TABLE variant_lifestyle_images IS
'Variant-level lifestyle images published to GMC feed (Google Sheets lifestyle_image_link column). One image per gmc_offer_id. Hosted on Shopify CDN but not shown on Shopify product pages.';

COMMENT ON COLUMN product_lifestyle_images.shopify_product_id IS
'Links to variant_index.shopify_product_id - applies to entire product (all variants)';

COMMENT ON COLUMN variant_lifestyle_images.gmc_offer_id IS
'Links to variant_index.gmc_offer_id - unique per variant (e.g., shopify_us_123_456)';

COMMENT ON COLUMN product_lifestyle_images.shopify_cdn_url IS
'Populated during publish flow when image is uploaded to Shopify. NULL means needs migration.';

COMMENT ON COLUMN variant_lifestyle_images.shopify_cdn_url IS
'Populated during publish flow when image is uploaded to Shopify CDN for GMC feed use.';

-- ============================================================================
-- Data Migration from generated_images
-- ============================================================================
-- IMPORTANT: Existing images have gmc_offer_id = NULL, so we must lookup
-- IDs from variant_index by matching master_sku + finish_code

-- Step 1: Migrate master images (use_for_master = true) to product_lifestyle_images
-- Lookup shopify_product_id from variant_index
DO $$
BEGIN
    INSERT INTO product_lifestyle_images (
        master_sku,
        shopify_product_id,
        image_url,
        thumbnail_url,
        prompt,
        generation_model,
        generation_timestamp,
        score,
        score_breakdown,
        approval_status,
        approved_by,
        approved_at,
        rejection_reason,
        ai_selected,
        user_selected,
        variation_index,
        shopify_media_id,
        shopify_cdn_url,
        migrated_to_shopify_at,
        created_at
    )
    SELECT DISTINCT ON (gi.master_sku, gi.variation_index)
        gi.master_sku,
        vi.shopify_product_id,  -- Lookup from variant_index
        gi.image_url,
        gi.thumbnail_url,
        gi.prompt,
        gi.generation_model,
        gi.generation_timestamp,
        gi.score,
        gi.score_breakdown,
        COALESCE(gi.approval_status, 'pending'),
        gi.approved_by,
        gi.approved_at,
        gi.rejection_reason,
        COALESCE(gi.ai_selected, false),
        COALESCE(gi.user_selected, false),
        gi.variation_index,
        gi.shopify_media_id,
        gi.shopify_cdn_url,
        gi.migrated_to_shopify_at,
        gi.created_at
    FROM generated_images gi
    JOIN variant_index vi ON vi.master_sku = gi.master_sku
    WHERE gi.use_for_master = true
      AND vi.shopify_product_id IS NOT NULL
    ON CONFLICT (master_sku, variation_index) DO NOTHING;

    RAISE NOTICE 'Migrated % product images', (SELECT COUNT(*) FROM product_lifestyle_images);
END $$;

-- Step 2: Migrate variant images (use_for_master = false) to variant_lifestyle_images
-- Match by master_sku + finish_code since gmc_offer_id is NULL in generated_images
DO $$
BEGIN
    INSERT INTO variant_lifestyle_images (
        master_sku,
        gmc_offer_id,
        finish,
        finish_code,
        image_url,
        thumbnail_url,
        prompt,
        generation_model,
        generation_timestamp,
        score,
        score_breakdown,
        approval_status,
        approved_by,
        approved_at,
        rejection_reason,
        ai_selected,
        user_selected,
        variation_index,
        shopify_media_id,
        shopify_cdn_url,
        migrated_to_shopify_at,
        gmc_pushed_at,
        created_at
    )
    SELECT DISTINCT ON (vi.gmc_offer_id, gi.variation_index)
        gi.master_sku,
        vi.gmc_offer_id,  -- Lookup from variant_index
        COALESCE(gi.finish, vi.finish),
        gi.finish_code,
        gi.image_url,
        gi.thumbnail_url,
        gi.prompt,
        gi.generation_model,
        gi.generation_timestamp,
        gi.score,
        gi.score_breakdown,
        COALESCE(gi.approval_status, 'pending'),
        gi.approved_by,
        gi.approved_at,
        gi.rejection_reason,
        COALESCE(gi.ai_selected, false),
        COALESCE(gi.user_selected, false),
        gi.variation_index,
        gi.shopify_media_id,
        gi.shopify_cdn_url,
        gi.migrated_to_shopify_at,
        gi.gmc_pushed_at,
        gi.created_at
    FROM generated_images gi
    JOIN variant_index vi ON vi.master_sku = gi.master_sku AND vi.finish_code = gi.finish_code
    WHERE gi.use_for_master = false
    ON CONFLICT (gmc_offer_id, variation_index) DO NOTHING;

    RAISE NOTICE 'Migrated % variant images', (SELECT COUNT(*) FROM variant_lifestyle_images);
END $$;

-- ============================================================================
-- Migration Verification
-- ============================================================================
-- Print verification report
DO $$
DECLARE
    old_master_count INTEGER;
    old_variant_count INTEGER;
    new_product_count INTEGER;
    new_variant_count INTEGER;
    orphaned_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO old_master_count FROM generated_images WHERE use_for_master = true;
    SELECT COUNT(*) INTO old_variant_count FROM generated_images WHERE use_for_master = false;
    SELECT COUNT(*) INTO new_product_count FROM product_lifestyle_images;
    SELECT COUNT(*) INTO new_variant_count FROM variant_lifestyle_images;

    SELECT COUNT(*) INTO orphaned_count
    FROM generated_images gi
    LEFT JOIN variant_index vi ON vi.master_sku = gi.master_sku
    WHERE gi.use_for_master = true AND vi.shopify_product_id IS NULL;

    RAISE NOTICE '';
    RAISE NOTICE '=== Migration Verification Report ===';
    RAISE NOTICE 'Old generated_images (master):     %', old_master_count;
    RAISE NOTICE 'New product_lifestyle_images:      %', new_product_count;
    RAISE NOTICE 'Old generated_images (variant):    %', old_variant_count;
    RAISE NOTICE 'New variant_lifestyle_images:      %', new_variant_count;
    RAISE NOTICE 'Orphaned master images (no Shopify ID): %', orphaned_count;
    RAISE NOTICE '';

    IF orphaned_count > 0 THEN
        RAISE WARNING 'Found % orphaned master images without Shopify product IDs', orphaned_count;
    END IF;

    IF new_product_count = 0 AND old_master_count > 0 THEN
        RAISE WARNING 'No product images migrated! Check foreign key constraints.';
    END IF;

    IF new_variant_count = 0 AND old_variant_count > 0 THEN
        RAISE WARNING 'No variant images migrated! Check master_sku + finish_code matching.';
    END IF;
END $$;

-- ============================================================================
-- Backup Old Table
-- ============================================================================
-- Rename generated_images to backup table for safety
-- Can be dropped after verifying migration succeeded

ALTER TABLE generated_images RENAME TO generated_images_backup_20260208;

COMMENT ON TABLE generated_images_backup_20260208 IS
'Backup of unified generated_images table before split into product_lifestyle_images and variant_lifestyle_images. Safe to drop after verifying migration. Created: 2026-02-08';

-- ============================================================================
-- Success Message
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '✅ Migration 023 completed successfully!';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Verify counts match expectations';
    RAISE NOTICE '2. Update TypeScript types (dashboard/src/lib/supabase/types.ts)';
    RAISE NOTICE '3. Update code to use new tables';
    RAISE NOTICE '4. Test end-to-end publishing flow';
    RAISE NOTICE '5. Drop backup table after verification: DROP TABLE generated_images_backup_20260208;';
    RAISE NOTICE '';
END $$;
