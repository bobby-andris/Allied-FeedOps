-- 003_content_storage_tables.sql
-- Migration for storing generated content in Supabase (currently in JSON files)
-- Part of the Next.js dashboard migration project.

-- ============================================================================
-- Generated Content Table
-- ============================================================================
-- Stores optimized titles and descriptions for each SKU/platform combination.
-- Replaces local JSON patch files (*-patch-*.json).

CREATE TABLE IF NOT EXISTS generated_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'google', 'bing', 'shopify'
    content_type TEXT NOT NULL,  -- 'title', 'description'
    
    -- Content versions
    baseline_content TEXT,  -- Original content from feed
    candidate_content TEXT,  -- AI-generated optimized content
    
    -- Quality metrics
    quality_score NUMERIC(5,2),  -- 0-100 score
    quality_breakdown JSONB,  -- Detailed scoring: {specificity, benefits, keywords, format, voice, accuracy}
    
    -- Generation metadata
    generation_model TEXT,  -- e.g., 'gpt-5.2', 'gemini-3-pro'
    generation_prompt_hash TEXT,  -- Hash of the prompt used (for version tracking)
    generation_timestamp TIMESTAMPTZ,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Ensure one content type per SKU/platform
    UNIQUE(master_sku, platform, content_type)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_content_sku ON generated_content(master_sku);
CREATE INDEX IF NOT EXISTS idx_content_platform ON generated_content(platform);
CREATE INDEX IF NOT EXISTS idx_content_score ON generated_content(quality_score DESC NULLS LAST);

-- ============================================================================
-- Generated Images Table
-- ============================================================================
-- Stores lifestyle image metadata and Supabase Storage URLs.
-- Each SKU can have multiple image variations.

CREATE TABLE IF NOT EXISTS generated_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    variation_index INTEGER NOT NULL,  -- 0, 1, 2, etc.
    
    -- Image storage
    image_url TEXT,  -- Supabase Storage URL
    thumbnail_url TEXT,  -- Optional thumbnail for faster loading
    
    -- Generation metadata
    prompt TEXT,  -- The prompt used to generate this image
    generation_model TEXT,  -- e.g., 'gemini-3-pro-image-preview'
    generation_timestamp TIMESTAMPTZ,
    
    -- Quality scoring
    score NUMERIC(5,2),  -- Image quality score (0-100)
    score_breakdown JSONB,  -- {composition, relevance, quality, brand_fit}
    
    -- Selection state
    selected BOOLEAN DEFAULT FALSE,  -- Is this the chosen image for this SKU?
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Ensure unique variation per SKU
    UNIQUE(master_sku, variation_index)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_images_sku ON generated_images(master_sku);
CREATE INDEX IF NOT EXISTS idx_images_selected ON generated_images(master_sku) WHERE selected = TRUE;
CREATE INDEX IF NOT EXISTS idx_images_score ON generated_images(master_sku, score DESC NULLS LAST);

-- ============================================================================
-- Generation Jobs Table
-- ============================================================================
-- Tracks content/image regeneration requests and their status.
-- Enables async generation workflow.

CREATE TABLE IF NOT EXISTS generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    job_type TEXT NOT NULL,  -- 'title', 'description', 'image', 'all'
    
    -- Job state
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed'
    priority INTEGER DEFAULT 0,  -- Higher = more urgent
    
    -- Input/Output
    input_params JSONB,  -- Job configuration (e.g., {platform: 'google', model: 'gpt-5.2'})
    result JSONB,  -- Job output when completed
    error TEXT,  -- Error message if failed
    
    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Retry tracking
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- Requestor
    requested_by TEXT
);

-- Indexes for job processing
CREATE INDEX IF NOT EXISTS idx_jobs_status ON generation_jobs(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_sku ON generation_jobs(master_sku, created_at DESC);

-- ============================================================================
-- Variant Index Table Enhancement
-- ============================================================================
-- Add columns to existing variant_index if it exists, or create it.
-- Maps GMC offer IDs to master SKUs with product details.

CREATE TABLE IF NOT EXISTS variant_index (
    id BIGSERIAL PRIMARY KEY,
    gmc_offer_id TEXT NOT NULL UNIQUE,
    master_sku TEXT NOT NULL,
    shopify_product_id TEXT,
    shopify_variant_id TEXT,
    finish TEXT,
    finish_code TEXT,
    dimensions TEXT,  -- e.g., "24 inch"
    product_title TEXT,
    product_category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_variant_master_sku ON variant_index(master_sku);
CREATE INDEX IF NOT EXISTS idx_variant_shopify ON variant_index(shopify_product_id);

-- ============================================================================
-- Row Level Security
-- ============================================================================
-- Enable RLS and allow full access (auth handled at app level)

ALTER TABLE generated_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE variant_index ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Allow all access" ON generated_content;
DROP POLICY IF EXISTS "Allow all access" ON generated_images;
DROP POLICY IF EXISTS "Allow all access" ON generation_jobs;
DROP POLICY IF EXISTS "Allow all access" ON variant_index;

-- Create policies
CREATE POLICY "Allow all access" ON generated_content FOR ALL USING (true);
CREATE POLICY "Allow all access" ON generated_images FOR ALL USING (true);
CREATE POLICY "Allow all access" ON generation_jobs FOR ALL USING (true);
CREATE POLICY "Allow all access" ON variant_index FOR ALL USING (true);

-- ============================================================================
-- Update timestamp trigger
-- ============================================================================
-- Automatically update the updated_at column on row updates.

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
DROP TRIGGER IF EXISTS update_generated_content_updated_at ON generated_content;
CREATE TRIGGER update_generated_content_updated_at
    BEFORE UPDATE ON generated_content
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_variant_index_updated_at ON variant_index;
CREATE TRIGGER update_variant_index_updated_at
    BEFORE UPDATE ON variant_index
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Storage Bucket Setup (run via Supabase dashboard or API)
-- ============================================================================
-- Note: Storage buckets cannot be created via SQL migrations.
-- Create a bucket named 'lifestyle-images' in the Supabase dashboard with:
--   - Public access: No (use signed URLs)
--   - File size limit: 10MB
--   - Allowed MIME types: image/png, image/jpeg, image/webp
--
-- SQL for storage policy (run in SQL editor after creating bucket):
--
-- CREATE POLICY "Allow authenticated uploads"
--   ON storage.objects FOR INSERT
--   WITH CHECK (bucket_id = 'lifestyle-images');
--
-- CREATE POLICY "Allow authenticated reads"
--   ON storage.objects FOR SELECT
--   USING (bucket_id = 'lifestyle-images');
